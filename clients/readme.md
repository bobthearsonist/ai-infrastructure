# Client Configuration

Configuration for connecting AI clients to the MCP infrastructure.

## Shared Workspace Hooks

The [graphify hook bundle](graphify-hooks/.claude/hooks/README.md) contains
portable Claude Code and Copilot CLI reminders, deployment instructions, and a
deterministic regression suite. These are workspace settings, not plugin hooks;
updating them does not require a plugin version bump.

## MCP Config File Locations

Where each client stores its MCP server configuration.

| Client | Windows | macOS |
|--------|---------|-------|
| VS Code / Copilot | `%APPDATA%\Code\User\mcp.json` | `~/Library/Application Support/Code/User/mcp.json` |
| VS Code Insiders | `%APPDATA%\Code - Insiders\User\mcp.json` | `~/Library/Application Support/Code - Insiders/User/mcp.json` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Code | `~/.claude.json` (user scope, root `mcpServers`) or project `.mcp.json` | same |
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

#### Claude Code (native HTTP)

Claude Code speaks streamable HTTP natively, so it connects to [mcpx](../mcps/mcpx/readme.md) without the `mcp-remote` bridge. User-scope entry in `~/.claude.json`:

```json
"mcpx": {
  "type": "http",
  "url": "http://127.0.0.1:9000/mcp",
  "headers": { "x-lunar-consumer-tag": "claude-code" }
}
```

Or from the CLI:

```bash
claude mcp add -t http -s user mcpx http://127.0.0.1:9000/mcp -H "x-lunar-consumer-tag: claude-code"
```

Use `127.0.0.1`, not `localhost`: on Windows with WSL, `localhost` resolves to `::1` first, where `wslrelay` holds the port and resets the connection.

Remote HTTPS MCP servers (e.g. a local Profisee instance's `https://<host>/<instance>/mcp/` endpoint, authenticated with an `x-api-key` header) use the same `type: http` shape. Claude Code validates TLS against the Windows certificate store as well as its bundled CAs (`CLAUDE_CODE_CERT_STORE` defaults to `bundled,system`), so a self-signed IIS certificate that Windows trusts needs no `NODE_TLS_REJECT_UNAUTHORIZED=0`.

#### Goose (native HTTP)

Goose's `streamable_http` extension type sends custom headers and expands `${VAR}` in header values from `env_keys`, resolved from the environment first and then Goose's keychain secret store. Entry in `~/.config/goose/config.yaml`:

```yaml
mcpx:
  enabled: true
  type: streamable_http
  name: mcpx
  uri: http://127.0.0.1:9000/mcp
  headers:
    x-lunar-consumer-tag: goose
    x-lunar-api-key: ${MCPX_API_KEY}
  envs: {}
  env_keys:
  - MCPX_API_KEY
  timeout: 600
```

Store the key once in Goose Desktop (Extensions > mcpx > Edit, environment variable `MCPX_API_KEY`) or through `goose configure`. Goose 1.61 has no non-interactive `set-secret` command. Apps launched from the Dock do not see shell environment variables, so the keychain entry is what Goose Desktop uses.

Quit Goose Desktop before editing `config.yaml` by hand: it writes its in-memory extension list back on save and overwrites hand edits.

#### Claude Desktop (stdio bridge)

`claude_desktop_config.json` only starts local commands; it skips any entry with a URL and no command, and remote Connectors run from Anthropic's servers, which cannot reach `127.0.0.1`. Claude Desktop therefore reaches mcpx through [`claude-desktop/mcpx-bridge`](claude-desktop/mcpx-bridge), which runs a pinned `mcp-remote` with the key in a header file:

```bash
ln -s ~/Repositories/ai-infrastructure/clients/claude-desktop/mcpx-bridge ~/.local/bin/mcpx-bridge
```

```json
"mcpx": {
  "command": "/Users/<you>/.local/bin/mcpx-bridge",
  "args": ["claude-desktop"]
}
```

The bridge reads `AUTH_KEY` from `mcps/mcpx/secrets/mcpx-auth.env`, writes it to `~/.config/mcpx/mcpx-auth.headers` (mode 0600) and passes that file with `--header-file`. Never pass the key with `--header`: process arguments are readable by every local user through `ps`, and `mcp-remote` does not expand `${VAR}` in `--header` values.

`mcp-remote` gives up after two reconnect attempts, so after an mcpx restart Claude Desktop has no mcpx tools until it is quit and reopened.

#### Rotating the mcpx key

The key has copies in `mcps/mcpx/secrets/mcpx-auth.env` (read by mcpx, nginx and the bridge), `~/.claude.json`, `~/.copilot/mcp-config.json`, Goose's keychain entry and Keeper. After changing the env file, recreate the containers; `docker compose restart` keeps the old `env_file` values:

```bash
docker compose -f mcps/mcpx/docker-compose.yml up -d --force-recreate --no-deps mcpx nginx-ssl
```

Then reconnect every client (`/mcp` in Claude Code, a full quit and reopen of Claude Desktop).

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

## LLM Proxy (Context Lens)

[Context Lens](../platform/context-lens/README.md) intercepts LLM API traffic for context window analysis. Clients that call the Anthropic API directly (Claude Code) are routed through the proxy via `ANTHROPIC_BASE_URL`. Clients using gateway providers (OpenCode via `github-copilot/`) are unaffected.

See the [Context Lens README](../platform/context-lens/README.md#client-configuration) for setup and troubleshooting.

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
