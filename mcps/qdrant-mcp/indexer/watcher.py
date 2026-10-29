#!/usr/bin/env python3
"""
Generic file watcher sidecar for the qdrant-mcp indexers.

Runs as a separate Compose service alongside an indexer.
Watches a path for changes and triggers incremental re-indexing
by invoking an indexer CLI as a subprocess. The subprocess approach
keeps the indexer CLI as the single source of truth and reuses its
existing hash-diff logic for incremental work.

This watcher is generic: the watched path, file extensions, indexer
command, and timing knobs all come from a YAML config file passed via
--config. That lets a single image power multiple watcher instances
(vault watcher, repo watcher, etc.) without code duplication.

Critical: uses stat-based polling (not native inotify) because Docker
Desktop on Windows + WSL2 does NOT reliably propagate filesystem events
across the bind-mount boundary. Each poll walks the same roots and
skip_dirs the indexer does (its config's repos, or watch_path when it
lists none), so .git / node_modules and unindexed repos are never stat'd.
Files are filtered with the indexer's own rules (filters.py), so a reindex
triggers only when a file the indexer would index changes mtime/size;
watched_extensions is the fallback for indexer configs of neither kind.
Polling is the only thing that actually works on this host topology.

Usage:
    python watcher.py --config /app/watcher.yaml

See watcher-obsidian.yaml.example for the schema.
"""

import argparse
import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from stat import S_ISREG
from pathlib import Path
from typing import Any, Callable, NamedTuple

import yaml

import filters

# ───────────────────────────────────────────────────────────────
# Config loading
# ───────────────────────────────────────────────────────────────

# Required top-level keys — no sensible default exists for these.
REQUIRED_KEYS = ["watch_path", "indexer_cmd"]

# Defaults for tuning knobs — overridable in YAML.
DEFAULTS: dict[str, Any] = {
    "debounce_seconds": 30,
    "poll_interval_seconds": 2,
    "min_interval_seconds": 60,
    "idle_only": True,
    "lockfile": "/app/.watcher.lock",
    "indexer_cwd": "/app",
    "lock_stale_seconds": 7200,
}

# A lockfile older than this is assumed to be orphaned by a crashed run
# rather than held by a live indexer. The lockfile lives in the container's
# writable layer, so a hard kill (OOM, docker kill, host reboot) skips the
# finally-block that would remove it AND survives a container restart —
# which silently froze the work-code index for 30 days. 2h is deliberately
# generous: the longest observed successful run was 801s.
DEFAULT_LOCK_STALE_SECONDS = 7200

# Fallback only. The real skip_dirs is read from the indexer's own config
# (see _indexer_config) so the watcher's poll-walk and the indexer's
# index-walk can never diverge — divergence was the original bug: the
# observer descended into 88 .git stores the indexer always skipped.
DEFAULT_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".eggs",
    ".next", ".nuxt", "coverage", ".nyc_output",
}


def _indexer_config(indexer_cmd: list[str]) -> dict:
    """Read the indexer's --config YAML (single source of truth for what the
    indexer walks). Returns {} if the config can't be located or parsed."""
    cfg_path = None
    for i, tok in enumerate(indexer_cmd):
        if tok in ("--config", "-c") and i + 1 < len(indexer_cmd):
            cfg_path = indexer_cmd[i + 1]
            break
    if not cfg_path or not Path(cfg_path).exists():
        return {}
    try:
        return yaml.safe_load(Path(cfg_path).read_text()) or {}
    except Exception:
        return {}


def _indexer_roots(indexer_cfg: dict) -> list[Path] | None:
    """The repo directories the indexer walks (repos_base/<repo>), or None
    when its config doesn't list repos (the vault indexer walks one tree).

    Polling only these keeps the walk the same size as what is indexed: the
    shared repos_base also holds worktrees and unindexed repos, which made
    each poll stat ~20x more files than the indexer would ever read."""
    base, repos = indexer_cfg.get("repos_base"), indexer_cfg.get("repos")
    if not base or not repos:
        return None
    return [Path(base).expanduser() / r for r in repos]


class FileFilter(NamedTuple):
    """Which files a snapshot keeps. name_ok is the cheap check on
    (root, dirpath, filename); stat_ok runs only on names that pass it."""

    description: str
    skip_dir: Callable[[str], bool]
    name_ok: Callable[[Path, str, str], bool]
    stat_ok: Callable[[os.stat_result], bool]


