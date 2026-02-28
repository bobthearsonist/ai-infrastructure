#!/usr/bin/env python3
"""Index Git repositories into a Qdrant 'code' collection."""

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# --- Constants (tied to mcp-server-qdrant, not user-configurable) ---

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "code"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384
VECTOR_NAME = "fast-all-minilm-l6-v2"  # Must match mcp-server-qdrant's naming
STATE_FILE = Path(__file__).parent / ".index_repos_state.json"
REPOS_CONFIG = Path(__file__).parent / "repos.json"

# Language detection by extension (logic, not config)
LANG_MAP = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".java": "java",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".cs": "csharp",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".fish": "fish",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json", ".toml": "toml",
    ".md": "markdown", ".txt": "text", ".rst": "rst",
    ".html": "html", ".css": "css", ".scss": "scss",
    ".sql": "sql", ".tf": "terraform", ".hcl": "hcl",
    ".xml": "xml", ".plist": "xml",
    ".lua": "lua", ".vim": "vim", ".el": "elisp",
    ".ini": "ini", ".cfg": "ini", ".conf": "config",
}


def load_config() -> dict:
    """Load all configuration from repos.json."""
    if not REPOS_CONFIG.exists():
        print(f"Config not found: {REPOS_CONFIG}")
        sys.exit(1)
    config = json.loads(REPOS_CONFIG.read_text())
    config["repos_base"] = Path(config["repos_base"]).expanduser()
    config["skip_dirs"] = set(config.get("skip_dirs", []))
    config["skip_files"] = set(config.get("skip_files", []))
    config["skip_extensions"] = set(config.get("skip_extensions", []))
    config["index_extensions"] = set(config.get("index_extensions", []))
    config["index_filenames"] = set(config.get("index_filenames", []))
    config.setdefault("max_chunk_chars", 1200)
    return config


def should_skip_dir(name: str, cfg: dict) -> bool:
    """Return True if directory should be skipped."""
    return name in cfg["skip_dirs"] or name.endswith(".egg-info")


def should_index_file(path: Path, cfg: dict) -> bool:
    """Return True if file should be indexed."""
    name = path.name
    suffix = path.suffix.lower()

    if name in cfg["skip_files"]:
        return False
    if suffix in cfg["skip_extensions"]:
        return False
    if name in cfg["index_filenames"]:
        return True
    if suffix in cfg["index_extensions"]:
        return True

    return False


def detect_language(path: Path) -> str:
    """Detect language from file extension."""
    if path.name == "Dockerfile":
        return "dockerfile"
    if path.name == "Makefile":
        return "makefile"
    return LANG_MAP.get(path.suffix.lower(), "text")


def file_hash(path: Path) -> str:
    """Return MD5 hex digest of file contents."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def chunk_code(content: str, language: str, max_chars: int) -> list[str]:
    """Split code into chunks, using language-appropriate boundaries."""
    if language == "markdown":
        return chunk_by_headers(content, max_chars)

    if language in ("python",):
        return chunk_by_pattern(content, r"^(?:class |def |async def )", max_chars)
    if language in ("typescript", "javascript"):
        return chunk_by_pattern(
            content,
            r"^(?:export\s+)?(?:async\s+)?(?:function |class |const \w+ = |interface |type )",
            max_chars,
        )
    if language in ("go",):
        return chunk_by_pattern(content, r"^(?:func |type )", max_chars)
    if language in ("rust",):
        return chunk_by_pattern(content, r"^(?:pub\s+)?(?:fn |struct |enum |impl |trait |mod )", max_chars)
    if language in ("ruby",):
        return chunk_by_pattern(content, r"^(?:class |module |def )", max_chars)
    if language in ("shell",):
        return chunk_by_pattern(content, r"^(?:\w+\s*\(\)|function )", max_chars)
    if language in ("csharp", "java"):
        return chunk_by_pattern(
            content,
            r"^(?:public|private|protected|internal|static)?\s*(?:class |interface |enum |void |async |[\w<>\[\]]+\s+\w+\s*\()",
            max_chars,
        )

    return chunk_by_paragraphs(content, max_chars)


def chunk_by_headers(content: str, max_chars: int) -> list[str]:
    """Split markdown by header boundaries."""
    sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
        else:
            chunks.extend(chunk_by_paragraphs(section, max_chars))
    return [c for c in chunks if len(c.strip()) > 30]


def chunk_by_pattern(content: str, pattern: str, max_chars: int) -> list[str]:
    """Split code by regex pattern (function/class definitions)."""
    sections = re.split(f"(?=(?:{pattern}))", content, flags=re.MULTILINE)
    chunks = []
    current = ""

    for section in sections:
        section = section.rstrip()
        if not section:
            continue

        if current and len(current) + len(section) + 1 > max_chars:
            chunks.append(current)
            current = section
        else:
            current = f"{current}\n{section}" if current else section

    if current:
        chunks.append(current)

    final = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            final.extend(chunk_by_lines(chunk, max_chars))

    return [c for c in final if len(c.strip()) > 30]


def chunk_by_paragraphs(content: str, max_chars: int) -> list[str]:
    """Split content by double-newline paragraph boundaries."""
    paragraphs = re.split(r"\n\n+", content)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)

    final = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            final.extend(chunk_by_lines(chunk, max_chars))

    return [c for c in final if len(c.strip()) > 30]


def chunk_by_lines(content: str, max_chars: int) -> list[str]:
    """Last resort: split by lines."""
    lines = content.split("\n")
    chunks = []
    current = ""

    for line in lines:
        if current and len(current) + len(line) + 1 > max_chars:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        chunks.append(current)

    return chunks


def load_state() -> dict:
    """Load previous indexing state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    """Persist indexing state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def make_point_id(repo: str, file_path: str, chunk_index: int) -> str:
    """Generate a deterministic UUID for a chunk."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{repo}::{file_path}::{chunk_index}"))


