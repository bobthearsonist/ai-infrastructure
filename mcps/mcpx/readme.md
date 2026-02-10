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
| browser | kapture, playwright, browser-use | Browser automation |
| home | hass-mcp | Home Assistant |
| creative | photoshop | Adobe Photoshop |

## Prerequisites

- SSE-based MCPs (playwright, browser-use, hass-mcp, context7) must be running on the host
- stdio-proxy must be running on port 7030 for photoshop
- SSL certs in `./certs/tls/` for HTTPS (optional)

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
