# Context Lens Dev Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Docker Compose dev override that mounts a local worktree/source path and runs hot-reloading backend + UI dev servers.

**Architecture:** A `docker-compose.dev.yml` overlay on the existing production compose. Uses `node:22-slim` with globally-installed `concurrently` and `nodemon`. Source is bind-mounted from a configurable host path (`CONTEXT_LENS_SRC`). Session data mount unchanged.

**Tech Stack:** Docker Compose, Node 22, pnpm, TypeScript (tsc --watch), Vite dev server, nodemon, concurrently

---

### Task 1: Create docker-compose.dev.yml

**Files:**
- Create: `platform/context-lens/docker-compose.dev.yml`

- [ ] **Step 1: Create the dev compose override**

```yaml
# Dev overlay — mounts local source for hot-reload development.
#
# Usage:
#   CONTEXT_LENS_SRC=/c/Repositories/context-lens docker compose -f docker-compose.yml -f docker-compose.dev.yml up
#
# Or create a .env file:
#   CONTEXT_LENS_SRC=/c/Repositories/context-lens
#
# Ports:
#   4040 - Proxy
#   4041 - Analysis API (nodemon auto-restart)
#   5173 - Vite dev server (UI hot-reload)

services:
  context-lens:
    volumes:
      - ${CONTEXT_LENS_SRC:-.}:/app
      - /app/node_modules
      - /app/ui/node_modules
      - ${CONTEXT_LENS_DATA:-~/.context-lens/data}:/root/.context-lens/data
    ports:
      - "5173:5173"
    environment:
      CONTEXT_LENS_BIND_HOST: "0.0.0.0"
      TSC_WATCHFILE: UseFsEventsWithFallbackDynamicPolling
    command:
      - |
        corepack enable
        pnpm install
        cd ui && pnpm install && cd ..
        npm install -g concurrently nodemon
        pnpm run build
        pnpm run build:ui
        concurrently -k -n tsc,srv,ui -c blue,green,magenta \
          "tsc --watch --preserveWatchOutput" \
          "nodemon --delay 1 --watch dist dist/cli.js -- --no-open" \
          "cd ui && pnpm dev --host 0.0.0.0"
```

Notes:
- Anonymous volumes for `node_modules` prevent host mounts from clobbering Linux-native deps
- Initial `pnpm run build` + `pnpm run build:ui` so the server can start before tsc --watch catches up
- `--preserveWatchOutput` prevents tsc from clearing the terminal
- `nodemon --delay 1` avoids restarting mid-compilation
- `TSC_WATCHFILE` env var improves file watching performance on bind mounts
- Port 5173 exposed for Vite HMR dev server
- `-k` flag on concurrently kills all processes if one exits

- [ ] **Step 2: Verify file created**

Run: `cat platform/context-lens/docker-compose.dev.yml`
Expected: The compose override content above

### Task 2: Create .env.dev.example

**Files:**
- Create: `platform/context-lens/.env.dev.example`

- [ ] **Step 1: Create the example env file**

```bash
# Path to context-lens source checkout or worktree.
# Change this to target a different worktree for development.
CONTEXT_LENS_SRC=/c/Repositories/context-lens

# Examples for worktrees:
# CONTEXT_LENS_SRC=/c/Repositories/context-lens.worktrees/feat/show-session-label
# CONTEXT_LENS_SRC=/c/Repositories/context-lens.worktrees/fix/claude-working-dir

# Session data directory (default: ~/.context-lens/data)
# CONTEXT_LENS_DATA=~/.context-lens/data
```

- [ ] **Step 2: Verify file created**

Run: `cat platform/context-lens/.env.dev.example`

### Task 3: Update README.md with dev workflow

**Files:**
- Modify: `platform/context-lens/README.md`

- [ ] **Step 1: Add Development section to README**

Append after the existing content:

```markdown
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

| Port | Service | Mode |
|------|---------|------|
| 4040 | Proxy | Auto-restart on backend changes |
| 4041 | Analysis API | Auto-restart on backend changes |
| 5173 | Vite dev server | HMR for UI changes |

To switch worktrees, update `CONTEXT_LENS_SRC` in `.env` and restart.
```

- [ ] **Step 2: Commit**

```bash
git add platform/context-lens/docker-compose.dev.yml platform/context-lens/.env.dev.example platform/context-lens/README.md
git commit -m "feat(context-lens): add docker compose dev overlay for local source hot-reload"
```

### Task 4: Stand it up and verify

- [ ] **Step 1: Create .env from example**

```bash
cp platform/context-lens/.env.dev.example platform/context-lens/.env
```

- [ ] **Step 2: Start dev mode**

```bash
cd platform/context-lens
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Expected: Container starts, installs deps, runs initial build, then shows three concurrent processes (tsc, srv, ui). Web UI accessible at http://localhost:5173, API at http://localhost:4041.

- [ ] **Step 3: Verify session data loads**

Open http://localhost:4041 — existing Claude sessions from `~/.context-lens/data` should appear.

- [ ] **Step 4: Verify hot-reload**

Make a trivial change to a UI file in the source worktree. Vite should hot-reload in the browser without manual restart.
