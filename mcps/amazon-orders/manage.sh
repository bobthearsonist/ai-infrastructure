#!/usr/bin/env bash
# Manage the Amazon Orders MCP host bridge (launchd LaunchAgent).
# This is the host-process equivalent of `docker compose` for a containerized
# MCP — see the Rosetta table in ../fantastical/readme.md.
set -euo pipefail

LABEL="com.bobthearsonist.amazon-orders-mcp"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$HERE/${LABEL}.plist"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"
PORT=7014
ERR_LOG="$HOME/Library/Logs/amazon-orders-mcp.err.log"
JAR="$HOME/.config/amazonorders/cookies.json"
PROBE="$HERE/bin/probe-session.py"

usage() { echo "usage: $0 {install|uninstall|start|stop|restart|status|logs [N]|test|login|jar|probe|bounce-gateway|reauth}"; exit 1; }

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
    "$0" jar
    ;;
  logs)              # ≈ docker logs
    tail -n "${2:-50}" "$ERR_LOG"
    ;;
  test)              # REAL liveness probe — see the warning below.
    # Do NOT use /healthz as the pass condition. In supergateway 3.3.0 the
    # --healthEndpoint route is an unconditional `res.send('ok')` with no
    # reference to the child process or the pool, so it returns ok even when the
    # bridge is completely dead. On the Fantastical bridge it reported healthy
    # for 12 days while every SSE connection hung on an exhausted child pool.
    # Probe the actual MCP handshake: a working bridge emits an `event: endpoint`
    # line on /sse within a couple of seconds; an exhausted pool accepts the
    # connection, logs it, and sends nothing.
    #
    # Wait for the port first (absorbs uvx cold-start on a fresh boot).
    for _ in $(seq 1 20); do
      curl -s --max-time 2 "http://localhost:$PORT/healthz" >/dev/null 2>&1 && break
      sleep 1
    done
    # NOTE: capture first, match second. Do NOT pipe curl into grep here — this
    # script runs `set -o pipefail`, and `curl --max-time` on an SSE stream
    # always exits 28 (it is a stream; it never ends on its own), so a piped form
    # reports FAIL even when the handshake succeeded.
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
  login)             # one-time (and occasional) interactive Amazon sign-in
    # Runs on the HOST, in a real browser, against Amazon's own sign-in page.
    # Neither this script nor the MCP server ever sees the password or the OTP.
    # Writes/refreshes $JAR, which is the only thing the bridge needs.
    # The --browser flag needs the `browser` extra, which plain
    # `uvx amazon-orders` does NOT pull in; without --from it exits complaining
    # about a missing extra rather than opening anything.
    echo "Opening Amazon sign-in in a browser. Complete it there (2FA included)."
    uvx --from 'amazon-orders[browser]' amazon-orders login --browser
    "$0" jar
    echo "note: the bridge caches a pre-warmed child; run '$0 restart' so it"
    echo "      picks up a jar that did not exist when it started."
    ;;
  jar)               # report session-jar presence WITHOUT printing its contents
    if [ -f "$JAR" ]; then
      echo "jar: present — $JAR ($(date -r "$JAR" '+%Y-%m-%d %H:%M'), $(wc -c <"$JAR" | tr -d ' ') bytes)"
    else
      echo "jar: ABSENT — $JAR"
      echo "     the bridge will answer tools/list but every data tool will report"
      echo "     signed_in:false. Fix with: $0 login"
    fi
    ;;
  probe)             # does the RUNNING bridge see a valid Amazon session?
    # Asks the bridge on :7014 directly, not through mcpx: an anonymous client
    # is not a consumer mcpx recognises, so it falls back to the `default`
    # permission group, which excludes `personal-finance` and cannot call these
    # tools at all. See bin/probe-session.py for what a pass does and does not
    # prove about the pooled child.
    python3 -I "$PROBE"
    ;;
  bounce-gateway)    # make mcpx re-dial this bridge
    # Restarting the bridge orphans mcpx's long-lived upstream SSE session; it
    # does not re-dial, and every tool call then fails with
    #   MCP error -32602: Invalid request parameters
    # while `$0 test` reports the bridge perfectly healthy. The parameters are
    # fine; the session is dead. Only bouncing mcpx fixes it.
    #
    # stop+start, NEVER `docker restart`: mcpx is privileged Docker-in-Docker and
    # `restart` leaves the container's PID namespace intact, so the inner
    # daemon's stale pid survives and the new one dies with "failed to save
    # daemon pid to disk: process with PID N is still running", looping every
    # ~45s indefinitely. A real stop tears the namespace down.
    echo "bouncing mcpx (this briefly takes down EVERY mcpx-served MCP)..."
    docker stop -t 30 mcpx
    docker start mcpx
    printf 'waiting for mcpx :9000 '
    for _ in $(seq 1 60); do
      if curl -s --max-time 2 -o /dev/null "http://localhost:9000/mcp"; then
        echo " up"
        exit 0
      fi
      printf '.'
      sleep 2
    done
    echo " TIMED OUT"
    echo "  check: docker logs --tail 40 mcpx"
    exit 1
    ;;
  reauth)            # full recovery after the Amazon session expires
    # Runs the steps in the one order that works, probing between each so no
    # step is taken on faith.
    #
    # MEASURED 2026-11-23: a running child holds its Amazon session IN MEMORY,
    # not re-read from the jar per call -- deleting the jar outright left the
    # same child still reporting signed_in=true. So a refreshed jar cannot be
    # assumed to reach an already-running child, and the restart below is the
    # safe step rather than a precaution. The probe still runs first, because if
    # the bridge already reports a working session there is by definition
    # nothing to fix, whatever the mechanism.
    before=""
    [ -f "$JAR" ] && before="$(date -r "$JAR" '+%s')"

    "$0" login || exit 1

    if [ ! -f "$JAR" ]; then
      echo "reauth: FAILED — no jar was written; sign-in did not complete."
      exit 1
    fi
    if [ -n "$before" ] && [ "$(date -r "$JAR" '+%s')" = "$before" ]; then
      echo "reauth: FAILED — jar is unchanged; sign-in did not complete."
      exit 1
    fi

    echo
    echo "reauth: jar refreshed. Does the running bridge already see it?"
    if "$0" probe; then
      echo
      echo "reauth: YES — nothing to fix, so stopping here."
      echo "  The bridge already reports a working session, so restarting it"
      echo "  would only orphan mcpx's session and force a needless gateway"
      echo "  bounce. Expected when the old session had not actually expired."
      echo
      echo "  If a client still fails with -32602, its session predates this"
      echo "  and only then: $0 bounce-gateway"
      exit 0
    fi

    echo
    echo "reauth: NO — the bridge is holding a stale session. Restarting it."
    "$0" restart
    sleep 3
    if ! "$0" probe; then
      echo
      echo "reauth: FAILED — bridge still reports no session after a restart."
      echo "  The jar exists but Amazon is rejecting it. Try: $0 login"
      exit 1
    fi

    echo
    echo "reauth: the restart fixed it, as expected for a genuinely expired"
    echo "  session. That orphaned mcpx's upstream session, so the gateway must"
    echo "  be bounced for any client to reach these tools."
    printf 'bounce mcpx now? every mcpx-served MCP drops briefly [y/N] '
    read -r reply
    case "$reply" in
      [yY]*) "$0" bounce-gateway ;;
      *) echo "skipped. run when ready: $0 bounce-gateway" ;;
    esac
    ;;
  *) usage ;;
esac
