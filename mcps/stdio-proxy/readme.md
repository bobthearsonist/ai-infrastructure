# stdio-proxy

Runs multiple stdio-based MCP servers as SSE endpoints using [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy).

## Status

✅ **Running** - Serving 3 MCP servers.

## Servers

| Server | Tools | Endpoint |
|--------|-------|----------|
| sequential-thinking | 1 | `/servers/sequential-thinking/sse` |
| memory | 8 | `/servers/memory/sse` |
| kapture | 15+ | `/servers/kapture/sse` |

## Endpoints

The stdio-proxy exposes each MCP server at a unique SSE endpoint:

| MCP | URL |
|-----|-----|
| sequential-thinking | `http://localhost:7030/servers/sequential-thinking/sse` |
| memory | `http://localhost:7030/servers/memory/sse` |
| kapture | `http://localhost:7030/servers/kapture/sse` |

### Special Ports

| Port | Purpose |
|------|--------|
| 61822 | Kapture WebSocket bridge (Chrome extension connects here) |

These endpoints are consumed by agentgateway, which aggregates them into a single MCP interface.

## Usage

```bash
docker-compose up -d
```

## Adding a New stdio MCP

1. **Add to `servers.json`**:

   ```json
   {
     "mcpServers": {
       "new-mcp": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-new-mcp"]
       }
     }
   }
   ```

2. **Rebuild the container**:

   ```bash
   docker-compose up -d --build
   ```

3. **Add to agentgateway** (`gateways/agentgateway/config.yaml`):

   ```yaml
   - name: new-mcp
     sse:
       host: http://host.docker.internal:7030/servers/new-mcp/sse
   ```

4. **Restart agentgateway**:

   ```bash
   cd ../../gateways/agentgateway
   docker-compose restart agentgateway
   ```

## Configuration

### servers.json

The `servers.json` file defines which MCP servers to run:

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "kapture": {
      "command": "npx",
      "args": ["-y", "kapture-mcp", "bridge"],
      "env": {
        "KAPTURE_BRIDGE_PORT": "61822"
      }
    }
  }
}
```

### Port

The container exposes port `7030` for SSE connections.

## Why mcp-proxy over supergateway?

| | [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) | [supergateway](https://github.com/supercorp-ai/supergateway) |
|---|------------|--------------|
| Multi-server | ✅ Single config file, single port | ❌ Separate process per server |
| Routing | `/servers/{name}/sse` | Multiple ports |
| Consistency | Already used in browser-use, hass-mcp | New dependency |

Both are excellent. We chose mcp-proxy for JSON config simplicity and project consistency.

## Related

- [sequential-thinking](../sequential-thinking/readme.md) - Chain of thought reasoning MCP
- [memory](../memory/readme.md) - Knowledge graph MCP
- [agentgateway](../../gateways/agentgateway/readme.md) - Consumes stdio-proxy endpoints
