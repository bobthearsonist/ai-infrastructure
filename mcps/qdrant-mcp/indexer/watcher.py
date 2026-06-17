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
(vault watcher with .md only, repo watcher with ~50 source extensions,
etc.) without code duplication.

Critical: uses stat-based polling (not native inotify) because Docker
Desktop on Windows + WSL2 does NOT reliably propagate filesystem events
across the bind-mount boundary. Each poll walks the tree honoring the
indexer's skip_dirs (so .git / node_modules are never stat'd) and
triggers a reindex only when a watched file's mtime/size changes.
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
from pathlib import Path
from typing import Any

import yaml

# ───────────────────────────────────────────────────────────────
# Config loading
# ───────────────────────────────────────────────────────────────

# Required top-level keys — no sensible default exists for these.
REQUIRED_KEYS = ["watch_path", "watched_extensions", "indexer_cmd"]

# Defaults for tuning knobs — overridable in YAML.
DEFAULTS: dict[str, Any] = {
    "debounce_seconds": 30,
    "poll_interval_seconds": 2,
    "min_interval_seconds": 60,
    "idle_only": True,
    "lockfile": "/app/.watcher.lock",
    "indexer_cwd": "/app",
}

# Fallback only. The real skip_dirs is read from the indexer's own config
# (see _indexer_skip_dirs) so the watcher's poll-walk and the indexer's
# index-walk can never diverge — divergence was the original bug: the
# observer descended into 88 .git stores the indexer always skipped.
DEFAULT_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".eggs",
    ".next", ".nuxt", "coverage", ".nyc_output",
}


def _indexer_skip_dirs(indexer_cmd: list[str]) -> set[str] | None:
    """Read skip_dirs from the indexer's --config YAML (single source of
    truth). Returns None if the config can't be located or parsed."""
    cfg_path = None
    for i, tok in enumerate(indexer_cmd):
        if tok in ("--config", "-c") and i + 1 < len(indexer_cmd):
            cfg_path = indexer_cmd[i + 1]
            break
    if not cfg_path or not Path(cfg_path).exists():
        return None
    try:
        data = yaml.safe_load(Path(cfg_path).read_text()) or {}
    except Exception:
        return None
    sd = data.get("skip_dirs")
    return set(sd) if sd else None


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
    cfg["watched_extensions"] = {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in cfg["watched_extensions"]
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

    # skip_dirs: prefer the indexer's own config (single source of truth),
    # then an explicit watcher-config key, then sane defaults.
    cfg["skip_dirs"] = (
        _indexer_skip_dirs(cfg["indexer_cmd"])
        or set(cfg.get("skip_dirs", []))
        or DEFAULT_SKIP_DIRS
    )

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

    def _run_indexer(self) -> None:
        if self._lockfile.exists():
            log.warning(
                "lockfile present; another indexer run in progress, skipping"
            )
            return
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
    root: Path, extensions: set[str], skip_dirs: set[str]
) -> dict[str, tuple[float, int]]:
    """Stat-walk `root`, pruning skip_dirs, returning {path: (mtime, size)}
    for files whose extension is watched. Metadata only — never reads file
    contents (that's the indexer's job, only on a detected change)."""
    snap: dict[str, tuple[float, int]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored dirs in place so os.walk never descends into them.
        dirnames[:] = [
            d for d in dirnames
            if d not in skip_dirs and not d.endswith(".egg-info")
        ]
        for fn in filenames:
            if Path(fn).suffix.lower() not in extensions:
                continue
            fp = os.path.join(dirpath, fn)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            snap[fp] = (st.st_mtime, st.st_size)
    return snap


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
        "starting watcher: path=%s extensions=%s debounce=%ds poll=%ds idle_only=%s min_interval=%ds",
        watch_path,
        sorted(cfg["watched_extensions"]),
        cfg["debounce_seconds"],
        cfg["poll_interval_seconds"],
        cfg["idle_only"],
        cfg["min_interval_seconds"],
    )
    log.info("indexer command: %s", " ".join(cfg["indexer_cmd"]))

    trigger = DebouncedTrigger(cfg)
    stop = threading.Event()

    def _shutdown(*_args) -> None:
        log.info("shutdown signal received")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    poll = cfg["poll_interval_seconds"]
    extensions = cfg["watched_extensions"]
    skip_dirs = cfg["skip_dirs"]

    try:
        # Build/refresh the index FIRST so it exists even if the first
        # snapshot walk is slow — the index build must never be gated behind
        # change-detection (the old ordering let a slow observer block it).
        log.info("running initial reconciliation pass")
        trigger._run_indexer()  # direct call, bypasses debounce

        # Baseline snapshot AFTER the build: only react to changes that land
        # once the index is current.
        t0 = time.monotonic()
        prev = take_snapshot(watch_path, extensions, skip_dirs)
        log.info(
            "baseline snapshot: %d watched files in %.1fs; polling every %ds",
            len(prev), time.monotonic() - t0, poll,
        )

        # Stat-poll loop: cheap metadata walk, debounced reindex only on delta.
        while not stop.is_set():
            stop.wait(poll)
            if stop.is_set():
                break
            cur = take_snapshot(watch_path, extensions, skip_dirs)
            if cur != prev:
                added = cur.keys() - prev.keys()
                removed = prev.keys() - cur.keys()
                modified = {
                    p for p in cur.keys() & prev.keys() if cur[p] != prev[p]
                }
                log.info(
                    "change detected (+%d/-%d/~%d); scheduling reindex",
                    len(added), len(removed), len(modified),
                )
                prev = cur
                trigger.schedule()
    finally:
        trigger.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
