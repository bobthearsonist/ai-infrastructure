#!/usr/bin/env bash
# Manage the Fantastical MCP host bridge (launchd LaunchAgent).
# This is the host-process equivalent of `docker compose` for a containerized
# MCP — see the Rosetta table in readme.md.
set -euo pipefail

LABEL="com.bobthearsonist.fantastical-mcp"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$HERE/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"
PORT=7013
ERR_LOG="$HOME/Library/Logs/fantastical-mcp.err.log"

usage() { echo "usage: $0 {install|uninstall|start|stop|restart|status|logs [N]|test}"; exit 1; }

cmd="${1:-status}"
case "$cmd" in
  install)   # symlink plist into LaunchAgents (repo stays source of truth)
    mkdir -p "$HOME/Library/LaunchAgents"
    ln -sf "$PLIST_SRC" "$PLIST_DST"
    echo "linked $PLIST_DST -> $PLIST_SRC"
    echo "next: $0 start"
    ;;
  uninstall) # stop + remove symlink
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "unloaded + removed symlink"
    ;;
  start|load)        # ≈ compose up -d
    launchctl bootstrap "$DOMAIN" "$PLIST_DST"
    echo "bootstrapped $LABEL"
    ;;
  stop|unload)       # ≈ compose down
    launchctl bootout "$DOMAIN/$LABEL"
    echo "booted out $LABEL"
    ;;
  restart)           # ≈ compose restart
    launchctl kickstart -k "$DOMAIN/$LABEL"
    echo "kickstarted $LABEL"
    ;;
  status)            # ≈ docker ps + healthcheck
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null \
      | grep -E "state =|pid =|program =|last exit" || echo "agent: NOT loaded"
    printf 'health: '
    curl -s --max-time 3 "http://localhost:$PORT/healthz" || printf '(no response)'
    echo
    ;;
  logs)              # ≈ docker logs
    tail -n "${2:-50}" "$ERR_LOG"
    ;;
  test)              # REAL liveness probe — see the warning below.
    # Do NOT use /healthz as the pass condition. In both supergateway 3.4.3 and
    # 3.3.0 the --healthEndpoint route is an unconditional `res.send('ok')` with
    # no reference to the child process or the pool, so it returns ok even when
    # the bridge is completely dead. It reported healthy for 12 days straight
    # (2026-09-07 -> 09-19) while every SSE connection hung forever on an
    # exhausted child pool. Probe the actual MCP handshake instead: a working
    # bridge emits an `event: endpoint` line on /sse within a couple of seconds;
    # an exhausted pool accepts the connection, logs it, and sends nothing.
    #
    # Wait for the port first (absorbs npx cold-start on a fresh boot).
    for _ in $(seq 1 20); do
      curl -s --max-time 2 "http://localhost:$PORT/healthz" >/dev/null 2>&1 && break
      sleep 1
    done
    # NOTE: capture first, match second. Do NOT pipe curl into grep here — this
    # script runs `set -o pipefail`, and `curl --max-time` on an SSE stream always
    # exits 28 (it is a stream; it never ends on its own), so a piped form reports
    # FAIL even when the handshake succeeded. That exact bug gave a false FAIL on
    # a perfectly healthy bridge while writing this check.
    sse_out="$(curl -sN --max-time 8 "http://localhost:$PORT/sse" 2>/dev/null || true)"
    case "$sse_out" in
      *"event: endpoint"*)
      echo "OK :$PORT (MCP handshake responded)"
      ;;
      *)
      echo "FAIL :$PORT — no 'event: endpoint' on /sse."
      echo "  Port is listening and /healthz likely still says ok; that means the"
      echo "  child pool is exhausted (3.3.0 leaks a slot per error-path"
      echo "  disconnect and deadlocks once full). Recover with: $0 restart"
      exit 1
      ;;
    esac
    ;;
  *) usage ;;
esac
