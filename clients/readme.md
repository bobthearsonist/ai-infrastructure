# Client Configuration

Configuration for connecting AI clients to the MCP infrastructure.

## Connection Details

**Endpoint:** `http://localhost:3847/mcp` (or `https://localhost:3443/mcp` for SSL)

All clients use `mcp-remote` to bridge stdio→HTTP:

```json
"command": "/bin/bash",
"args": [
  "-c",
  "source ~/.nvm/nvm.sh && nvm use 20.11.1 >/dev/null 2>&1 && npx mcp-remote@latest http://localhost:3847/mcp"
]
```

### Why nvm?

`mcp-remote` requires Node.js 20+. Since system Node versions vary, we use nvm to guarantee the correct version. The `>/dev/null 2>&1` suppresses nvm output that would interfere with the MCP protocol.

## Config Files

| Client | Config File |
| ------ | ----------- |
| VS Code Copilot | [copilot/vscode-user.json](copilot/vscode-user.json) |
| Claude Desktop | [claude/claude_desktop_config.json](claude/claude_desktop_config.json) |
| Cline | [cline/mcp_settings.json](cline/mcp_settings.json) |