def _build_file_filter(
    indexer_cfg: dict, extensions: set[str], skip_dirs: set[str]
) -> FileFilter | None:
    """The filter matching what the indexer indexes: its repo or vault rules
    when its config is one, else the watched_extensions fallback (None when
    that is empty too)."""
    if filters.is_repo_config(indexer_cfg):
        flt = filters.normalize_repo_filter(indexer_cfg)
        return FileFilter(
            "indexer repo filter (filters.py)",
            lambda d: filters.should_skip_dir(d, flt),
            lambda root, dirpath, fn: filters.should_index_name(fn, flt),
            lambda st: filters.should_index_stat(st, flt),
        )
    if filters.is_vault_config(indexer_cfg):
        vault_skip = set(indexer_cfg["skip_dirs"] or [])

        def vault_name_ok(root: Path, dirpath: str, fn: str) -> bool:
            rel = Path(dirpath, fn).relative_to(root)
            return filters.vault_indexable(rel, indexer_cfg)

        return FileFilter(
            "indexer vault filter (filters.py)",
            lambda d: d in vault_skip,
            vault_name_ok,
            lambda st: S_ISREG(st.st_mode),
        )
    if extensions:
        return FileFilter(
            f"watched_extensions fallback {sorted(extensions)}",
            lambda d: d in skip_dirs or d.endswith(".egg-info"),
            lambda root, dirpath, fn: Path(fn).suffix.lower() in extensions,
            lambda st: True,
        )
    return None


