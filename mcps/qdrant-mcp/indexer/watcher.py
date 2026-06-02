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

Critical: uses PollingObserver (not native inotify) because Docker
Desktop on Windows + WSL2 does NOT reliably propagate filesystem
events across the bind-mount boundary. Polling is slightly more CPU
but is the only thing that actually works on this host topology.

Usage:
    python watcher.py --config /app/watcher.yaml

See watcher-obsidian.yaml.example for the schema.
"""

import argparse
import logging
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

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
            result = subprocess.run(
                self._indexer_cmd,
                cwd=self._indexer_cwd,
                capture_output=True,
                text=True,
            )
            dt = time.monotonic() - t0
            if result.returncode == 0:
                log.info("reindex complete in %.1fs", dt)
            else:
                log.error(
                    "reindex failed (exit %d) in %.1fs\nstdout: %s\nstderr: %s",
                    result.returncode,
                    dt,
                    result.stdout[-2000:],
                    result.stderr[-2000:],
                )
        finally:
            self._lockfile.unlink(missing_ok=True)

    def stop(self) -> None:
        self._stopping.set()
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()


class WatchedEventHandler(FileSystemEventHandler):
    def __init__(
        self, trigger: DebouncedTrigger, watched_extensions: set[str]
    ) -> None:
        self.trigger = trigger
        self._extensions = watched_extensions

    def _interesting(self, path: str) -> bool:
        return Path(path).suffix.lower() in self._extensions

    def on_any_event(self, event) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        if not self._interesting(event.src_path):
            return
        log.debug("change detected: %s %s", event.event_type, event.src_path)
        self.trigger.schedule()


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
    handler = WatchedEventHandler(trigger, cfg["watched_extensions"])
    observer = PollingObserver(timeout=cfg["poll_interval_seconds"])
    observer.schedule(handler, str(watch_path), recursive=True)
    observer.start()

    stop = threading.Event()

    def _shutdown(*_args) -> None:
        log.info("shutdown signal received")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        # Initial reconciliation on startup catches anything that drifted
        # while the watcher was offline.
        log.info("running initial reconciliation pass")
        trigger._run_indexer()  # direct call, bypasses debounce
        stop.wait()
    finally:
        trigger.stop()
        observer.stop()
        observer.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
