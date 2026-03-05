# Qdrant RAG MCP Server

Semantic search over Obsidian vault content and Git repositories via Qdrant vector database, exposed as MCP tools through mcp-proxy SSE endpoints.

## Architecture

```plantuml
@startuml
!theme plain
skinparam backgroundColor white
skinparam roundCorner 8
skinparam defaultFontSize 11
skinparam defaultFontName "Segoe UI"
skinparam shadowing false
skinparam packageStyle frame
skinparam nodesep 40
skinparam ranksep 30

' -- Color palette --
skinparam package {
  BackgroundColor<<source>> #F0F7FF
  BorderColor<<source>> #4A90D9
  BackgroundColor<<indexing>> #FFF8E1
  BorderColor<<indexing>> #F9A825
  BackgroundColor<<infra>> #F3E5F5
  BorderColor<<infra>> #8E24AA
  BackgroundColor<<clients>> #ECEFF1
  BorderColor<<clients>> #546E7A
}

skinparam rectangle {
  BackgroundColor<<work>> #BBDEFB
  BorderColor<<work>> #1565C0
  BackgroundColor<<personal>> #C8E6C9
  BorderColor<<personal>> #2E7D32
  BackgroundColor<<code>> #FFF9C4
  BorderColor<<code>> #F9A825
}

skinparam storage {
  BackgroundColor<<work>> #BBDEFB
  BorderColor<<work>> #1565C0
  BackgroundColor<<personal>> #C8E6C9
  BorderColor<<personal>> #2E7D32
  BackgroundColor<<code>> #FFF9C4
  BorderColor<<code>> #F9A825
}

' ══════════════════════════════════════
' LAYER 1: DATA SOURCES
' ══════════════════════════════════════
package "Data Sources" <<source>> {
  rectangle "Obsidian: 0 Profisee/" <<work>> as profisee
  rectangle "Obsidian: Personal folders" <<personal>> as personal_files
  rectangle "Git Repositories" <<code>> as repos
  profisee -[hidden]right- personal_files
  personal_files -[hidden]right- repos
}

' ══════════════════════════════════════
' LAYER 2: INDEXING + STORAGE
' ══════════════════════════════════════
package "Indexing + Storage" <<indexing>> {
  component "**index_obsidian.py**\nchunking + FastEmbed\nall-MiniLM-L6-v2 (384d)" as indexer
  component "**index_repos.py**\ncode-aware chunking" as repo_indexer
  storage "work" <<work>> as work_col
  storage "personal" <<personal>> as personal_col
  storage "code" <<code>> as code_col
  indexer -[hidden]right- repo_indexer
}

' ══════════════════════════════════════
' LAYER 3: MCP INFRASTRUCTURE
' ══════════════════════════════════════
package "qdrant-mcp container :7020" <<infra>> {
  component "**mcp-proxy**\nSSE multiplexer" as proxy
  rectangle "qdrant-work" <<work>> as work_sse
  rectangle "qdrant-personal" <<personal>> as personal_sse
  rectangle "qdrant-code" <<code>> as code_sse
  proxy -[hidden]down- work_sse
}

' ══════════════════════════════════════
' LAYER 4: AI CLIENTS
' ══════════════════════════════════════
package "AI Clients" <<clients>> {
  actor "VS Code\nCopilot" as copilot
  actor "Claude\nDesktop" as claude_desktop
  actor "Claude\nCode" as claude_code
  actor "OpenCode" as opencode
  actor "Cline /\nKilo Code" as cline
  copilot -[hidden]right- claude_desktop
  claude_desktop -[hidden]right- claude_code
  claude_code -[hidden]right- opencode
  opencode -[hidden]right- cline
}

' ══════════════════════════════════════
' CONNECTIONS
' ══════════════════════════════════════

' Layer 1 → Layer 2
profisee -[#1565C0]down-> indexer
personal_files -[#2E7D32]down-> indexer
repos -[#F9A825]down-> repo_indexer

' Indexers → Storage
indexer -[#1565C0]down-> work_col
indexer -[#2E7D32]down-> personal_col
repo_indexer -[#F9A825]down-> code_col

' Layer 2 → Layer 3
work_col -[#1565C0]down-> work_sse
personal_col -[#2E7D32]down-> personal_sse
code_col -[#F9A825]down-> code_sse

' Layer 3 → Layer 4: Direct SSE access
proxy -[#546E7A]down-> copilot
proxy -[#546E7A]down-> claude_desktop
proxy -[#546E7A]down-> claude_code
proxy -[#546E7A]down-> opencode
proxy -[#546E7A]down-> cline

legend bottom right
  |<#BBDEFB> Work (Profisee) |
  |<#C8E6C9> Personal |
  |<#FFF9C4> Code (Git repos) |
  | Clients connect directly via SSE |
end legend

@enduml
```

## Components

### Qdrant DB

