"""
Single definition of "is this path indexable" for both indexers.

index_repos.py and index_obsidian.py use these to decide what to index, and
watcher.py uses the same functions to decide which file changes are worth a
reindex, so the two can never disagree. Imported by the long-running watcher,
so it must stay stdlib-only (no embedding, Qdrant or chunking imports).
"""

import os
import subprocess
from pathlib import Path, PurePath, PurePosixPath
from stat import S_ISREG

DEFAULT_MAX_FILE_BYTES = 1_000_000
# A file whose mean line length exceeds this is minified/bundled JS or a
# one-line data blob. Real source, prose and pretty-printed JSON average well
# under 200; minified bundles average thousands. 0 disables the check.
DEFAULT_MAX_AVG_LINE_CHARS = 1000
# Below this size the mean is too noisy to judge (a short one-liner is fine).
_MINIFIED_MIN_CHARS = 4096
GIT_LS_TIMEOUT_SECONDS = 60

_REPO_SET_KEYS = (
    "skip_dirs", "skip_files", "skip_extensions",
    "index_extensions", "index_filenames",
)


# ── Repo indexer ───────────────────────────────────────────────

def is_repo_config(cfg: dict) -> bool:
    """True if cfg is a code-repo indexer config (as opposed to a vault's)."""
    return bool(cfg.get("repos_base") and cfg.get("repos"))


def normalize_repo_filter(cfg: dict) -> dict:
    """The repo filter keys of an indexer config, normalized: the five list
    keys become sets and max_file_bytes gets its default."""
    out: dict = {k: set(cfg.get(k) or []) for k in _REPO_SET_KEYS}
    out["max_file_bytes"] = cfg.get("max_file_bytes", DEFAULT_MAX_FILE_BYTES)
    out["max_avg_line_chars"] = cfg.get(
        "max_avg_line_chars", DEFAULT_MAX_AVG_LINE_CHARS)
    out["respect_gitignore"] = cfg.get("respect_gitignore", True)
    return out


def should_skip_dir(name: str, flt: dict) -> bool:
    """True if a directory is never descended into."""
    return name in flt["skip_dirs"] or name.endswith(".egg-info")


def should_index_name(name: str, flt: dict) -> bool:
    """True if a file's name marks it as indexable. Free, unlike the stat
    check in should_index_stat, so callers run it first."""
    suffix = PurePath(name).suffix.lower()

    if name in flt["skip_files"]:
        return False
    if suffix in flt["skip_extensions"]:
        return False
    # Compound extensions: PurePath.suffix only returns the LAST part, so
    # '.min.js'/'.min.css'/'.d.ts' skip entries never match via suffix.
    # Match the full filename so minified/generated vendor files are skipped.
    if any(name.endswith(ext) for ext in flt["skip_extensions"]):
        return False
    if name in flt["index_filenames"]:
        return True
    return suffix in flt["index_extensions"]


def should_index_stat(st, flt: dict) -> bool:
    """True if a stat result is an indexable file.

    Regular files only: a directory named like source would raise
    IsADirectoryError on read. Oversized files are generated/data/minified
    blobs that explode into thousands of chunks, dominate embed time, and
    pollute a code-search index."""
    return S_ISREG(st.st_mode) and st.st_size <= flt["max_file_bytes"]


def looks_minified(content: str, flt: dict) -> bool:
    """True if content is minified/bundled: big, with very long mean lines.
    Such files carry no searchable structure and explode into hundreds of
    near-identical chunks."""
    limit = flt.get("max_avg_line_chars", DEFAULT_MAX_AVG_LINE_CHARS)
    if not limit or len(content) < _MINIFIED_MIN_CHARS:
        return False
    return len(content) / (content.count("\n") + 1) > limit


# ── Git ignore rules ───────────────────────────────────────────

class GitListing:
    """The files git would show for a work tree: tracked plus untracked but
    not ignored (.gitignore, .git/info/exclude, core.excludesFile). Answers
    membership for paths relative to the listed root.

    Nested repositories and submodules are separate repositories that git
    reports as one opaque entry, so nothing under them is listed: a stray
    clone or worktree inside a repo is not indexed as part of it. List such a
    repo in `repos` to index it."""

    def __init__(self, paths: list[str]):
        self.files: set[str] = set()
        self.dirs: set[str] = {""}
        for p in paths:
            if p.endswith("/"):  # untracked nested repository
                continue
            self.files.add(p)
            parent = PurePosixPath(p).parent
            while str(parent) not in self.dirs and str(parent) != ".":
                self.dirs.add(str(parent))
                parent = parent.parent

    def has_dir(self, rel: str) -> bool:
        """True if the walk should descend into this root-relative dir."""
        return rel in self.dirs

    def has_file(self, rel: str) -> bool:
        """True if a root-relative file is tracked or untracked-not-ignored."""
        return rel in self.files


class GitListingError(Exception):
    """root is a git work tree but listing it failed (timeout, damaged
    index). Falling back to a plain walk here would index everything the
    repo ignores, so callers skip the root instead."""


def git_listing(root: Path) -> tuple[GitListing | None, str]:
    """List root with git so ignored files can be dropped, or (None, reason)
    when root is not in a git work tree or git is not installed, in which
    case callers fall back to a plain filesystem walk. Raises GitListingError
    for any other failure.

    safe.directory=* because the repos are bind-mounted into the indexer
    container under another owner; ls-files never writes, so a read-only
    mount is fine."""
    cmd = [
        "git", "-c", "safe.directory=*", "-C", str(root),
        "ls-files", "--cached", "--others", "--exclude-standard", "-z",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=GIT_LS_TIMEOUT_SECONDS,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except FileNotFoundError:
        return None, "git not installed"
    except (OSError, subprocess.SubprocessError) as e:
        raise GitListingError(f"git failed: {e}") from e
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace").strip()
        reason = stderr.splitlines()[-1] if stderr else f"git exited {proc.returncode}"
        # Also covers a worktree whose .git points outside the container.
        if "not a git repository" in stderr:
            return None, reason
        raise GitListingError(reason)
    paths = [p for p in proc.stdout.decode(errors="surrogateescape").split("\0") if p]
    return GitListing(paths), f"git ls-files: {len(paths)} paths"


# ── Vault indexer ──────────────────────────────────────────────

def is_vault_config(cfg: dict) -> bool:
    """True if cfg is an Obsidian vault indexer config."""
    return "routing" in cfg and "skip_unrouted" in cfg


def vault_skipped(rel_path: PurePath, skip_dirs: set[str]) -> bool:
    """True if any component of a vault-relative path is in skip_dirs."""
    return any(part in skip_dirs for part in rel_path.parts)


def vault_route(rel_path: PurePath, cfg: dict) -> str | None:
    """Collection a vault-relative path routes to by its top-level folder, or
    None when unrouted and skip_unrouted is set."""
    top_folder = rel_path.parts[0] if rel_path.parts else ""

    for collection, prefixes in cfg["routing"].items():
        if top_folder in prefixes:
            return collection

    if cfg["skip_unrouted"]:
        return None
    return cfg.get("default_collection")


def vault_name_indexable(name: str) -> bool:
    """The vault indexer's note rule. Case-sensitive, like rglob on Linux."""
    return name.endswith(".md")


def vault_indexable(rel_path: PurePath, cfg: dict) -> bool:
    """True if a vault-relative path is a note the vault indexer would index
    (assuming it is a regular file)."""
    return (
        vault_name_indexable(rel_path.name)
        and not vault_skipped(rel_path, set(cfg["skip_dirs"]))
        and vault_route(rel_path, cfg) is not None
    )
