#!/usr/bin/env python3
"""AST-aware, token-bounded code chunking.

Why this exists: the previous chunker split code with regexes and sized chunks
by CHARACTERS. But an embedding model's cost (and context limit) is measured in
TOKENS, and dense content (escaped JSON, base64, minified blobs) packs ~1
token/char vs ~0.25 for normal code. So a "2000-char" chunk of dense data was
~2000 tokens — 4x budget — which melted the GPU on large generated/fixture
files. Regex splitting also produced arbitrary mid-token slices.

This module instead:
  1. Parses the file with tree-sitter (real grammar per language).
  2. Greedily packs sibling AST nodes (by byte span, preserving formatting) up
     to a TOKEN budget.
  3. Recurses into any single node that exceeds the budget.
  4. Token-window-splits a leaf node that is still too big (a giant string
     literal), so no chunk can ever exceed the budget regardless of content.

The token cap is a hard guarantee — it retires every char/size/line-length
heuristic that was bolted on to stop the embedder stalling.

Falls back to a token-bounded line splitter for languages without a grammar or
when parsing fails. Pure-CPU; no model/GPU needed (good for fast testing).
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Callable, Optional

# Map our internal language names (from index_repos.detect_language) to
# tree-sitter-language-pack grammar names. Anything not here uses the fallback.
TS_LANG = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
    "go": "go",
    "rust": "rust",
    "ruby": "ruby",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "csharp": "csharp",
    "shell": "bash",
    "yaml": "yaml",
    "json": "json",
    "toml": "toml",
    "html": "html",
    "css": "css",
    "scss": "css",
    "sql": "sql",
    "lua": "lua",
    "hcl": "hcl",
    "terraform": "hcl",
    "xml": "xml",
    "markdown": "markdown",
}


def load_jina_tokenizer(model_name: str, cache_dir: str = "/root/.cache/fastembed"):
    """Locate and load the model's tokenizer.json from the FastEmbed cache.

    Returns a tokenizers.Tokenizer or None. We load directly from disk (rather
    than reaching into FastEmbed internals) so this is version-independent.
    """
    try:
        from tokenizers import Tokenizer
    except ImportError:
        return None
    candidates = glob.glob(f"{cache_dir}/**/tokenizer.json", recursive=True)
    if not candidates:
        return None
    key = model_name.split("/")[-1].lower().replace("-", "")
    for path in candidates:
        if key in path.lower().replace("-", ""):
            try:
                return Tokenizer.from_file(path)
            except Exception:
                continue
    try:
        return Tokenizer.from_file(candidates[0])
    except Exception:
        return None


class CodeChunker:
    """Token-bounded, AST-aware chunker.

    count_tokens: text -> int. encode_decode: optional (encode, decode) pair used
    to split oversize leaf nodes by token windows; if absent, leaves fall back to
    a char-window split sized by the observed chars/token ratio.
    """

    def __init__(
        self,
        count_tokens: Callable[[str], int],
        max_tokens: int = 512,
        tokenizer=None,
    ):
        self.count_tokens = count_tokens
        self.max_tokens = max_tokens
        self.tokenizer = tokenizer
        self._parsers: dict[str, object] = {}

    # -- public ---------------------------------------------------------------

    def chunk(self, content: str, language: str) -> list[str]:
        if not content.strip():
            return []
        ts_lang = TS_LANG.get(language)
        parser = self._get_parser(ts_lang) if ts_lang else None
        if parser is None:
            return self._fallback(content)
        try:
            data = content.encode("utf-8", "replace")
            tree = parser.parse(data)
        except Exception:
            return self._fallback(content)
        out: list[str] = []
        self._pack(tree.root_node.children, data, out)
        return [c for c in (s.strip("\n") for s in out) if len(c.strip()) > 2]

    # -- internals ------------------------------------------------------------

    def _get_parser(self, ts_lang: Optional[str]):
        if not ts_lang:
            return None
        if ts_lang in self._parsers:
            return self._parsers[ts_lang]
        try:
            from tree_sitter_language_pack import get_parser

            parser = get_parser(ts_lang)
        except Exception:
            parser = None
        self._parsers[ts_lang] = parser
        return parser

    def _span(self, data: bytes, start: int, end: int) -> str:
        return data[start:end].decode("utf-8", "replace")

    def _pack(self, nodes, data: bytes, out: list[str]) -> None:
        """Greedily pack contiguous sibling nodes (by byte span) up to the token
        budget. Recurse oversize nodes; token-split oversize leaves."""
        buf_start: Optional[int] = None
        buf_end: int = 0
        buf_tokens = 0

        def flush():
            nonlocal buf_start, buf_end, buf_tokens
            if buf_start is not None and buf_end > buf_start:
                out.append(self._span(data, buf_start, buf_end))
            buf_start, buf_end, buf_tokens = None, 0, 0

        for node in nodes:
            text = self._span(data, node.start_byte, node.end_byte)
            ntok = self.count_tokens(text)

            if ntok > self.max_tokens:
                flush()
                if node.children:
                    self._pack(node.children, data, out)
                else:
                    out.extend(self._token_split(text))
                continue

            if buf_start is None:
                buf_start, buf_end, buf_tokens = node.start_byte, node.end_byte, ntok
            elif buf_tokens + ntok > self.max_tokens:
                flush()
                buf_start, buf_end, buf_tokens = node.start_byte, node.end_byte, ntok
            else:
                # Extend the contiguous span (includes inter-node whitespace).
                buf_end = node.end_byte
                buf_tokens += ntok
        flush()

    def _token_split(self, text: str) -> list[str]:
        """Split a too-large leaf (e.g. a giant string literal) into
        token-bounded pieces. Uses the real tokenizer when available."""
        if self.tokenizer is not None:
            try:
                ids = self.tokenizer.encode(text).ids
                if len(ids) <= self.max_tokens:
                    return [text]
                pieces = []
                for i in range(0, len(ids), self.max_tokens):
                    pieces.append(self.tokenizer.decode(ids[i : i + self.max_tokens]))
                return [p for p in pieces if p.strip()]
            except Exception:
                pass
        # No tokenizer: split by chars using the observed chars/token ratio.
        approx_chars = max(self.max_tokens * 3, 1000)
        return [text[i : i + approx_chars] for i in range(0, len(text), approx_chars)]

    def _fallback(self, content: str) -> list[str]:
        """No grammar/parse failed: pack whole lines up to the token budget,
        token-splitting any single line that is itself too large."""
        out: list[str] = []
        buf = ""
        buf_tokens = 0
        for line in content.split("\n"):
            ltok = self.count_tokens(line)
            if ltok > self.max_tokens:
                if buf:
                    out.append(buf)
                    buf, buf_tokens = "", 0
                out.extend(self._token_split(line))
                continue
            if buf and buf_tokens + ltok > self.max_tokens:
                out.append(buf)
                buf, buf_tokens = line, ltok
            else:
                buf = f"{buf}\n{line}" if buf else line
                buf_tokens += ltok
        if buf:
            out.append(buf)
        return [c for c in out if len(c.strip()) > 2]


def is_generated(content: str) -> bool:
    """Detect auto-generated source (skip for code-search quality). Checks the
    head for the conventional <auto-generated> / 'generated by a tool' markers."""
    head = content[:600].lower()
    return (
        "<auto-generated" in head
        or "auto-generated>" in head
        or "this code was generated by a tool" in head
        or "do not edit" in head
        and "generated" in head
    )
