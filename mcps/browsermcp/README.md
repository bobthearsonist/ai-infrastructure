# BrowserMCP

BrowserMCP integration for the mcpx gateway system. This allows AI applications to automate browser tasks using your existing browser profile.

## Overview

BrowserMCP is an MCP server + Chrome extension that allows you to automate your browser using AI applications. It runs as a Docker container and connects to mcpx through SSE (Server-Sent Events).

## Features

- ⚡ **Fast**: Automation happens locally on your machine
- 🔒 **Private**: Browser activity stays on your device
- 👤 **Logged In**: Uses your existing browser profile
- 🥷🏼 **Stealth**: Avoids basic bot detection and CAPTCHAs

## Setup

### 1. Start the BrowserMCP Container

```bash
cd ./mcps/browsermcp
docker-compose up -d
```

### 2. Install Browser Extension

1. Visit the [Chrome Web Store](https://chrome.google.com/webstore) and search for "Browser MCP"
2. Install the Browser MCP extension
3. Click the extension icon in your browser toolbar
4. Click "Connect" to establish connection with the MCP server

### 3. Verify Setup

1. Check that the container is running:

   ```bash
   docker-compose ps
   ```

2. Check mcpx dashboard at [http://localhost:5173/dashboard](http://localhost:5173/dashboard) to see if BrowserMCP appears in the available servers

3. Test a browser automation command through your AI client

## Available Tools

BrowserMCP provides the following automation tools:

- **navigate**: Navigate to a URL
- **click**: Click on elements
- **type**: Type text into input fields
- **hover**: Hover over elements
- **screenshot**: Take page screenshots
- **snapshot**: Capture page structure
- **goBack**: Navigate back in browser history
- **goForward**: Navigate forward in browser history
- **selectOption**: Select options from dropdowns
- **pressKey**: Press keyboard keys
- **wait**: Wait for specified time
- **getConsoleLogs**: Get browser console logs

## Configuration

The service is configured to:

- Run on port 7009
- Connect to the mcpx network
- Auto-restart on failure
- Use the latest published @browsermcp/mcp package

## Troubleshooting

### Container Issues

```bash
# View logs
docker-compose logs browsermcp

# Restart container
docker-compose restart browsermcp

# Rebuild and restart
docker-compose down && docker-compose up -d
```

### Browser Extension Issues

1. Ensure the extension is properly installed and enabled
2. Click the extension icon and verify connection status
3. Check that no firewall is blocking port 7009
4. Try refreshing the browser tab and reconnecting

### Network Issues

- Verify the ai-infrastructure network exists: `docker network ls`
- Check port 7009 is not already in use: `lsof -i :7009`

## Integration with mcpx

BrowserMCP is automatically registered with mcpx through the configuration in:

```
./mcps/mcpx/mcp.json
```

The service connects via SSE at: `http://browsermcp:7009/sse`

## Security Notes

- BrowserMCP runs in a containerized environment
- Browser automation uses your existing profile and sessions
- No browser data is sent to external servers
- All automation happens locally

## Resources

- [Browser MCP Documentation](https://docs.browsermcp.io/)
- [Browser MCP Website](https://browsermcp.io/)
- [GitHub Repository](https://github.com/BrowserMCP/mcp)
