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

### Claude Code (terminal and VS Code extension)

Point Claude Code at the built-in proxy:

```jsonc
// VS Code settings.json
"claudeCode.environmentVariables": {
    "ANTHROPIC_BASE_URL": "http://localhost:4040/claude"
}
```

> If Context Lens is not running, Claude Code will fail to connect to the API. Remove or comment out the env var when not using the proxy.

### VS Code Copilot, Codex, and other HTTPS-only tools

These tools can't set a custom base URL, so they go through mitmproxy on port 8080 instead.

**Option A: PAC file** -- a `proxy.pac` is included that routes `githubcopilot.com` and `api.anthropic.com` through mitmproxy:

```jsonc
// VS Code settings.json
"http.proxyAutoconfigUrl": "file:///C:/Users/YourName/.context-lens/proxy.pac",
"http.proxyStrictSSL": false
```

**Option B: Environment variable**

```bash
https_proxy=http://localhost:8080 SSL_CERT_FILE=~/.mitmproxy/mitmproxy-ca-cert.pem codex "prompt"
```

## Windows Setup

### mitmproxy CA certificate

mitmproxy needs a trusted CA cert to intercept HTTPS. On first run it generates certs in `~/.mitmproxy/`. Install the root CA into the OS trust store:

```bash
certutil -addstore Root "%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer"
```

## What It Shows

The web UI at `localhost:4041` provides:

- **Treemap** of context composition: system prompts, tool definitions, conversation history, tool results, thinking blocks
- **Cost tracking** per turn and per session
- **Session threading** with main agent vs subagent identification
- **Findings** that flag issues (large tool results, context overflow risk, unused definitions)
- **Timeline** showing context growth over turns

