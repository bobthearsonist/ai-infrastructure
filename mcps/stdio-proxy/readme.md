# stdio-proxy

Runs multiple stdio-based MCP servers as SSE endpoints using [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy).

## Architecture

- **Included per-stack** via Compose `include:` — each gateway (mcpx, agentgateway) gets its own instance
- **Per-machine config** via `SERVERS_CONFIG` env var — selects which `servers.*.json` to mount
- **No baked-in config** — `servers.json` must be provided via volume mount

## Per-Machine Configuration

The committed `servers.json` contains only servers common to all machines (currently just `sequential-thinking`). Machine-specific servers go in local config files that are gitignored.

| File | Machine | Servers |
|------|---------|---------|
| `servers.json` | All (baseline) | sequential-thinking |
| `servers.windows-work.json` | Work (Windows) | sequential-thinking, azure-devops |
| `servers.home.json` | Home (macOS) | sequential-thinking, kapture, photoshop |

Set `SERVERS_CONFIG` in your local `.env` file to select which config to use:

```bash
# .env (gitignored)
SERVERS_CONFIG=./servers.windows-work.json
```

If `SERVERS_CONFIG` is not set, defaults to `./servers.json` (baseline).

## Endpoints

Each MCP server is exposed at `/servers/{name}/sse` on port 7030.

Example: `http://stdio-proxy:7030/servers/sequential-thinking/sse`

## Adding a New Server

1. Add the server definition to the appropriate `servers.*.json` file
2. Rebuild: `docker compose up -d --build` (from the parent gateway stack)

## Why mcp-proxy?

|              | [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) | [supergateway](https://github.com/supercorp-ai/supergateway) |
|--------------|------------------------------------------------------|--------------------------------------------------------------|
| Multi-server | ✅ Single config file, single port                    | ❌ Separate process per server                                |
| Routing      | `/servers/{name}/sse`                                | Multiple ports                                               |
| Consistency  | Already used in browser-use, hass-mcp                | New dependency                                               |

## Related

- [memory](../memory/readme.md) — Standalone shared memory MCP
- [mcpx](../mcpx/) — Lunar mcpx gateway (includes stdio-proxy)
- [agentgateway](../../gateways/agentgateway/) — Agent gateway (includes stdio-proxy)
