# fantastical

Fantastical calendar MCP, exposed to the Dockerized gateways (agentgateway, mcpx)
via a **host** SSE bridge on port **7013**.

## Why this one is different from every other MCP here

[`mcp-fantastical`](https://github.com/aplaceforallmystuff/mcp-fantastical) drives
the **Fantastical.app** on macOS via **AppleScript + EventKit**, behind a signed
`FantasticalHelper.app` that requires macOS **TCC** (Full Calendar Access),
granted through a GUI prompt in your logged-in session.

That means it **cannot run in a container**. Docker on macOS is a Linux VM — no
AppleScript, no Apple Events, no GUI session, no `Fantastical.app`. Network
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
        └─ npx mcp-fantastical ──► AppleScript ──► Fantastical.app
```

## Bridge: supergateway (not mcp-proxy)

The rest of the repo standardizes on `sparfenyuk/mcp-proxy`, but the **host**
toolchain has Node/npx and **no `uv`** (mcp-proxy is a Python tool). So this
bridge uses [`supergateway`](https://github.com/supercorp-ai/supergateway):

- pure Node — runs through the `npx` already on the host, nothing to install;
- exits with its stdio child, so launchd `KeepAlive` respawns cleanly — it does
  **not** have mcp-proxy's [zombie-state bug](../../README.md), so no watchdog
  is needed.

Command (baked into the plist):

```
npx -y supergateway --stdio "npx -y mcp-fantastical" --port 7013 \
  --baseUrl http://host.docker.internal:7013 --healthEndpoint /healthz
```

SSE is served at `/sse`; the message endpoint is advertised as a relative path,
so the container→host hop resolves correctly without depending on `--baseUrl`.

## Install (one time)

```bash
./manage.sh install     # symlink plist into ~/Library/LaunchAgents
./manage.sh start       # launchctl bootstrap
./manage.sh test        # curl /healthz -> OK :7013
```

Then grant macOS permissions (GUI, can't be scripted):

1. The first calendar tool call triggers a **"FantasticalHelper" → Full Calendar
   Access** prompt → Allow.
2. If AppleScript errors appear: **System Settings → Privacy & Security →
   Accessibility** → enable the launching process (node/Terminal).

Requires **Fantastical** installed and **Node 18+** (uses Homebrew node).

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

`mcp-fantastical` exposes create/update tools, not just reads. Gate
create/update/delete to `ask` at the client permission layer (see
`permissions.yaml`) so calendar writes always prompt, even though reads
auto-approve.
