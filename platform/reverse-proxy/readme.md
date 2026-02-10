# AI Infrastructure Reverse Proxy

Central nginx reverse proxy for hostname-based routing to all AI infrastructure services.

## Hostnames

> **Note:** Uses `.localhost` TLD (RFC 6761 reserved, always resolves to 127.0.0.1). Avoids `.local` which macOS reserves for mDNS/Bonjour.

| URL | Service | Backend |
|-----|---------|----------|
| http://mcpx.localhost | MCPX Dashboard | :5173 |
| http://mcpx.localhost/sse | MCPX SSE endpoint | :9000 |
| http://mcpx.localhost/mcp | MCPX MCP endpoint | :9000 |
| http://agentgateway.localhost | Agent Gateway Admin UI | :15001 |
| http://agentgateway.localhost/mcp | Agent Gateway MCP API | :3847 |
| http://grafana.localhost | Grafana | :3000 |
| http://jaeger.localhost | Jaeger UI | :16686 |
| http://prometheus.localhost | Prometheus | :9090 |

## Prerequisites

Hostnames must be in `/etc/hosts`:

```
127.0.0.1 mcpx.localhost
127.0.0.1 agentgateway.localhost
127.0.0.1 grafana.localhost
127.0.0.1 jaeger.localhost
127.0.0.1 prometheus.localhost
```

## Usage

```bash
docker compose up -d
```

## Adding a new service

1. Add a `server` block to [nginx.conf](nginx.conf)
2. Add the hostname to `/etc/hosts`
3. Restart: `docker compose restart`
