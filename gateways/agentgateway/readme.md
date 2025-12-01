# agentgateway

agentgateway is an open-source MCP gateway/proxy from the Linux Foundation. It serves as a central entrypoint for multiple MCP servers, routing requests to appropriate backends.

- 📖 **Docs**: <https://agentgateway.dev/docs/>
- 🔗 **GitHub**: <https://github.com/agentgateway/agentgateway>
- 🏗️ **Architecture**: See [root README](../../README.md)

## Current Status

✅ **Working** - Serving 24+ tools from 3 MCP backends.

## Ports

| Port  | Protocol   | Description              |
| ----- | ---------- | ------------------------ |
| 3847  | HTTP       | MCP endpoint             |
| 15001 | HTTP       | Admin UI Dashboard       |
| 15020 | Prometheus | Metrics endpoint         |
| 3443  | HTTPS      | MCP endpoint (via nginx) |

## Configured Backends

| MCP Server | Status | Transport | Source | Docs |
| ---------- | ------ | --------- | ------ | ---- |
| sequential-thinking | ✅ Running | SSE | [stdio-proxy](../../mcps/stdio-proxy/readme.md) | [→](../../mcps/sequential-thinking/readme.md) |
| memory | ✅ Running | SSE | [stdio-proxy](../../mcps/stdio-proxy/readme.md) | [→](../../mcps/memory/readme.md) |
| kapture | ✅ Running | SSE + WebSocket | [stdio-proxy](../../mcps/stdio-proxy/readme.md) | [→](../../mcps/kapture/readme.md) |
| context7 | ✅ Running | SSE | container | [→](../../mcps/context7/readme.md) |
| playwright | ✅ Running | SSE | container | [→](../../mcps/playwright/readme.md) |
| browser-use | ✅ Running | SSE | container | [→](../../mcps/browser-use/readme.md) |
| hass-mcp | ✅ Running | SSE | container | [→](../../mcps/hass-mcp/readme.md) |
| langfuse-mcp | ⏳ Planned | SSE | container | [→](../../services/langfuse/readme.md) |

## Setup

### Prerequisites

1. Create the shared Docker network:

   ```bash
   docker network create mcpx_ai-infrastructure
   ```

2. Start stdio-proxy (required for sequential-thinking and memory):

   ```bash
   cd ../../mcps/stdio-proxy
   docker-compose up -d
   ```

### Run

```bash
docker-compose up -d
```

### Access

- **Admin UI**: `http://localhost:15001/ui`
- **MCP Endpoint**: `http://localhost:3847/mcp`

## Configuration

### config.yaml

The `config.yaml` file defines which MCP backends to connect to:

```yaml
version: v1
listeners:
  - name: mcp-listener
    protocol: MCP
    address: 0.0.0.0:3847

backends:
  mcp:
    targets:
      - name: sequential-thinking
        sse:
          host: http://host.docker.internal:7030/servers/sequential-thinking/sse
      - name: memory
        sse:
          host: http://host.docker.internal:7030/servers/memory/sse
```

### Adding a New Backend

1. **SSE-based MCP** - Add directly to `config.yaml`:

   ```yaml
   - name: new-mcp
     sse:
       host: http://host.docker.internal:PORT/sse
   ```

2. **stdio-based MCP** - Add to [stdio-proxy](../../mcps/stdio-proxy/readme.md) first, then reference it here.

3. **Restart**:

   ```bash
   docker-compose restart agentgateway
   ```

### DNS Notes

Use `host.docker.internal:PORT` for backend URLs. Container-to-container DNS doesn't work reliably with agentgateway's Go resolver.

## Features

agentgateway provides enterprise features not available in simpler gateways:

| Feature | Description |
| ------- | ----------- |
| **Authentication** | JWT, OAuth2 support |
| **Authorization** | CEL-based RBAC policies |
| **Rate Limiting** | Per-client rate limits |
| **Native TLS** | Built-in SSL/TLS |
| **OpenAPI → MCP** | Convert OpenAPI specs to MCP |
| **A2A Protocol** | Agent-to-agent communication |
| **Hot Reload** | Config updates via xDS |

## Comparison to MCPX

| Feature | MCPX | agentgateway |
| ------- | ---- | ------------ |
| MCP Gateway | ✅ | ✅ |
| Authentication | ❌ | ✅ |
| Authorization/RBAC | ❌ | ✅ |
| Native TLS | ❌ | ✅ |
| Rate Limiting | ❌ | ✅ |
| Hot Reload | ❌ | ✅ |

## Docker Compose

This setup runs two containers:

| Container | Image | Purpose |
| --------- | ----- | ------- |
| agentgateway | `ghcr.io/agentgateway/agentgateway` | MCP gateway (Linux Foundation) |
| nginx-proxy | `nginx:alpine` | SSL termination, CDP proxy |

### nginx-proxy

The nginx-proxy is our custom addition (not part of agentgateway) that provides:

| Port | Purpose | Direction |
|------|---------|-----------|
| 3443 | HTTPS MCP endpoint | Clients → agentgateway |
| 15443 | HTTPS Admin UI | Browser → agentgateway |
| 9223 | CDP proxy | Containers → host Chrome:9222 |

**Why CDP proxy?** Playwright and browser-use MCPs run inside Docker containers but need to control Chrome running on the host. Containers can't reach `localhost:9222` directly, so nginx proxies `host.docker.internal:9223` → `host:9222`.

> **Note:** Kapture doesn't use this proxy. The Chrome extension (running on host) connects directly to stdio-proxy:61822. The connection direction is reversed - host→container instead of container→host.

## Troubleshooting

### DNS Resolution Failed

If you see "backends required DNS resolution which failed":

1. Use `host.docker.internal:PORT` for backend URLs
2. Ensure docker-compose.yml has `dns: - 127.0.0.11`

### prompts/list 500 Error

Expected - some MCP backends don't implement prompts. Doesn't affect tool discovery.

### Slow Initial Response

First request takes ~4 seconds as agentgateway queries all backends. Subsequent requests are faster.

## TODO

- [ ] Configure authentication (JWT/OAuth2)
- [ ] Set up RBAC policies
- [ ] Configure rate limiting
- [ ] Set up xDS for hot-reload
- [ ] Restrict sequential-thinking MCP to local models only (hosted models/agents like Cline and GitHub Copilot provide similar chain-of-thought functionality in the client)

## Related

- [Client Configuration](../../clients/) - Configure AI clients to connect
- [stdio-proxy](../../mcps/stdio-proxy/readme.md) - stdio→SSE bridge for MCPs
- [Langfuse](../../services/langfuse/readme.md) - LLM observability platform (planned)