Vector database running in Docker.

```bash
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v ~/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

### qdrant-mcp Container

Standalone Debian-based container (`python:3.12-slim`) running `mcp-proxy` + `mcp-server-qdrant`. Debian is required because `onnxruntime` (dependency of `fastembed`) has no wheels for Alpine Linux on ARM.

- **Port:** 7020
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **Vector name:** `fast-all-minilm-l6-v2` (set by mcp-server-qdrant's FastEmbed provider)
- **Named servers:** Configured in `servers.json` (e.g., `qdrant-work`, `qdrant-personal`)

#### Setup

```bash
# Copy example config and customize for your machine
cp servers.json.example servers.json
# Edit servers.json - remove qdrant-personal if you only need work collection

# Build and start
docker compose up -d --build

# Rebuild after config changes
docker compose up -d --build && docker compose restart
```

### Indexer

Python script that walks the Obsidian vault, chunks markdown files, generates embeddings, and upserts to Qdrant.

Location: `indexer/index_obsidian.py`

#### Setup

```bash
cd indexer

# Copy example config and customize for your machine
cp indexer.yaml.example indexer.yaml
# Edit indexer.yaml:
#   - Set vault_path to your Obsidian vault location
#   - Adjust collections and routing for your needs
#   - Set skip_unrouted: true for work-only indexing

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

#### Usage

```bash
cd indexer
source .venv/bin/activate

# Index using config file (recommended)
python index_obsidian.py --config indexer.yaml

# Incremental index (skips unchanged files)
python index_obsidian.py --config indexer.yaml

# Full re-index
python index_obsidian.py --config indexer.yaml --force

# Preview without writing
python index_obsidian.py --config indexer.yaml --dry-run
```

#### Configuration (indexer.yaml)

See `indexer.yaml.example` for all options. Key settings:

| Setting | Description |
|---|---|
| `vault_path` | Path to Obsidian vault (machine-specific) |
| `collections` | List of Qdrant collections to use |
| `routing` | Maps folder patterns to collections |
| `skip_unrouted` | `true` = skip unmatched files, `false` = use default_collection |
| `skip_dirs` | Folders to ignore entirely |

#### How It Works

1. Reads config from `indexer.yaml` (or command-line `--config`)
2. Walks vault for `.md` files, skipping excluded directories
3. Routes files to collections based on `routing` rules
4. Skips unchanged files (tracked via `.index_state.json`)
5. Chunks by markdown headers (H1-H3), falls back to paragraph splitting, max ~800 chars
6. Prepends document title to each chunk for better embedding context
7. Uses `passage_embed` (not `embed` or `query_embed`) to match MCP server behavior
8. Upserts with named vector `fast-all-minilm-l6-v2` and metadata payload
9. Cleans up points for deleted files

#### First-Time Setup

```bash
cd indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp indexer.yaml.example indexer.yaml
# Edit indexer.yaml with your vault path and preferences
python index_obsidian.py --config indexer.yaml
```

## Client Configuration

AI clients connect directly to the qdrant-mcp SSE endpoints on port 7020. Each named server has its own endpoint: `http://localhost:7020/servers/{name}/sse`

### VS Code / GitHub Copilot (`mcp.json`)

```json
{
  "servers": {
    "qdrant-work": {
      "command": "npx",
      "args": ["--prefer-online", "-y", "mcp-remote", "http://localhost:7020/servers/qdrant-work/sse"]
    },
    "qdrant-code": {
      "command": "npx",
      "args": ["--prefer-online", "-y", "mcp-remote", "http://localhost:7020/servers/qdrant-code/sse"]
    }
  }
}
```

Config location: `%APPDATA%\Code\User\mcp.json` (Windows) or `~/Library/Application Support/Code/User/mcp.json` (macOS)

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "qdrant-work": {
      "command": "npx.cmd",
      "args": ["-y", "mcp-remote", "http://localhost:7020/servers/qdrant-work/sse"]
    }
  }
}
```

Uses `npx.cmd` on Windows (not `npx`). Config location: `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS).

### Claude Code (`settings.local.json`)

Claude Code discovers MCP servers from `~/.claude/.mcp.json` or project-level `.mcp.json`. Enable them in `~/.claude/settings.local.json`:

```json
{
  "enabledMcpjsonServers": ["qdrant-work", "qdrant-code"]
}
```

### OpenCode (`opencode.json`)

OpenCode supports SSE natively — no `mcp-remote` bridge needed:

```json
{
  "mcpServers": {
    "qdrant-work": {
      "type": "remote",
      "url": "http://localhost:7020/servers/qdrant-work/sse",
      "enabled": true
    }
  }
}
```

Config location: `.config/opencode/opencode.json` (user-level) or `opencode.json` (project-level).

### Cline / Kilo Code (`mcp_settings.json`)

