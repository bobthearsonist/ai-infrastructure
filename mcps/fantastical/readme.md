# fantastical

Fantastical calendar MCP, exposed to the Dockerized gateways (agentgateway, mcpx)
via a **host** SSE bridge on port **7013**.

## Server: Flexibits' official helper

The stdio server is **FantasticalMCP**, the helper Flexibits ships inside the app at
`/Applications/Fantastical.app/Contents/Helpers/FantasticalMCP.app`. It is the same
server the Fantastical Claude Desktop extension runs, and it updates with the app.

Tools (Fantastical 4.2.4): `queryCalendars`, `queryCalendarSets`,
`queryCalendarItems`, `findAvailableTimes`, `createCalendarItem`,
`modifyCalendarItem`, `deleteCalendarItem`. They cover events and tasks, return ISO
8601 dates and stable item IDs, and carry `readOnlyHint` / `destructiveHint`
annotations.

### Why not `mcp-fantastical`

This bridge previously ran [`mcp-fantastical`](https://github.com/aplaceforallmystuff/mcp-fantastical),
a community server that drives Fantastical through AppleScript and EventKit. It was
replaced because:

- it only sees calendars macOS knows about, so Fantastical-only calendars (Openings,
  Proposals) and tasks were missing;
- output was locale strings, with event address lines misparsed as extra calendars
  and empty locations returned as `missing value`;
- it could read and create but not modify or delete;
- it ran unpinned from npm (`npx -y mcp-fantastical`).

Tested under this exact LaunchAgent + supergateway 3.3.0 setup before the switch:
`initialize`, `tools/list` and real `queryCalendars` / `queryCalendarItems` calls
all answered. Known quirks:

- On start the helper logs `MCP host identity unresolved: pid N has no valid code
  signature`, because Homebrew node is unsigned. It is info-level; calls still work.
- The first tool call on a freshly started helper was seen to stall once; later
  calls answered in 1-2 s.
- Run from a plain terminal shell or through a wrapper script, the helper can go
  silent. Launched by launchd or Claude Desktop it works.

## Why this one is different from every other MCP here

The helper talks to the running **Fantastical.app** and needs macOS **TCC**
(calendar access) granted in your logged-in GUI session.

That means it **cannot run in a container**. Docker on macOS is a Linux VM — no
Apple Events, no GUI session, no `Fantastical.app`. Network
reach-back (`host.docker.internal`) only shares the *network*, not Apple Events,
so there is no "let the container see the host" trick that helps. The work must
execute in macOS userland, in the Aqua session.

So this is the only MCP in the repo that runs as a **native host process** under
`launchd`, not as a container.

```
agentgateway / mcpx  (Linux VM containers)
        │   backend URL: http://host.docker.internal:7013/sse
        ▼
host.docker.internal ──► macOS host :7013
        ▼
   supergateway (launchd LaunchAgent)
        └─ FantasticalMCP (helper inside Fantastical.app) ──► Fantastical.app
```

## Bridge: supergateway (not mcp-proxy)

The rest of the repo standardizes on `sparfenyuk/mcp-proxy`, but the **host**
toolchain has Node/npx and **no `uv`** (mcp-proxy is a Python tool). So this
bridge uses [`supergateway`](https://github.com/supercorp-ai/supergateway):

- pure Node — runs through the `npx` already on the host, nothing to install.

It does **not** exit when its stdio child dies, and `/healthz` always returns ok.
Pinned to 3.3.0 with a pool of 8; the plist comments explain why. Use
`manage.sh test`, which probes the MCP handshake, not `/healthz`.

Command (baked into the plist):

```
npx -y supergateway@3.3.0 \
  --stdio /Applications/Fantastical.app/Contents/Helpers/FantasticalMCP.app/Contents/MacOS/FantasticalMCP \
  --port 7013 --baseUrl http://host.docker.internal:7013 --healthEndpoint /healthz \
  --minConcurrency 1 --maxConcurrency 8
```

SSE is served at `/sse`; the message endpoint is advertised as a relative path,
so the container→host hop resolves correctly without depending on `--baseUrl`.

## Install (one time)

```bash
./manage.sh install     # symlink plist into ~/Library/LaunchAgents
./manage.sh start       # launchctl bootstrap
./manage.sh test        # MCP handshake probe -> OK :7013
```

If macOS shows a calendar access prompt on the first tool call, allow it (GUI, can't
be scripted).

Requires **Fantastical** installed (the helper ships with it) and **Node 18+**
(Homebrew node runs supergateway).

## Manage (launchd ≈ docker compose)

| Intent | This | Compose analogue |
|--------|------|------------------|
| start  | `./manage.sh start`   | `compose up -d` |
| stop   | `./manage.sh stop`    | `compose down` |
| restart| `./manage.sh restart` | `compose restart` |
| status | `./manage.sh status`  | `docker ps` + healthcheck |
| logs   | `./manage.sh logs`    | `docker logs` |

Logs: `~/Library/Logs/fantastical-mcp.{out,err}.log`.

## Gateway wiring

- **agentgateway** — `gateways/agentgateway/config.yaml`: SSE target
  `fantastical` → `http://host.docker.internal:7013/sse`. No per-tool filtering
  at this layer (enforce at the client permission layer).
- **mcpx** — `mcps/mcpx/mcp.json` (SSE server) + `mcps/mcpx/app.yaml`
  (`calendar` toolGroup, granted to consumers). Per mcpx's permissions gate, a
  backend is hidden unless it is in an allowed toolGroup.

After editing either gateway's config, restart that gateway's container.

## Calendar writes

The helper exposes `createCalendarItem`, `modifyCalendarItem` and
`deleteCalendarItem`, not just reads. At the client permission layer (see
`permissions.yaml`), reads and create auto-approve, since a wrong new item is
cheap to fix, while modify and delete are gated to `ask`.
