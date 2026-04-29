# Context Lens

Local reverse proxy that intercepts LLM API calls from coding agents and visualizes context window composition.

- **Repo**: [github.com/larsderidder/context-lens](https://github.com/larsderidder/context-lens)
- **Proxy**: `http://localhost:4040`
- **Web UI**: `http://localhost:4041`
- **Data**: `~/.context-lens/data/*.lhar`

## Architecture

The Docker Compose stack runs two services:

- **context-lens** -- the proxy (4040) and web UI (4041), installed from npm at startup.
- **mitmproxy** -- a forward proxy (8080) that intercepts HTTPS traffic from tools that can't set a custom base URL (VS Code Copilot, Codex, etc.) and forwards captures to the ingest API.

### Quick start

```bash
docker compose up -d
# Open http://localhost:4041
```

### Ports

| Port | Service         | Notes                                        |
| ---- | --------------- | -------------------------------------------- |
| 4040 | Proxy           | `ANTHROPIC_BASE_URL` override for Claude Code |
| 4041 | Web UI / API    | Analysis dashboard and ingest endpoint        |
| 8080 | mitmproxy       | HTTPS forward proxy for Copilot, Codex, etc. |

### Environment (`.env`)

Copy `.env.example` and edit as needed:

```bash
cp .env.example .env
```

| Variable              | Default                  | Description                                     |
| --------------------- | ------------------------ | ----------------------------------------------- |
| `CONTEXT_LENS_DATA`   | `~/.context-lens/data`   | Host path for session data (mounted into container) |
| `MITMPROXY_CERTS`     | `~/.mitmproxy`           | Host path to mitmproxy CA certs                 |

### Stopping

```bash
docker compose down
```

## Development (hot-reload from source)

The dev overlay mounts your local context-lens source into the container so changes rebuild and reload automatically.

### Prerequisites

- A local clone or worktree of the [context-lens repo](https://github.com/larsderidder/context-lens)
- Docker and Docker Compose

### Setup

```bash
# Copy the dev env template
cp .env.dev.example .env

# Edit .env — set CONTEXT_LENS_SRC to your source checkout
# CONTEXT_LENS_SRC=/c/Repositories/context-lens
```

### Start dev mode

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This runs three processes inside the container via `concurrently`:

| Process   | What it does                           |
| --------- | -------------------------------------- |
| `tsc`     | TypeScript watch compiler              |
| `nodemon` | Auto-restarts the server on `dist/` changes |
| `vite`    | UI dev server with hot-reload          |

### Dev ports

| Port | Service         | Notes                            |
| ---- | --------------- | -------------------------------- |
| 4040 | Proxy           | LLM API interception             |
| 4041 | Analysis API    | Auto-restart on backend changes  |
| 5173 | Vite dev server | UI hot-reload (dev mode only)    |

In dev mode, open `http://localhost:5173` for the UI (Vite serves it with HMR). The API on 4041 still works but the UI there won't hot-reload.

### Switching worktrees

Update `CONTEXT_LENS_SRC` in `.env` to point at a different worktree, then restart:

```bash
# .env
CONTEXT_LENS_SRC=/c/Repositories/context-lens.worktrees/feat/show-session-label
```

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Client Configuration

### Setting ANTHROPIC_BASE_URL

The `ANTHROPIC_BASE_URL` environment variable redirects Anthropic API calls through the Context Lens proxy. Set it wherever your AI client inherits environment from.

**Shell profile (macOS / Linux / WSL)**

Add to `~/.bashrc`, `~/.zshrc`, or equivalent:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:4040/claude"
```

**Windows user environment variable**

```cmd
setx ANTHROPIC_BASE_URL "http://127.0.0.1:4040/claude"
```

Restart your terminal after running `setx`.

**VS Code settings (all platforms)**

Add to your VS Code `settings.json`:

```jsonc
"claudeCode.environmentVariables": {
    "ANTHROPIC_BASE_URL": "http://localhost:4040/claude"
},

// Also set for integrated terminals (pick your platform):
"terminal.integrated.env.windows": {
    "ANTHROPIC_BASE_URL": "http://localhost:4040/claude"
},
"terminal.integrated.env.osx": {
    "ANTHROPIC_BASE_URL": "http://localhost:4040/claude"
},
"terminal.integrated.env.linux": {
    "ANTHROPIC_BASE_URL": "http://localhost:4040/claude"
}
```

`claudeCode.environmentVariables` affects the extension's API calls. The `terminal.integrated.env.*` settings ensure integrated terminals also use the proxy.

### Disabling the proxy

If Context Lens is not running, Claude Code will fail to connect. Disable the proxy temporarily or permanently:

**Temporary (single session)**

```bash
# Bash / Zsh (macOS, Linux, Git Bash, WSL)
unset ANTHROPIC_BASE_URL
claude
```

```powershell
# PowerShell (Windows)
$env:ANTHROPIC_BASE_URL = ""
claude
```

**Permanent**

1. **Shell profile**: Remove or comment out the `export ANTHROPIC_BASE_URL=...` line from your shell RC file.
2. **Windows env var**: Delete via System Properties → Environment Variables, or run `setx ANTHROPIC_BASE_URL ""`.
3. **VS Code settings**: Remove or comment out the `claudeCode.environmentVariables` and `terminal.integrated.env.*` entries.
4. Restart VS Code and any open terminals.

### Claude Code

Point Claude Code at the proxy using any of the methods in [Setting ANTHROPIC_BASE_URL](#setting-anthropic_base_url) above.

### OpenCode

OpenCode using `github-copilot/claude-*` model IDs routes through GitHub Copilot's API and is **not affected** by `ANTHROPIC_BASE_URL`.

If you switch to a raw `anthropic/claude-*` model ID, set `ANTHROPIC_BASE_URL` the same way as for Claude Code.

### VS Code Copilot, Codex, and other HTTPS-only tools

These tools can't set a custom base URL, so they go through mitmproxy on port 8080 instead.

**Option A: PAC file** — a `proxy.pac` is included that routes `githubcopilot.com` and `api.anthropic.com` through mitmproxy:

```jsonc
// VS Code settings.json
"http.proxyAutoconfigUrl": "file:///path/to/.context-lens/proxy.pac",
"http.proxyStrictSSL": false
```

> Replace `/path/to/` with your actual home directory (e.g., `C:/Users/YourName` on Windows, `/Users/yourname` on macOS).

**Option B: Environment variable**

```bash
https_proxy=http://localhost:8080 SSL_CERT_FILE=~/.mitmproxy/mitmproxy-ca-cert.pem codex "prompt"
```

## Platform-Specific Setup

### mitmproxy CA certificate

mitmproxy needs a trusted CA cert to intercept HTTPS. On first run it generates certs in `~/.mitmproxy/`.

**Windows:**
```cmd
certutil -addstore Root "%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer"
```

**macOS:**
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem
```

**Linux (Debian/Ubuntu):**
```bash
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy.crt
sudo update-ca-certificates
```

## What It Shows

The web UI at `localhost:4041` provides:

- **Treemap** of context composition: system prompts, tool definitions, conversation history, tool results, thinking blocks
- **Cost tracking** per turn and per session
- **Session threading** with main agent vs subagent identification
- **Findings** that flag issues (large tool results, context overflow risk, unused definitions)
- **Timeline** showing context growth over turns