```json
{
  "mcpServers": {
    "qdrant-work": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:7020/servers/qdrant-work/sse"]
    }
  }
}
```

Config locations:
- **Cline (VS Code):** `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **Cline (Standalone):** `~/.cline/data/settings/cline_mcp_settings.json`
- **Kilo Code:** `%APPDATA%\Code\User\globalStorage\kilocode.kilo-code\settings\mcp_settings.json`

### Permissions

Add qdrant tools to auto-approve in `~/ai/permissions/permissions.yaml`:

```yaml
auto_approve:
  - qdrant-work_qdrant-find
  - qdrant-work_qdrant-store
  - qdrant-code_qdrant-find
  - qdrant-code_qdrant-store
```

## MCP Tools

Available once a client is configured to connect to the qdrant-mcp SSE endpoints:

| Tool | Description |
|---|---|
| `qdrant-work_qdrant-find` | Semantic search over work (Profisee) content |
| `qdrant-work_qdrant-store` | Store new entries in work collection |
| `qdrant-personal_qdrant-find` | Semantic search over personal content |
| `qdrant-personal_qdrant-store` | Store new entries in personal collection |

## Current State

- **Work collection:** 225 points (Profisee Captain's Log, notes, session summaries)
- **Personal collection:** 3,389 points (daily logs, renovation, finance, fitness, job hunt, etc.)
- **Code collection:** 7,640 points (10 Git repositories — source code, configs, docs)
- **Embedding model:** `all-MiniLM-L6-v2` (384d, ~45MB)

## Repository Indexing

Indexes local Git repositories into a `code` collection for semantic search over codebases.

### Collection

| Collection | Content | MCP Server |
|---|---|---|
| `code` | Source code, configs, docs from Git repos | `qdrant-code` |

Same pattern as `work`/`personal` — named server in `servers.json`, SSE endpoint on port 7020.

### Configuration

All repo indexer settings live in `indexer/repos.json` — no code changes needed to add/remove repos or adjust skip patterns.

| Key | Purpose |
|---|---|
| `repos_base` | Base directory for repositories (e.g., `~/Repositories`) |
| `repos` | List of repository directory names to index |
| `skip_dirs` | Directories to skip (e.g., `.git`, `node_modules`, `dist`) |
| `skip_files` | Files to skip (e.g., `package-lock.json`, `yarn.lock`) |
| `skip_extensions` | Binary/generated file extensions to skip |
| `index_extensions` | Text file extensions to index |
| `index_filenames` | Specific filenames to always index (e.g., `Dockerfile`, `CLAUDE.md`) |
| `max_chunk_chars` | Maximum chunk size in characters (default: 1200) |

### Chunking Strategy

Code-aware chunking splits by language-specific boundaries:

| Language | Split Pattern |
|---|---|
| Python | `class`, `def`, `async def` |
| TypeScript/JavaScript | `function`, `class`, `const =`, `interface`, `type` |
| Go | `func`, `type` |
| Rust | `fn`, `struct`, `enum`, `impl`, `trait`, `mod` |
| Ruby | `class`, `module`, `def` |
| Shell | Function definitions |
| C#/Java | Class, interface, enum, method declarations |
| Markdown | H1-H3 header boundaries |
| Other text | Paragraph-based fallback, then line-based |

### Usage

```bash
cd indexer
source .venv/bin/activate

# Incremental index (skips unchanged files)
python index_repos.py

# Full re-index
python index_repos.py --force

# Preview without writing
python index_repos.py --dry-run
```

### How It Works

1. Loads configuration from `repos.json`
2. Walks each repository, respecting skip patterns
3. Skips unchanged files (tracked via `.index_repos_state.json` with MD5 hashes)
4. Detects language from file extension for code-aware chunking
5. Prepends `repo/filepath` context to each chunk for better embeddings
6. Uses `passage_embed` with named vector `fast-all-minilm-l6-v2`
7. Upserts with deterministic point IDs: `UUID5(repo::filepath::chunk_index)`
8. Cleans up points for deleted files

### Metadata

Each point stores:

```json
{
  "document": "<chunk content>",
  "metadata": {
    "repo": "ai-infrastructure",
    "file_path": "mcps/qdrant-mcp/indexer/index_obsidian.py",
    "language": "python",
    "chunk_index": 0,
    "total_chunks": 5,
    "collection": "code",
    "last_modified": "2026-02-27T..."
  }
}
```

### MCP Tools

| Tool | Description |
|---|---|
| `qdrant-code_qdrant-find` | Semantic search over indexed repositories |
| `qdrant-code_qdrant-store` | Store entries in code collection |

## Future Work

- [ ] Automate re-indexing via launchd/cron schedule
- [ ] Add AI skills + memory indexing
- [ ] Migrate Qdrant DB to Synology NAS
- [ ] Evaluate upgrading to a larger embedding model (nomic-embed-text 768d or mxbai-embed-large 1024d)


