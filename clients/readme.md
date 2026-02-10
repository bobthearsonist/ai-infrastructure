# Client Configuration

Configuration for connecting AI clients to the MCP infrastructure.

## Setup

Create symlinks from this directory to your actual client config files:

```bash
# VS Code Copilot
ln -s ~/Library/Application\ Support/Code/User/mcp.json copilot/vscode-user.json

# IntelliJ Copilot
ln -s ~/.config/github-copilot/intellij/mcp.json copilot/intellij.mcp

# Claude Desktop
ln -s ~/Library/Application\ Support/Claude/claude_desktop_config.json claude/claude_desktop_config.json

# Claude Code
ln -s ~/.claude.json claude/claude_code_config.json
ln -s ~/.claude claude/.claude

# Claude Code User Instructions, Agents, and Skills
ln -s ~/Repositories/ai/AGENTS.md ~/.claude/claude.md
ln -s ~/Repositories/ai/agents ~/.claude/agents
ln -s ~/Repositories/ai/skills ~/.claude/skills

# Cline
ln -s ~/Library/Application\ Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json cline/mcp_settings.json

# Kilo Code (fork of Cline)
ln -s ~/Library/Application\ Support/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json kilocode/mcp_settings.json

# Goose
ln -s ~/.config/goose/config.yaml goose/config.yaml
```

## Connection Details

**Endpoint:** `http://localhost:3847/mcp` (or `https://localhost:3443/mcp` for SSL)

All clients use `mcp-remote` to bridge stdio→HTTP:

```json
"command": "/bin/bash",
"args": [
  "-c",
  "source ~/.nvm/nvm.sh && nvm use 20.11.1 >/dev/null 2>&1 && npx mcp-remote@latest http://localhost:3847/mcp --header 'x-client-id: your-client-name'"
]
```

### Client Identification

Each client should include an `x-client-id` header for tracking in metrics and traces:

| Client          | Header Value                  |
| --------------- | ----------------------------- |
| VS Code Copilot | `x-client-id: vscode-copilot` |
| Claude Desktop  | `x-client-id: claude-desktop` |
| Cline           | `x-client-id: cline`          |
| Kilo Code       | `x-client-id: kilocode`       |
| Goose           | `x-client-id: goose`          |

### Why nvm?

`mcp-remote` requires Node.js 20+. Since system Node versions vary, we use nvm to guarantee the correct version. The `>/dev/null 2>&1` suppresses nvm output that would interfere with the MCP protocol.

## Claude Code User Instructions, Agents, and Skills

Claude Code reads several user-level configuration paths:

| Path | Purpose |
| ---- | ------- |
| `~/.claude/claude.md` | Global instructions for all sessions |
| `~/.claude/agents/` | Custom agent definitions |
| `~/.claude/skills/` | Personal skills (slash commands) available across all projects |

All are symlinked to the centralized ai repository:

```bash
~/.claude/claude.md → ~/Repositories/ai/AGENTS.md
~/.claude/agents    → ~/Repositories/ai/agents
~/.claude/skills    → ~/Repositories/ai/skills
```

This allows:

- **Single source of truth** for instructions, agents, and skills across all Claude Code sessions
- **Version controlled** configuration via the ai repository
- **Shared patterns** for memory, todo management, sequential thinking, and skill promotion
