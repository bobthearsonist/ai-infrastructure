#!/usr/bin/env python3
"""Ask the RUNNING bridge whether it can see a valid Amazon session.

Why this exists rather than a curl one-liner: the bridge speaks MCP over SSE,
which is two coupled connections - a long-lived GET /sse that carries responses,
and POSTs to the per-session endpoint that stream announces. bash cannot hold
both.

Why it probes the bridge rather than the gateway: an anonymous JSON-RPC client
is not a consumer mcpx recognises, so it falls back to the `default` permission
group, which excludes `personal-finance` - the amazon-orders tools are simply
not callable that way. Going straight at :7014 sidesteps consumer identity
entirely and isolates "is the session good?" from "is the gateway stale?".

CAVEAT on what a pass proves: supergateway 3.3.0 POOLS stdio children, so this
probe may be answered either by the long-lived pre-warmed child or by a freshly
spawned one - it is not deterministic which. A PASS from a pool that contains a
child older than the cookie jar is strong evidence the server re-reads the jar
per call (so no bridge restart is needed after re-login). A FAIL is not proof of
the opposite, since it may simply be a stale child.

Exit codes: 0 signed in, 1 not signed in, 2 could not probe.
"""

import json
import queue
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

HOST = "http://localhost:7014"
TOOL = "check_session"
SSE_READ_TIMEOUT = 15
RPC_WAIT_TIMEOUT = 60


def read_sse(stream, lines):
    """Pump SSE lines into a queue until the stream ends."""
    try:
        for raw in stream:
            lines.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
    except Exception as e:  # stream closed/aborted; the main thread will time out
        lines.put(f"__ERROR__ {e}")
    finally:
        lines.put(None)


def next_event(lines, timeout):
    """Collect one SSE event's field lines, returning {field: value}."""
    event = {}
    while True:
        line = lines.get(timeout=timeout)
        if line is None:
            raise RuntimeError("SSE stream closed")
        if line.startswith("__ERROR__"):
            raise RuntimeError(line)
        if line == "":
            if event:
                return event
            continue  # keep-alive / leading blank
        field, _, value = line.partition(":")
        event[field.strip()] = value.strip()


def post(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def await_result(lines, want_id):
    """Read SSE events until the response with want_id arrives."""
    while True:
        event = next_event(lines, RPC_WAIT_TIMEOUT)
        data = event.get("data")
        if not data:
            continue
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg


def main():
    try:
        sse = urllib.request.urlopen(f"{HOST}/sse", timeout=SSE_READ_TIMEOUT)
    except (urllib.error.URLError, OSError) as e:
        print(f"probe: cannot reach the bridge at {HOST}/sse ({e})")
        print("probe: is the agent running? try: manage.sh status")
        return 2

    lines: "queue.Queue" = queue.Queue()
    threading.Thread(target=read_sse, args=(sse, lines), daemon=True).start()

    try:
        endpoint_event = next_event(lines, SSE_READ_TIMEOUT)
    except Exception as e:
        print(f"probe: no endpoint announced on /sse ({e})")
        print("probe: the child pool is likely exhausted; try: manage.sh restart")
        return 2

    path = endpoint_event.get("data")
    if not path:
        print(f"probe: unexpected first SSE event: {endpoint_event}")
        return 2
    endpoint = urllib.parse.urljoin(HOST, path)

    try:
        post(endpoint, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "amazon-orders-reauth-probe", "version": "1"},
            },
        })
        await_result(lines, 1)
        post(endpoint, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        post(endpoint, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": TOOL, "arguments": {}},
        })
        reply = await_result(lines, 2)
    except Exception as e:
        print(f"probe: MCP exchange failed ({e})")
        return 2

    if "error" in reply:
        print(f"probe: {TOOL} returned an error: {reply['error']}")
        return 2

    # tools/call wraps the payload in content[].text
    try:
        text = reply["result"]["content"][0]["text"]
        session = json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"probe: could not parse {TOOL} result ({e}): {reply.get('result')}")
        return 2

    signed_in = bool(session.get("signed_in"))
    site = session.get("site", "?")
    print(f"probe: signed_in={signed_in} site={site}")
    return 0 if signed_in else 1


if __name__ == "__main__":
    sys.exit(main())
