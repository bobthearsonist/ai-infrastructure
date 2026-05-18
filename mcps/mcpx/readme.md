# MCPX

MCPX is a MCP gateway/proxy by [Lunar.dev](https://docs.lunar.dev/mcpx/architecture). It acts as a common entrypoint for multiple MCP servers, routing requests to the appropriate backend. It solves the problem of AI clients creating their own containers for each MCP and instead provides a single gateway shared between clients.

Key features:

- **Tool Groups** — named sets of tools assigned to clients/agents
- **Agent Access Control** — per-consumer tool group permissions
- **Tool Catalog** — customizable tool descriptions and visibility
- **Metrics & Audit Logs** — usage stats and audit trail
- **OAuth / API Key Auth** — secure access to gateway
- **Disconnection-safe caching** — tool calls survive disconnections (v0.2.28+)

See <https://docs.lunar.dev/> and <https://docs.lunar.dev/mcpx/architecture>

## MCP Servers

| Server | Type | Source | Port |
|--------|------|--------|------|
| sequential-thinking | stdio (npx) | Built-in | — |
| memory | stdio (npx) | Built-in | — |
| kapture | stdio (npx) | Built-in | — |
| photoshop | SSE | stdio-proxy | 7030 |
| context7 | SSE | Container | 7008 |
| playwright | SSE | Container | 7007 |
| browser-use | SSE | Container | 7011 |
| hass-mcp | SSE | Container | 7010 |

## Tool Groups

Defined in [app.yaml](app.yaml):

| Group | Servers | Purpose |
|-------|---------|---------|
| core | sequential-thinking, memory | Always assigned — thinking + persistence |
| coding | context7 | Library docs |
| knowledge-work | qdrant-work | Work-context RAG (Obsidian notes via qdrant-mcp) |
| knowledge-code | qdrant-code | Indexed source-code RAG |
| knowledge-personal | qdrant-personal | Personal-context RAG |
| devops | azure-devops | Azure DevOps work items / pipelines (when configured) |
| diagrams | mermaid | Mermaid diagram rendering (when configured) |
| homelab | hass-mcp | Home Assistant |
| browser | kapture, playwright | Browser automation |
| creative | photoshop | Adobe Photoshop |

### How a tool actually reaches a client

mcpx 0.4.x gates tool visibility through TWO layers — both must pass:

1. **mcp.json** lists every backend mcpx connects to. Anything not here isn't talked to.
2. **app.yaml** controls what mcpx *exposes*. A backend is only surfaced if:
   - It appears in a `toolGroups` entry, AND
   - That group name is in the active consumer's `permissions.consumers.<name>.allow` list (or `permissions.default.allow` for unknown consumers).

If either condition fails, mcpx **silently drops** the backend from `tools/list` — no error, no warning at INFO log level. Backends will still log `Client connected` and appear in `count=N`. Easy to miss.

When adding a new backend: add it to mcp.json, then add it to a `toolGroups` entry, then add that group to every consumer's `allow` that needs to see it.

### Diagnosing a missing backend

If tools don't appear in a client even though the backend looks connected:

```bash
# Bump log verbosity, restart, then look for the loaded-config dump
docker compose exec mcpx sh -c 'echo "set LOG_LEVEL=debug in compose env, restart"'
docker logs mcpx --since 1m 2>&1 | grep -A1 "Config loaded successfully"
```

The dump shows the exact `permissions` and `toolGroups` mcpx parsed. Cross-reference with the consumer name to see why your backend isn't surfacing.

This was a major behavior change between mcpx 0.2.x (`:stable`) and 0.4.x (`:latest`); the older version surfaced everything in mcp.json. Saved as memory `reference_mcpx_permissions_gate`.

## Prerequisites

- SSE/HTTP-based MCPs (playwright, hass-mcp via stdio-proxy, context7, qdrant-mcp) must be running and reachable
- stdio-proxy must be running on port 7030 for photoshop, hass-mcp, and kapture (mcpx-stdio-proxy alias on the private network)
- SSL certs in `./certs/tls/` for HTTPS (optional)

Note: `browser-use` is currently moved to `_disabledMcpServers` in mcp.json — re-enable it there before expecting it to connect.

## Usage

```bash
# Pull latest and start
docker compose pull && docker compose up -d
```

Dashboard: <http://localhost:5173/dashboard>

### Endpoints

| Protocol | HTTP | HTTPS |
|----------|------|-------|
| SSE | http://localhost:9000/sse | https://localhost:9443/sse |
| MCP | http://localhost:9000/mcp | https://localhost:9443/mcp |
| Dashboard | http://localhost:5173 | https://localhost:5443 |

## Configuration

- [mcp.json](mcp.json) — MCP server definitions (restart required after changes)
- [app.yaml](app.yaml) — Tool groups, permissions, auth settings
- [docker-compose.yml](docker-compose.yml) — Container orchestration
- [nginx.conf](nginx.conf) — SSL termination and WebSocket proxying

## HTTPS Support

The nginx SSL proxy terminates TLS and forwards to MCPX. Requires certs at `./certs/tls/{cert,key}.pem`.

```bash
# Generate self-signed certs for testing
mkdir -p certs/tls
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/tls/key.pem -out certs/tls/cert.pem \
  -subj "/CN=localhost"
```

## TODO

- [ ] Configure authentication (API key or OAuth)
- [ ] Test disconnection-safe caching with OpenCode
- [ ] Set up consumer tags for per-client metrics
- [ ] Compare to Atrax and MetaMCP as alternatives
