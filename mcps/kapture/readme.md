# Kapture MCP Setup

> **TODO**: Migrate to agentgateway setup. Currently documented for MCPX.
> Kapture requires special handling due to WebSocket requirements for Chrome extension.

Kapture is a Chrome DevTools Extension that enables browser automation through the Model Context Protocol (MCP). This setup runs Kapture within the MCPX Docker infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (Chrome)                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │            Kapture Chrome Extension                          │  │
│  │            (DevTools Panel)                                  │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
└────────────────────────────────┼────────────────────────────────────┘
                                 │ WebSocket
                                 │ ws://localhost:61822
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Docker Infrastructure                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  nginx-ssl container                                         │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │  localhost:61822 (nginx proxy)                         │  │  │
│  │  │  Proxies WebSocket → mcpx:61822                        │  │  │
│  │  └──────────────────┬─────────────────────────────────────┘  │  │
│  └─────────────────────┼────────────────────────────────────────┘  │
│                        │                                            │
│  ┌─────────────────────▼────────────────────────────────────────┐  │
│  │  mcpx container                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │  Kapture MCP Server (port 61822)                       │  │  │
│  │  │  - Handles WebSocket connections from extension        │  │  │
│  │  │  - Executes browser automation commands                │  │  │
│  │  └──────────────────┬─────────────────────────────────────┘  │  │
│  │  ┌─────────────────▼──────────────────────────────────────┐  │  │
│  │  │  MCPX Gateway                                          │  │  │
│  │  │  - Aggregates multiple MCP servers                     │  │  │
│  │  │  - Exposes unified MCP interface                       │  │  │
│  │  └──────────────────┬─────────────────────────────────────┘  │  │
│  └─────────────────────┼────────────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────────────┘
                         │ HTTP/SSE
                         │ http://localhost:9000/mcp
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MCP Client (Cline/VS Code)                       │
│  - Connects to MCPX via mcp-remote                                 │
│  - Uses Kapture tools for browser automation                       │
└─────────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Chrome Extension

- Install Kapture extension from Chrome Web Store
- Open Chrome DevTools (F12 or Cmd+Option+I)
- Navigate to "Kapture" panel
- Extension automatically connects to `localhost:61822`

### 2. WebSocket Proxy (nginx)

- nginx-ssl container listens on `localhost:61822`
- Proxies WebSocket connections to Kapture server in mcpx container
- Handles CORS and connection upgrades

### 3. Kapture MCP Server (Docker)

- Runs inside mcpx container via `npx kapture-mcp bridge`
- Listens on port 61822 for WebSocket connections from extension
- Translates MCP protocol commands to browser automation actions
- Configured in `mcps/mcpx/mcp.json`

### 4. MCPX Gateway

- Aggregates Kapture with other MCP servers
- Exposes unified interface at `http://localhost:9000/mcp`
- Routes commands to appropriate MCP server

### 5. MCP Client (Cline)

- Connects to MCPX via `mcp-remote`
- Uses Kapture tools: `navigate`, `click`, `fill`, `screenshot`, etc.
- Commands flow through entire stack to control Chrome browser

## Configuration Files

### docker-compose.yml

```yaml
nginx-ssl:
  ports:
    - '61822:61822' # Kapture WebSocket server port
```

### nginx.conf

```nginx
# WebSocket server for Kapture MCP
server {
    listen 61822;
    server_name localhost;

    location / {
        proxy_pass http://mcpx:61822;
        proxy_http_version 1.1;

        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Prevent timeouts
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_connect_timeout 3600s;
    }
}
```

### mcp.json

```json
{
  "mcpServers": {
    "kapture": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "kapture-mcp", "bridge"]
    }
  }
}
```

## Available Tools

- `kapture__list_tabs` - List all connected browser tabs
- `kapture__navigate` - Navigate to URL
- `kapture__click` - Click elements
- `kapture__fill` - Fill input fields
- `kapture__screenshot` - Capture screenshots
- `kapture__dom` - Get page HTML
- `kapture__elements` - Query elements
- `kapture__console_logs` - Get console output
- And many more...

## Benefits of This Setup

1. **Containerized**: Kapture server runs in Docker for consistency
2. **Centralized**: Single MCPX gateway for all MCP servers
3. **Secure**: Localhost-only connections, no external exposure
4. **Scalable**: Multiple AI clients can connect to same MCPX gateway
5. **Isolated**: Browser automation isolated from development environment

## Installation

1. Ensure Docker services are running:

   ```bash
   cd mcps/mcpx
   docker-compose up -d
   ```

2. Install Kapture Chrome extension:

   - Visit: https://chromewebstore.google.com/detail/kapture/aeojbjkdienbkmfdhdllobehhcklhecp
   - Click "Add to Chrome"

3. Open Chrome DevTools and navigate to "Kapture" panel

4. Use Kapture tools through your MCP client (Cline, Claude Desktop, etc.)

## Troubleshooting

- **Extension won't connect**: Verify nginx is listening on port 61822 with `lsof -i :61822`
- **Port conflict**: Stop any other services using port 61822
- **WebSocket errors**: Check nginx logs: `docker logs mcpx-ssl-proxy`
- **Server not responding**: Verify Kapture is running in mcpx: `docker exec mcpx ps aux | grep kapture`
