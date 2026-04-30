# Windows Setup

Platform-specific notes for running ai-infrastructure on Windows with WSL2 and Docker Desktop. This document covers only what differs from the standard setup in the [main README](../README.md).

## Repo Locations

The infrastructure spans two filesystems:

| Location | Filesystem | What lives there |
| -------- | ---------- | ---------------- |
| `C:\Repositories\ai-infrastructure\` | Windows (NTFS) | Docker Compose stacks, configs, certs — everything Docker reads |
| `~/repositories/context-lens` (WSL Ubuntu) | ext4 via WSL | Context Lens source repo (fork: `bobthearsonist/context-lens`) |

**Why the split**: Context Lens development uses `pnpm` and `node_modules`, which perform poorly on NTFS due to symlink limitations. The source repo lives in WSL's native ext4 filesystem for fast builds. The Docker Compose deployment in ai-infrastructure installs from npm at runtime and doesn't need the source.

## Docker Desktop

Docker Desktop runs a shared daemon accessible from both Windows and WSL. Containers started from either side share the same Docker engine, networks, and port mappings.

- **Compose commands** work from both Git Bash and WSL
- **Volume paths**: Use Windows paths in compose files (`C:\...` or `/c/...` in Git Bash) — Docker Desktop translates them. WSL paths (`/home/martinpe/...`) also work when running compose from WSL.
- **host.docker.internal**: Resolves to the host from inside containers on both platforms

## Git & SSH

| Context | SSH Key | Config |
| ------- | ------- | ------ |
| Windows (Git Bash) | `~/.ssh/id_rsa` | Default identity |
| WSL Ubuntu | `~/.ssh/id_ed25519_github` | GitHub via `~/.ssh/config` Host entry |
| WSL Ubuntu | `~/.ssh/id_rsa_ado` | Azure DevOps via `~/.ssh/config` Host entry |

The context-lens fork repo in WSL uses SSH remotes (`git@github.com:bobthearsonist/context-lens.git`). HTTPS remotes hang in non-interactive shells because credential helpers can't prompt.

## Context Lens: Source vs Deployment

There are two docker-compose.yml files for Context Lens:

| File | Purpose | How it runs |
| ---- | ------- | ----------- |
| `ai-infrastructure/platform/context-lens/docker-compose.yml` | Production deployment | Installs `context-lens@latest` from npm at startup |
| `ai-infrastructure/platform/context-lens/docker-compose.dev.yml` | Dev overlay | Mounts WSL source repo via `$CONTEXT_LENS_SRC`, runs tsc + nodemon + vite |

For dev mode, set `CONTEXT_LENS_SRC` in `platform/context-lens/.env` to the WSL source path:

```bash
CONTEXT_LENS_SRC=//wsl.localhost/Ubuntu/home/martinpe/repositories/context-lens
```

Or from WSL:

```bash
CONTEXT_LENS_SRC=~/repositories/context-lens
```

### Cross-Filesystem Gotchas

- **Broken node_modules**: The WSL source repo's `node_modules/` contains pnpm symlinks that point to an absolute path. If you run `pnpm install` from one side and try to resolve modules from the other, the symlinks break. Fix: run `pnpm install` from the same filesystem where you'll use the modules.
- **File watchers**: `tsc --watch` and Vite HMR work in dev containers when the source is bind-mounted from WSL, but inotify events may be delayed (~1s) crossing the filesystem boundary.
- **Git line endings**: The `.gitattributes` in context-lens enforces LF. Windows editors may add CRLF warnings — these are cosmetic.

## Running Git Commands Against WSL Repos

From Windows (Git Bash or Claude Code):

```bash
# Option A: wsl exec (preferred — uses WSL's git, SSH keys, and shell)
wsl -d Ubuntu -- bash -c 'cd ~/repositories/context-lens && git status'

# Option B: Windows git with UNC path (works but uses Windows SSH keys)
git -C //wsl.localhost/Ubuntu/home/martinpe/repositories/context-lens status
```

Option A is preferred because it uses WSL's SSH config and keys. Option B uses the Windows SSH agent, which may not have the right keys loaded.

## Shell Wrappers

Context Lens provides shell wrappers that route AI tool commands through the proxy. On Windows, these are configured in:

- **Git Bash**: `~/.bashrc` (via `~/ai/init.bash`)
- **PowerShell**: `$PROFILE` (typically `Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1`)

The `ANTHROPIC_BASE_URL` environment variable is set globally via `setx` so all shells (Git Bash, PowerShell, cmd) pick it up without per-shell configuration.

## Machine-Specific Config Files

These files are gitignored and must be created per-machine:

| File | Purpose |
| ---- | ------- |
| `mcps/mcpx/.env` | `MCP_CONFIG` path, `CUSTOM_CA_CERT` path |
| `mcps/mcpx/mcp.windows-work.json` | mcpx MCP server definitions (Windows work machine) |
| `mcps/stdio-proxy/servers.windows-work.json` | stdio-proxy MCP definitions (Windows work machine) |
| `platform/context-lens/.env` | `CONTEXT_LENS_SRC` for dev mode |
| `gateways/agentgateway/certs/` | TLS certs for nginx-proxy |
| `mcps/mcpx/certs/` | TLS certs for nginx-ssl, custom CA certs |