def load_config(path: str) -> dict[str, Any]:
    """Load watcher config from YAML. Required keys must be present."""
    config_file = Path(path)
    if not config_file.exists():
        print(f"Error: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(config_file) as f:
        cfg = yaml.safe_load(f) or {}

    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        print(
            f"Error: Missing required config keys: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Apply defaults for optional keys
    for key, value in DEFAULTS.items():
        cfg.setdefault(key, value)

    # Normalize types
    cfg["watch_path"] = Path(cfg["watch_path"])
    exts = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in cfg.get("watched_extensions") or []
    }
    # indexer_cmd may be a list (preferred) or a string (we'll shlex-split)
    if isinstance(cfg["indexer_cmd"], str):
        cfg["indexer_cmd"] = shlex.split(cfg["indexer_cmd"])
    elif not isinstance(cfg["indexer_cmd"], list):
        print(
            "Error: indexer_cmd must be a list or string", file=sys.stderr
        )
        sys.exit(1)
    cfg["lockfile"] = Path(cfg["lockfile"])

    # skip_dirs and walk roots: prefer the indexer's own config (single source
    # of truth), then an explicit watcher-config key, then sane defaults.
    indexer_cfg = _indexer_config(cfg["indexer_cmd"])
    cfg["skip_dirs"] = (
        set(indexer_cfg.get("skip_dirs") or [])
        or set(cfg.get("skip_dirs", []))
        or DEFAULT_SKIP_DIRS
    )
    cfg["watch_roots"] = _indexer_roots(indexer_cfg) or [cfg["watch_path"]]
    cfg["file_filter"] = _build_file_filter(indexer_cfg, exts, cfg["skip_dirs"])
    if cfg["file_filter"] is None:
        print(
            "Error: indexer config is neither a repo nor a vault config, so "
            "watched_extensions is required",
            file=sys.stderr,
        )
        sys.exit(1)

    return cfg


# ───────────────────────────────────────────────────────────────
# Watcher implementation
# ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watcher] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


class DebouncedTrigger:
    """Coalesces a stream of filesystem events into bounded reindex runs."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._first_event_at: float | None = None
        self._last_run_at: float = 0.0
        self._stopping = threading.Event()
        self._debounce = cfg["debounce_seconds"]
        self._min_interval = cfg["min_interval_seconds"]
        self._idle_only = cfg["idle_only"]
        self._indexer_cmd = cfg["indexer_cmd"]
        self._indexer_cwd = cfg["indexer_cwd"]
        self._lockfile = cfg["lockfile"]
        self._lock_stale = cfg.get(
            "lock_stale_seconds", DEFAULT_LOCK_STALE_SECONDS
        )

    def schedule(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._first_event_at is None:
                self._first_event_at = now
            if self._idle_only and self._timer is not None:
                self._timer.cancel()
            elif not self._idle_only and self._timer is not None:
                return  # first-event-wins mode: keep the existing timer
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            since_last = time.monotonic() - self._last_run_at
            if since_last < self._min_interval:
                wait = self._min_interval - since_last
                log.info(
                    "skipping run; under min_interval_seconds, retrying in %.0fs",
                    wait,
                )
                self._timer = threading.Timer(wait, self._fire)
                self._timer.daemon = True
                self._timer.start()
                return
            self._first_event_at = None
            self._timer = None
            self._last_run_at = time.monotonic()
        self._run_indexer()

    def _lock_age_seconds(self) -> float | None:
        """Age of the lockfile in seconds, or None if it can't be stat'd
        (it vanished under us, or the stat failed). None is treated as
        'not stale' by the caller — the conservative choice, and it
        self-heals on the next poll."""
        try:
            return max(0.0, time.time() - self._lockfile.stat().st_mtime)
        except OSError:
            return None

    def _run_indexer(self) -> None:
        if self._lockfile.exists():
            age = self._lock_age_seconds()
            if age is None or age <= self._lock_stale:
                log.warning(
                    "lockfile present; another indexer run in progress, skipping"
                )
                return
            # Past the TTL: no live run lasts this long, so the holder died
            # without unlinking. Reclaim it instead of blocking forever.
            log.warning(
                "lockfile is %.1fh old (> %.1fh TTL); assuming it was orphaned "
                "by a crashed run, removing it and proceeding",
                age / 3600.0,
                self._lock_stale / 3600.0,
            )
            self._lockfile.unlink(missing_ok=True)
        try:
            self._lockfile.touch()
            log.info("triggering reindex: %s", " ".join(self._indexer_cmd))
            t0 = time.monotonic()
            # Inherit stdio so the indexer's progress streams live to the
            # container's stdout (docker logs) instead of being captured and
            # hidden until exit. PYTHONUNBUFFERED=1 keeps it real-time.
            result = subprocess.run(
                self._indexer_cmd,
                cwd=self._indexer_cwd,
            )
            dt = time.monotonic() - t0
            if result.returncode == 0:
                log.info("reindex complete in %.1fs", dt)
            else:
                log.error(
                    "reindex failed (exit %d) in %.1fs (see indexer output above)",
                    result.returncode,
                    dt,
                )
        finally:
            self._lockfile.unlink(missing_ok=True)

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()


def take_snapshot(
    roots: list[Path], flt: FileFilter
) -> dict[str, tuple[float, int]]:
    """Stat-walk each root, pruning skipped dirs, returning {path: (mtime,
    size)} for files the filter accepts. Metadata only — never reads file
    contents (that's the indexer's job, only on a detected change). A root
    that doesn't exist yet contributes nothing until it appears."""
    snap: dict[str, tuple[float, int]] = {}
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored dirs in place so os.walk never descends into them.
            dirnames[:] = [d for d in dirnames if not flt.skip_dir(d)]
            for fn in filenames:
                # Name checks first: every stat is a round trip to the host
                # filesystem on a Docker Desktop bind mount.
                if not flt.name_ok(root, dirpath, fn):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    st = os.stat(fp)
                except OSError:
                    continue
                if flt.stat_ok(st):
                    snap[fp] = (st.st_mtime, st.st_size)
    return snap


def _sample_paths(added: set[str], removed: set[str], modified: set[str]) -> str:
    """Up to 5 changed paths, marked +/-/~, for the change-detected line."""
    marked = (
        [f"+{p}" for p in sorted(added)]
        + [f"-{p}" for p in sorted(removed)]
        + [f"~{p}" for p in sorted(modified)]
    )
    more = len(marked) - 5
    return ", ".join(marked[:5]) + (f", ... (+{more} more)" if more > 0 else "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generic debounced filesystem watcher that triggers an indexer subprocess."
    )
    parser.add_argument(
        "--config",
        "-c",
        required=True,
        help="Path to watcher YAML config (see watcher-obsidian.yaml.example).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    watch_path: Path = cfg["watch_path"]

    if not watch_path.is_dir():
        log.error("watch path does not exist: %s", watch_path)
        return 1

    log.info(
        "starting watcher: path=%s filter=%s debounce=%ds poll=%ds idle_only=%s min_interval=%ds",
        watch_path,
        cfg["file_filter"].description,
        cfg["debounce_seconds"],
        cfg["poll_interval_seconds"],
        cfg["idle_only"],
        cfg["min_interval_seconds"],
    )
    log.info("indexer command: %s", " ".join(cfg["indexer_cmd"]))
    roots: list[Path] = cfg["watch_roots"]
    missing = [str(r) for r in roots if not r.is_dir()]
    log.info("walking %d root(s)%s", len(roots),
             f"; not present yet: {', '.join(missing)}" if missing else "")

    trigger = DebouncedTrigger(cfg)
    stop = threading.Event()

    def _shutdown(*_args) -> None:
        log.info("shutdown signal received")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    poll = cfg["poll_interval_seconds"]
    flt: FileFilter = cfg["file_filter"]

    try:
        # Build/refresh the index FIRST so it exists even if the first
        # snapshot walk is slow — the index build must never be gated behind
        # change-detection (the old ordering let a slow observer block it).
        log.info("running initial reconciliation pass")
        trigger._run_indexer()  # direct call, bypasses debounce

        # Baseline snapshot AFTER the build: only react to changes that land
        # once the index is current.
        t0 = time.monotonic()
        prev = take_snapshot(roots, flt)
        log.info(
            "baseline snapshot: %d watched files in %.1fs; polling every %ds",
            len(prev), time.monotonic() - t0, poll,
        )

        # Stat-poll loop: cheap metadata walk, debounced reindex only on delta.
        while not stop.is_set():
            stop.wait(poll)
            if stop.is_set():
                break
            cur = take_snapshot(roots, flt)
            if cur != prev:
                added = cur.keys() - prev.keys()
                removed = prev.keys() - cur.keys()
                modified = {
                    p for p in cur.keys() & prev.keys() if cur[p] != prev[p]
                }
                log.info(
                    "change detected (+%d/-%d/~%d): %s; scheduling reindex",
                    len(added), len(removed), len(modified),
                    _sample_paths(added, removed, modified),
                )
                prev = cur
                trigger.schedule()
    finally:
        trigger.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
