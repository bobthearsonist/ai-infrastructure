"""
Single definition of "is this path indexable" for both indexers.

index_repos.py and index_obsidian.py use these to decide what to index, and
watcher.py uses the same functions to decide which file changes are worth a
reindex, so the two can never disagree. Imported by the long-running watcher,
so it must stay stdlib-only (no embedding, Qdrant or chunking imports).
"""

from pathlib import PurePath
from stat import S_ISREG

DEFAULT_MAX_FILE_BYTES = 1_000_000

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
