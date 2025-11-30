# stdio-proxy

Runs multiple stdio-based MCP servers as SSE endpoints using [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy).

## Servers

This container aggregates:

| Server | Source Folder | Endpoint |
|--------|---------------|----------|
| sequential-thinking | `../sequential-thinking/` | `/servers/sequential-thinking/sse` |
| memory | `../memory/` | `/servers/memory/sse` |

## Usage

```bash
docker-compose up -d
```

## Why mcp-proxy over supergateway?

| | [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) | [supergateway](https://github.com/supercorp-ai/supergateway) |
|---|------------|--------------|
| Multi-server | ✅ Single config file, single port | ❌ Separate process per server |
| Routing | `/servers/{name}/sse` | Multiple ports |
| Consistency | Already used in browser-use, hass-mcp | New dependency |

Both are excellent. We chose mcp-proxy for JSON config simplicity and project consistency.