def ensure_collection(client: QdrantClient, name: str):
    """Create collection if it doesn't exist."""
    collections = [c.name for c in client.get_collections().collections]
    if name not in collections:
        client.create_collection(
            collection_name=name,
            vectors_config={
                VECTOR_NAME: VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            },
        )
        print(f"  Created collection: {name}")


def walk_repo(repo_path: Path, cfg: dict):
    """Walk repo yielding indexable files, respecting skip patterns."""
    for root, dirs, files in repo_path.walk():
        dirs[:] = [d for d in dirs if not should_skip_dir(d, cfg)]

        for fname in sorted(files):
            fpath = root / fname
            if should_index_file(fpath, cfg):
                yield fpath


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    cfg = load_config()
    repos_base = cfg["repos_base"]
    repos = cfg["repos"]
    max_chars = cfg["max_chunk_chars"]

    print(f"Repos base: {repos_base}")
    print(f"Repos: {len(repos)}")
    print(f"Qdrant: {QDRANT_URL}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Model: {EMBEDDING_MODEL}")
    if force:
        print("Mode: FULL RE-INDEX (--force)")
    if dry_run:
        print("Mode: DRY RUN (no writes)")
    print()

    # Validate repos exist
    missing = [r for r in repos if not (repos_base / r).exists()]
    if missing:
        print(f"WARNING: Missing repos: {', '.join(missing)}")
        print()

    # Initialize
    client = QdrantClient(url=QDRANT_URL)
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
    ensure_collection(client, COLLECTION_NAME)

    prev_state = {} if force else load_state()
    new_state = {}
    stats = {"skipped": 0, "indexed": 0, "unchanged": 0, "errors": 0, "chunks": 0}
    current_keys = set()

    for repo_name in repos:
        repo_path = repos_base / repo_name
        if not repo_path.exists():
            continue

        print(f"[{repo_name}]")
        repo_files = 0

        for fpath in walk_repo(repo_path, cfg):
            rel = fpath.relative_to(repo_path)
            rel_str = str(rel)
            state_key = f"{repo_name}::{rel_str}"
            current_keys.add(state_key)

            # Check if file changed
            try:
                h = file_hash(fpath)
            except Exception as e:
                print(f"  ERROR hashing {rel}: {e}")
                stats["errors"] += 1
                continue

            if state_key in prev_state and prev_state[state_key]["hash"] == h:
                new_state[state_key] = prev_state[state_key]
                stats["unchanged"] += 1
                continue

            # Read file
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"  ERROR reading {rel}: {e}")
                stats["errors"] += 1
                continue

            if not content.strip():
                stats["skipped"] += 1
                continue

            language = detect_language(fpath)
            chunks = chunk_code(content, language, max_chars)

            if not chunks:
                stats["skipped"] += 1
                continue

            # Prepend file context to each chunk for better embeddings
            context_prefix = f"{repo_name}/{rel_str}"
            texts = [f"{context_prefix}\n\n{chunk}" for chunk in chunks]

            try:
                vectors = list(embedder.passage_embed(texts))
            except Exception as e:
                print(f"  ERROR embedding {rel}: {e}")
                stats["errors"] += 1
                continue

            points = []
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                point_id = make_point_id(repo_name, rel_str, i)
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={VECTOR_NAME: vector.tolist()},
                        payload={
                            "document": chunk,
                            "metadata": {
                                "repo": repo_name,
                                "file_path": rel_str,
                                "language": language,
                                "chunk_index": i,
                                "total_chunks": len(chunks),
                                "collection": COLLECTION_NAME,
                                "last_modified": datetime.fromtimestamp(
                                    fpath.stat().st_mtime, tz=timezone.utc
                                ).isoformat(),
                            },
                        },
                    )
                )

            if not dry_run:
                # Delete old points first (chunk count may have changed)
                old = prev_state.get(state_key, {})
                old_count = old.get("chunks", 0)
                if old_count > 0:
                    old_ids = [make_point_id(repo_name, rel_str, i) for i in range(old_count)]
                    client.delete(collection_name=COLLECTION_NAME, points_selector=old_ids)

                client.upsert(collection_name=COLLECTION_NAME, points=points)

            new_state[state_key] = {"hash": h, "chunks": len(chunks)}
            stats["indexed"] += 1
            stats["chunks"] += len(chunks)
            repo_files += 1

        if repo_files:
            print(f"  {repo_files} files indexed")
        else:
            print(f"  (no changes)")

    # Clean up deleted files
    deleted = set(prev_state.keys()) - current_keys
    for del_key in deleted:
        old = prev_state[del_key]
        parts = del_key.split("::", 1)
        if len(parts) == 2:
            repo_name, rel_str = parts
            old_ids = [make_point_id(repo_name, rel_str, i) for i in range(old.get("chunks", 0))]
            if old_ids and not dry_run:
                client.delete(collection_name=COLLECTION_NAME, points_selector=old_ids)
        print(f"  DELETED {del_key}")

    if not dry_run:
        save_state(new_state)

    # Summary
    print()
    print("--- Summary ---")
    print(f"Indexed:   {stats['indexed']} files ({stats['chunks']} chunks)")
    print(f"Unchanged: {stats['unchanged']} files")
    print(f"Skipped:   {stats['skipped']} files")
    print(f"Errors:    {stats['errors']} files")
    print(f"Deleted:   {len(deleted)} files")

    info = client.get_collection(COLLECTION_NAME)
    print(f"Collection '{COLLECTION_NAME}': {info.points_count} points")


if __name__ == "__main__":
    main()
