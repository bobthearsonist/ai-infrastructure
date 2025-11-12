# Home Assistant MCP Server

Docker configuration for running the Home Assistant MCP (Model Context Protocol) Server.

it has to be run with a proxy sidecar to bridge stdio to sse

## Usage

```bash
docker-compose up -d
```

## Configuration

The MCP server is configured through environment variables in the `.env` file:

- **HA_URL**: Home Assistant base URL
- **HA_TOKEN**: Long-lived access token from Home Assistant
- **AUTO_APPROVE**: Enable/disable automatic approval of operations

## Docker Images

This configuration uses the official hass mcp image: `voska/hass-mcp:latest`
For more information about the MCP server, visit: https://github.com/voska/hass-mcp

This configuration also uses the official mcp proxy image: `ghcr.io/sparfenyuk/mcp-proxy:latest`
For more information about the MCP proxy, visit: https://github.com/sparfenyuk/mcp-proxy
