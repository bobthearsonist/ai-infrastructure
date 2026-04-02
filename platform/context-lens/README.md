# Context Lens

Local reverse proxy that intercepts LLM API calls from coding agents and visualizes context window composition.

- **Repo**: [github.com/larsderidder/context-lens](https://github.com/larsderidder/context-lens)
- **Proxy**: `http://localhost:4040`
- **Web UI**: `http://localhost:4041`
- **Data**: `~/.context-lens/data/*.lhar`

## Installation

Installed globally via npm (not Docker — lightweight local tool):

```bash
npm install -g context-lens
```

Update:

```bash
npm update -g context-lens
```

Context Lens checks for updates on each run and notifies you.

### Dependencies

- **mitmproxy** (for OpenCode, Cline interception): already installed via `pip install --user mitmproxy`
- Requires `C:\Users\MartinPe\AppData\Roaming\Python\Python314\Scripts` on PATH

## Usage

### Terminal (Claude Code)

```bash
context-lens --no-open claude
# or with flags
context-lens --no-open claude --continue
context-lens --no-open claude --resume
```

> `--no-open` required on Windows Git Bash — `start` command doesn't exist in MSYS2. See [issue #33](https://github.com/larsderidder/context-lens/issues/33).

### Terminal (OpenCode)

```bash
context-lens --no-open oc
```

### VS Code Extension

The Claude Code VS Code extension is configured to route through Context Lens via environment variable:

```jsonc
// VS Code settings.json
"claudeCode.environmentVariables": {
    "ANTHROPIC_BASE_URL": "http://localhost:4040/claude"
}
```

Start the proxy in background mode before using VS Code:

```bash
context-lens background start --no-open
```

Stop when done:

```bash
context-lens background stop
```

> If Context Lens is not running, Claude Code in VS Code will fail to connect to the API. Remove or comment out the env var setting when not using the proxy.

### Background Mode

Keep the proxy running across terminal sessions:

```bash
context-lens background start --no-open   # start detached
context-lens background status             # check if running
context-lens background stop               # stop
```

## Analyze Captures

```bash
# Human-readable summary
context-lens analyze ~/.context-lens/data/claude-<id>.lhar

# JSON output for scripting
context-lens analyze ~/.context-lens/data/claude-<id>.lhar --json

# Composition before compaction events
context-lens analyze <file>.lhar --composition=pre-compaction
```

## Diagnostics

```bash
context-lens doctor
```

Checks: node version, port availability, mitmdump presence, CA cert, data directory.

## What It Shows

The web UI at `localhost:4041` provides:

- **Treemap** of context composition: system prompts, tool definitions, conversation history, tool results, thinking blocks
- **Cost tracking** per turn and per session
- **Session threading** with main agent vs subagent identification
- **Findings** that flag issues (large tool results, context overflow risk, unused definitions)
- **Timeline** showing context growth over turns

## Known Limitations

- Findings panel is informational only — no drill-down to specific tool calls
- No per-tool/provider aggregation (all tool_results lumped together)
- `start` command fails on Windows Git Bash ([#33](https://github.com/larsderidder/context-lens/issues/33))

## Windows Bugs (local patches required)

Two bugs prevent `context-lens oc` from working on Windows with the GitHub Copilot provider. Both patched locally in `C:\nvm4w\nodejs\node_modules\context-lens\` — patches are lost on `npm update -g context-lens`, reapply after updating.

### 1. ENOENT when spawning npm-installed tools

**File**: `dist/cli.js` (~line 461)

`spawn(commandName, ...)` is called without `shell: true`. On Windows, npm-installed tools like `opencode` and `codex` only have `.cmd`/`.sh` shims — no `.exe`. Node's `spawn` without shell mode can't resolve `.cmd` extensions, causing `ENOENT`.

**Fix**: Add `shell: true` on Windows:

```js
// Before (broken on Windows):
childProcess = spawn(spawnCommand, spawnArgs, {
    stdio: "inherit",
    env: childEnv,
});

// After:
const isWindows = process.platform === "win32";
childProcess = spawn(spawnCommand, spawnArgs, {
    stdio: "inherit",
    env: childEnv,
    shell: isWindows,
});
```

### 2. GitHub Copilot API traffic not captured by mitmproxy addon

**File**: `mitm_addon.py`

The `CAPTURE_PATTERNS` list has no entry for `githubcopilot.com`, and `CATCHALL_PATH_PATTERNS` only matches `/v1/chat/completions` — but GitHub Copilot's API uses `/chat/completions` (no `/v1/` prefix). Traffic passes through mitmproxy but is silently dropped.

**Fix**: Add GitHub Copilot to `CAPTURE_PATTERNS` and a catchall for `/chat/completions`:

```python
# Add to CAPTURE_PATTERNS (before the OpenAI entries):
("githubcopilot.com", "/chat/completions", "openai", None),

# Add to CATCHALL_PATH_PATTERNS:
("/chat/completions", "openai"),
```

## Development

Run from local source with hot-reload:

```bash
# Copy and configure env
cp .env.dev.example .env

# Edit .env to set CONTEXT_LENS_SRC to your worktree path

# Start dev mode
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This mounts the source from `CONTEXT_LENS_SRC`, runs `tsc --watch` for backend compilation, `nodemon` for server auto-restart, and Vite dev server for UI hot-reload.

To switch worktrees, update `CONTEXT_LENS_SRC` in `.env` and restart.

## Ports

| Port | Service | Notes |
|------|---------|-------|
| 4040 | Proxy | LLM API interception |
| 4041 | Analysis API | Auto-restart in dev mode |
| 5173 | Vite dev server | UI hot-reload (dev mode only) |
