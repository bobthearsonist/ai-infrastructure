# Client Configuration

Configuration for connecting AI clients to the MCP infrastructure.

## MCP Config File Locations

Where each client stores its MCP server configuration.

| Client | Windows | macOS |
|--------|---------|-------|
| VS Code / Copilot | `%APPDATA%\Code\User\mcp.json` | `~/Library/Application Support/Code/User/mcp.json` |
| VS Code Insiders | `%APPDATA%\Code - Insiders\User\mcp.json` | `~/Library/Application Support/Code - Insiders/User/mcp.json` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Code | `~/.claude/.mcp.json` + `~/.claude/settings.local.json` | same |
| OpenCode | `~/.config/opencode/opencode.json` or project `opencode.json` | same |
| Cline (VS Code) | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` | `~/Library/Application Support/Code/User/globalStorage/...` |
| Cline (Standalone) | `~/.cline/data/settings/cline_mcp_settings.json` | same |
| Kilo Code | `%APPDATA%\Code\User\globalStorage\kilocode.kilo-code\settings\mcp_settings.json` | `~/Library/Application Support/Code/User/globalStorage/...` |
| Goose | `~/.config/goose/config.yaml` | same |

## Connection Patterns

There are two ways clients connect to MCP servers:

### 1. Via gateway (centralized)

All MCPs behind a single endpoint with auth, RBAC, and metrics. Either [agentgateway](../gateways/agentgateway/readme.md) or [mcpx](../mcps/mcpx/) can serve as the gateway.

**Endpoint:** `http://localhost:3847/mcp` (or `https://localhost:3443/mcp` for TLS)

Clients use `mcp-remote` to bridge stdio to HTTP:

```json
{
  "command": "npx",
  "args": ["--prefer-online", "-y", "mcp-remote", "http://localhost:3847/mcp", "--header", "x-client-id: your-client-name"]
}
```

> **Note:** Claude Desktop on Windows requires `npx.cmd` instead of `npx`.

### 2. Direct SSE (per-MCP)

Clients connect directly to individual MCP SSE endpoints. Used for MCPs that expose their own SSE server (e.g., qdrant-mcp on `:7020`).

```json
{
  "command": "npx",
  "args": ["--prefer-online", "-y", "mcp-remote", "http://localhost:7020/servers/qdrant-work/sse"]
}
```

OpenCode supports SSE natively without `mcp-remote`:

```json
{
  "type": "remote",
  "url": "http://localhost:7020/servers/qdrant-work/sse",
  "enabled": true
}
```

### Client Identification

When using agentgateway, include an `x-client-id` header for tracking:

| Client | Header Value |
|--------|-------------|
| VS Code Copilot | `x-client-id: vscode-copilot` |
| Claude Desktop | `x-client-id: claude-desktop` |
| OpenCode | `x-client-id: opencode` |
| Cline | `x-client-id: cline` |
| Kilo Code | `x-client-id: kilocode` |
| Goose | `x-client-id: goose` |

## Symlinks

Symlink client config files into this directory for version control. Use `ln -s` (macOS/Linux) or `mklink` (Windows, elevated).

| Source (actual config) | Target (this repo) |
|------------------------|--------------------|
| `{APPDATA}/Code/User/mcp.json` | `copilot/vscode-user.json` |
| `{APPDATA}/Claude/claude_desktop_config.json` | `claude/claude_desktop_config.json` |
| `{APPDATA}/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | `cline/mcp_settings.json` |
| `{APPDATA}/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json` | `kilocode/mcp_settings.json` |
| `~/.config/goose/config.yaml` | `goose/config.yaml` |

`{APPDATA}` = `%APPDATA%` on Windows, `~/Library/Application Support` on macOS.

## User Instructions, Agents, and Skills

Shared across Claude Code, OpenCode, and GitHub Copilot via symlinks from a centralized ai repository:

| Source (canonical) | Target | Used by |
|--------------------|--------|---------|
| `~/ai/AGENTS.md` | `~/.claude/CLAUDE.md` | Claude Code |
| `~/ai/agents/` | `~/.claude/agents/` | Claude Code |
| `~/ai/skills/` | `~/.claude/skills/` | Claude Code, OpenCode |
| `~/ai/skills/` | `~/.copilot/skills/` | GitHub Copilot |
| `~/ai/agents/opencode/` | `~/.config/opencode/agent/` | OpenCode |

This allows:

- **Single source of truth** for instructions, agents, and skills across all sessions
- **Version controlled** configuration via the ai repository
- **Shared patterns** for memory, todo management, sequential thinking, and skill promotion
