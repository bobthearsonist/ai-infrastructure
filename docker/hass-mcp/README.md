# Home Assistant MCP Server

Docker configuration for running the Home Assistant MCP (Model Context Protocol) Server.

## Usage

```bash
docker-compose up -d
```

## Configuration

The MCP server is configured through environment variables in the `.env` file:

- **HA_URL**: Home Assistant base URL
- **HA_TOKEN**: Long-lived access token from Home Assistant
- **AUTO_APPROVE**: Enable/disable automatic approval of operations

## Docker Image

This configuration uses the official image: `voska/hass-mcp:latest`

For more information about the MCP server, visit: https://github.com/voska/hass-mcp
