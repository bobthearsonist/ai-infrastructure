# AI Infrastructure

Central infrastructure for AI tools, MCP servers, gateways, and platform services.

## TODO

- [ ] Create an `ai-infrastructure` skill (in `~/AI/skills/` or in this repo) that documents all services, ports, startup commands, and dependencies so AI agents know what infrastructure is available when setting up machines or debugging connectivity issues.

## Architecture

```plantuml
@startuml ai-infrastructure
!theme plain
skinparam backgroundColor #FEFEFE
skinparam componentStyle rectangle
skinparam defaultFontName Consolas

title AI Infrastructure Architecture\n(each component = 1 Docker container; nested boxes = processes inside their parent container)

' === AI Clients ===
package "AI Clients" as clients #E3F2FD {
  [Claude Code] as claude_code
  [VS Code Copilot] as vscode
  [Claude Desktop] as claude
  [Cline / Other] as other
}

' === LLM Proxy (standalone, implicit default network) ===
package "Context Lens stack (implicit network)" as cl_stack #E0F7FA {
  component "context-lens\n:4040 (reverse proxy)\n:4041 (web UI + ingest API)" as context_lens #80DEEA
  component "mitmproxy\n:8080 (HTTPS forward proxy)" as mitmproxy #4DD0E1
}

' === MCP Gateway layer (ONE element; 2 interchangeable implementations inside) ===
' The two gateways are structurally identical (same sidecar pattern), so the
' shared sidecars are drawn ONCE and annotated "per gateway" instead of twice.
package "MCP Gateway layer" as gateways #DCEDC8 {
  ' --- The two interchangeable implementations, grouped so "there are two" reads clearly ---
  package "2 implementations · mcpx is the live one" as gw_impls #D0E8C0 {
    component "agentgateway\n:3847 (MCP) · :15001 (UI) · :15020 (metrics)\nLinux Foundation\n<b>STOPPED — stack still on disk</b>" as agentgateway #E0E0E0
    component "<b>mcpx</b>\n:9000 (MCP) · :5173 (Control Plane)\nLunar.dev — tool groups + RBAC\n<b>ACTIVE — all clients route here</b>" as mcpx #C8E6C9
  }

  ' --- Shared sidecar pattern (each gateway runs its OWN copy of each) ---
  component "nginx (TLS termination)\nag :3443/:9223 · mcpx :9443/:5443/:9222" as nginx_tls #A5D6A7
  component "stdio-proxy\n:7030 (internal, one per gateway)" as stdio_proxy #81C784 {
    [sequential-thinking] as stdio_seq #FFECB3
    [azure-devops\n(mcpx only)] as stdio_azdo #FFECB3
    [psmcp / Photoshop\n(mcpx only, per-machine)] as stdio_psmcp #FFECB3
  }
  component "mcp-status\n(health poller, per gateway)" as mcp_status #BCAAA4
  component "lunar-proxy\n(mcpx only · inactive)" as lunar #E0E0E0
}

' === Shared MCPs (ai-shared network) — each box = 1 standalone container ===
package "Shared MCPs (ai-shared)" as shared_mcps #FFF3E0 {
  [context7\n:7008] as context7 #FFCC80
  [memory\n:7040 (singleton)] as memory #FFCC80
  [kapture-server\n:61822 (WebSocket)] as kapture #FFCC80
  [hass-mcp\n:7010] as hass_mcp #FFE0B2
  [playwright\n:7007] as playwright #FFE0B2
  [browser-use\n:7011] as browser_use #FFE0B2
  [browsermcp\n:7009 (distinct from browser-use)] as browsermcp #FFE0B2
  [adb-proxy\n:3927 → :3001 (WS)\nPhotoshop UXP bridge, not an MCP endpoint] as adb_proxy #FFE0B2
}

' === Code Intelligence — codebase + knowledge indexing (two complementary kinds) ===
package "Code Intelligence" as code_intel #ECEFF1 {
  package "qdrant stack (ai-shared)\n<b>semantic — vector RAG</b>" as qdrant_stack #FFF3E0 {
    component "qdrant-mcp\n:7020 (mcp-proxy)\n4 named servers · 8 tools" as qdrant_mcp #FFCC80
    component "qdrant (vector DB)\n:6333 (HTTP) · :6334 (gRPC)\n""code-work__jina"" · ""code-public__jina""\n""notes-work"" · ""personal"" (empty)" as qdrant #CE93D8
    component "obsidian-watcher\n(sidecar, :cpu image)" as obs_watcher #FFE0B2
    component "repo-watcher-work\n(sidecar, :gpu image)" as repo_watcher_work #FFE0B2
    component "repo-watcher-public\n(sidecar, :gpu image)" as repo_watcher_public #FFE0B2
  }
  component "<b>graphify</b>\nCLI + MCP + Claude skill\n<b>structural — AST / call graph</b>\n[host-side, NOT containerized]" as graphify #FFF59D
}

' === Backing Services ===
package "Backing Services (ai-shared)" as backing #F3E5F5 {
  [Langfuse\n:3100 (UI)] as langfuse #CE93D8
  [Watchtower\n(auto-update)] as watchtower #E1BEE7
}

' === Observability ===
package "Observability (ai-shared)" as observability #E1F5FE {
  component "OTel Collector\n:4317/:4318 (internal)" as otel #81D4FA
  component "Jaeger\n:16686 (UI)" as jaeger #4FC3F7
  component "Prometheus\n:9090" as prometheus #29B6F6
  component "Grafana\n:3000" as grafana #03A9F4
}

' === Connections ===

' Clients linked as a GROUP (arrows leave the AI Clients box, not individual clients).
' LLM API — all clients route through Context Lens (rollout in progress); two entry paths:
clients --> context_lens : LLM API\nANTHROPIC_BASE_URL :4040
clients --> mitmproxy    : LLM API\nHTTPS_PROXY :8080
mitmproxy --> context_lens : POST /api/ingest :4041

' MCP — every client connects to one gateway implementation
clients --> gateways : MCP

' Host-side stdio MCP (Claude Code, via Claude skill; not through a gateway)
clients ..> graphify : stdio MCP\n(Claude Code)

' Layout anchors ONLY (invisible): keep the four client boxes spread across the TOP,
' exactly as the old per-client edges did. Visible arrows above stay group-level.
claude_code -[hidden]-> gateways
vscode      -[hidden]-> gateways
claude      -[hidden]-> gateways
other       -[hidden]-> gateways

' TLS termination (each gateway fronted by its own nginx; shown once)
nginx_tls -[#9E9E9E,dashed]-> agentgateway : reverse proxy (stopped)
nginx_tls --> mcpx : reverse proxy

' Each gateway → its own stdio-proxy (private network)
agentgateway -[#9E9E9E,dashed]-> stdio_proxy : private network (stopped)
mcpx --> stdio_proxy : private network

' Health poller (one per gateway, polls its stdio-proxy)
mcp_status --> stdio_proxy : poll /status

' Shared MCP backends: ONE visible line per MCP from the gateway layer (both
' implementations reach each; the line leaves the MCP Gateway layer box, not each gateway).
gateways --> context7   : SSE (ai-shared)
gateways --> memory     : SSE
gateways --> qdrant_mcp : SSE (semantic search)

' Photoshop chain: psmcp (stdio) → adb-proxy (WS bridge) → host Photoshop UXP plugin
stdio_psmcp ..> adb_proxy : WS :3001\n(→ host Photoshop UXP)

' qdrant stack internals. NOTE: the watchers do NOT talk to qdrant-mcp. Each spawns an
' indexer subprocess (index_obsidian.py / index_repos.py) that upserts straight into the
' DB. Read path and write path only meet at the collections.
qdrant_mcp --> qdrant : query :6333
obs_watcher --> qdrant : upsert (index_obsidian.py)
repo_watcher_work --> qdrant : upsert (index_repos.py)
repo_watcher_public --> qdrant : upsert (index_repos.py)

' Observability (agentgateway emitted OTLP, but it is stopped; mcpx not yet wired —
' so nothing is currently feeding the observability stack)
agentgateway -[#9E9E9E,dashed]-> otel : OTLP traces (stopped)
otel --> jaeger : traces
otel --> prometheus : span metrics
grafana --> prometheus : query
grafana --> jaeger : query

' Layout: place Observability UNDER the gateway layer (invisible ordering edge)
gateways -[hidden]-> observability

' Legend
legend right
  |= Color |= Layer / What it is |
  | <#80DEEA> | LLM Proxy (standalone container) |
  | <#C8E6C9> | Gateway container |
  | <#A5D6A7> | TLS Termination container |
  | <#81C784> | stdio-proxy container (per-stack) |
  | <#FFECB3> | stdio process **inside** a stdio-proxy |
  | <#BCAAA4> | mcp-status sidecar (health poller) |
  | <#FFCC80> | Shared MCP container (running) |
  | <#FFE0B2> | Shared MCP / sidecar container (available) |
  | <#FFF59D> | Host-side tool (NOT containerized) |
  | <#CE93D8> | Backing Service container |
  | <#81D4FA> | Observability container |
  | <#E0E0E0> | Inactive |
endlegend

@enduml
```

## Current Status

### Compose Stacks

Each stack is a self-contained `docker compose` unit. Stacks with a stdio-proxy include it from the shared template (`mcps/stdio-proxy/`) — each gets its own instance on a private network to avoid DNS collisions.

**agentgateway** (`gateways/agentgateway/`) — Linux Foundation MCP gateway — ⏹ **stopped as of 2026-08-18** (containers exited; stack still on disk). mcpx is the gateway clients actually use. Ports below are what it publishes *when started*.

| Service | What it does | Host Ports |
| ------- | ------------ | ---------- |
| agentgateway | Routes MCP requests to 10+ backends; CORS, stateless SSE mode | :3847 (MCP), :15001 (Admin UI), :15020 (Metrics) |
| nginx-proxy | TLS termination for agentgateway; reverse-proxies `/mcp` and `/sse`; proxies Chrome DevTools Protocol from :9223 → host :9222 | :3443 (HTTPS MCP), :15443 (HTTPS Admin), :9223 (CDP) |
| stdio-proxy | Bridges stdio MCPs: **sequential-thinking** (default `servers.json`). No per-server overlays included by this stack. | (internal :7030) |
| mcp-status | Polls stdio-proxy /status every 30s, logs per-MCP health | — |

**mcpx** (`mcps/mcpx/`) — Lunar.dev MCP gateway with tool groups and per-client access control — ✅ **running; this is the live gateway.** Added 2026-06-16. Before that, clients connected to backing MCPs (including qdrant-mcp on :7020) directly.

| Service | What it does | Host Ports |
| ------- | ------------ | ---------- |
| mcpx | Multiplexes MCP servers with tool grouping (core, coding, browser, creative, home) and consumer auth | :9000 (MCP), :5173 (Control Plane UI), :9001 (internal), :3100 (metrics, remapped from 3000) |
| nginx-ssl | TLS termination for mcpx; proxies `/mcp` and `/sse` on :9443; serves Control Plane on :5443; proxies CDP on :9222 → host :9222 | :9443 (HTTPS MCP), :5443 (HTTPS UI), :9222 (CDP) |
| stdio-proxy | Bridges stdio MCPs: **sequential-thinking** + **azure-devops** (azure-devops added via the per-server overlay `mcps/azure-devops/docker-compose.yml` that mcpx's compose includes, which mounts `~/.azure` into the proxy) | (internal :7030) |
| mcp-status | Polls stdio-proxy /status every 30s, logs per-MCP health | — |
| lunar-proxy | API gateway for rate limiting / observability (defined but not actively routed through) | :8000, :8040, :8081 |

> **Note on Kapture WebSocket (:61822):** previously proxied through `nginx-ssl`, now served by the standalone `kapture-server` container (`mcps/kapture/docker-compose.yml`). The `nginx-ssl` block above no longer publishes it.

**context-lens** (`platform/context-lens/`) — LLM API traffic interception and context window analysis

| Service | What it does | Host Ports |
| ------- | ------------ | ---------- |
| context-lens | Reverse proxy (:4040) intercepts calls from clients using `ANTHROPIC_BASE_URL`; web UI + ingest API (:4041) analyzes context composition, cost, waste | :4040 (proxy), :4041 (web UI), :5175 (Vite dev, dev mode) |
| mitmproxy | HTTPS forward proxy for clients that can't set a custom base URL (Copilot, Codex); addon POSTs captures to ingest API asynchronously | :8080 |

**qdrant** (`mcps/qdrant-mcp/`) — Vector database and semantic search MCP

| Service | What it does | Host Ports |
| ------- | ------------ | ---------- |
| qdrant | Vector database for RAG embeddings. 4 collections: `code-work__jina`, `code-public__jina`, `notes-work`, `personal` (empty) | :6333 (HTTP), :6334 (gRPC) |
| qdrant-mcp | mcp-proxy hosting 4 named MCP servers (one per collection) from a single `servers.json`; FastEmbed-powered semantic search | :7020 |
| repo-watcher-work | Watches `/repos`, reindexes into `code-work__jina` (`:gpu` image) | — |
| repo-watcher-public | Watches `/repos`, reindexes into `code-public__jina` (`:gpu` image) | — |
| obsidian-watcher | Watches `/vault`, reindexes into `notes-work` (`:cpu` image) | — |

Three independent watchers, one per corpus — nothing coordinates them, and each holds its
lockfile in its own container layer, so one lane can freeze silently while the others keep
working. Details: [`mcps/qdrant-mcp/README.md`](mcps/qdrant-mcp/README.md).

### Shared MCPs (ai-shared network)

These run as standalone containers (each has its own `mcps/<name>/docker-compose.yml`), reachable by both gateways over the `ai-shared` network.

| MCP | Port | Status | Tools |
| --- | ---- | ------ | ----- |
| context7 | :7008 | ✅ Running | 2 |
| qdrant-mcp (4 named servers x find/store) | :7020 | ✅ Running | 8 |
| memory (singleton — shared by both gateways to prevent write races) | :7040 | ✅ Running | 8 |
| kapture-server (WebSocket bridge for Chrome extension) | :61822 (WS) | ✅ Running | — |
| playwright | :7007 | ⬚ Available | 15+ |
| browser-use | :7011 | ⬚ Available | 10+ |
| hass-mcp | :7010 | ⬚ Available | 5+ |

### Platform Services

| Service | Compose Path | Status | Ports |
| ------- | ------------ | ------ | ----- |
| Watchtower (label-based auto image updates) | `platform/watchtower/` | ✅ Running | — |
| Langfuse (LLM observability, prompts, evals) | `platform/langfuse/` | ⬚ Available | :3100 (UI), :3101 (MCP auth proxy) |
| Observability (Prometheus, Grafana, Jaeger, OTel Collector) | `platform/observability/` | ⬚ Available | :9090, :3000, :16686 |

## Network Architecture

### Docker Networks

| Network | Type | Purpose | Services |
| ------- | ---- | ------- | -------- |
| `ai-shared` | External | Hub network for all shared MCPs, backing services, and observability | Both gateways, all standalone MCPs, qdrant, watchtower, langfuse (web/worker/proxy), observability stack |
| `agentgateway_default` | Stack-private | Isolates agentgateway's stdio-proxy from DNS collisions | agentgateway, nginx-proxy, stdio-proxy, mcp-status |
| `mcpx_default` | Stack-private | Isolates mcpx's stdio-proxy from DNS collisions | mcpx, nginx-ssl, stdio-proxy, mcp-status |
| `context-lens_default` | Implicit | Context Lens + mitmproxy internal communication | context-lens, mitmproxy |
| `langfuse-internal` | Stack-private | Isolates Langfuse storage (postgres, redis, clickhouse, minio) | langfuse-postgres, langfuse-redis, langfuse-clickhouse, langfuse-minio |

Both gateway services (agentgateway, mcpx) join **two** networks: their stack's private `default` (to reach their own stdio-proxy) and `ai-shared` (to reach shared MCPs). This is why stdio-proxy is included as a compose template rather than run as a shared service — each stack gets its own instance on its own network.

### Internal Docker Traffic (ai-shared)

| From | To | Port | Purpose |
| ---- | -- | ---- | ------- |
| agentgateway / mcpx | context7_mcp | 7008 | Library docs MCP |
| agentgateway / mcpx | qdrant-mcp | 7020 | Semantic search MCP |
| agentgateway / mcpx | memory_mcp | 7040 | Knowledge graph MCP (singleton) |
| agentgateway / mcpx | stdio-proxy (own stack) | 7030 | stdio MCPs (private network) |
| qdrant-mcp | qdrant | 6333 | Vector DB queries |
| agentgateway | otel-collector | 4317 | OTLP traces |
| otel-collector | jaeger | 14317 | Trace export |
| otel-collector | (self) | 8889 | Span metrics |
| prometheus | agentgateway | 15020 | Metrics scrape |
| prometheus | otel-collector | 8889 | Span metrics scrape |
| grafana | prometheus | 9090 | Metrics queries |
| grafana | jaeger | 16686 | Trace queries |
| mitmproxy | context-lens | 4041 | POST captures to ingest API |

## Directory Structure

```text
ai-infrastructure/
├── clients/           # AI client configurations
│   ├── claude/        # Claude Desktop config
│   ├── cline/         # Cline config
│   └── copilot/       # VS Code Copilot config
├── gateways/          # MCP gateways
│   └── agentgateway/  # Linux Foundation MCP gateway
├── mcps/              # MCP servers
│   ├── browser-use/   # AI browser automation
│   ├── context7/      # Library documentation
│   ├── hass-mcp/      # Home Assistant
│   ├── kapture/       # Chrome extension MCP
│   ├── mcpx/          # MCPX gateway (alternative)
│   ├── memory/        # Memory/knowledge graph
│   ├── playwright/    # Playwright browser automation
│   ├── qdrant-mcp/    # Qdrant semantic search (mcp-proxy + mcp-server-qdrant)
│   ├── sequential-thinking/ # Chain of thought reasoning
│   └── stdio-proxy/   # stdio→SSE bridge
├── platform/          # Platform services
│   ├── context-lens/  # LLM context window inspector
│   ├── langfuse/      # LLM observability, prompts, evals
│   └── observability/ # Prometheus, Grafana, Jaeger
└── workflows/         # Custom workflow definitions
```

## Components

### Gateways

| Gateway | Description | Status |
| ------- | ----------- | ------ |
| [agentgateway](gateways/agentgateway/readme.md) | Linux Foundation MCP gateway — routes to 10+ backends, stateless SSE, CORS, OTLP traces | ✅ Running |
| [mcpx](mcps/mcpx/) | Lunar.dev MCP gateway — tool grouping, per-consumer auth/RBAC, control plane UI | ✅ Running |

### MCP Servers

Standalone MCPs run as their own containers on `ai-shared`. stdio MCPs run inside per-stack stdio-proxy instances.

| MCP | Type | Description | Status | Docs |
| --- | ---- | ----------- | ------ | ---- |
| [context7](mcps/context7/readme.md) | Standalone | Library documentation lookup | ✅ Running | [→](mcps/context7/readme.md) |
| [qdrant-mcp](mcps/qdrant-mcp/README.md) | Standalone | Vector RAG — multi-collection routing (notes, code, etc. by scope). Includes watcher sidecars for auto-reindex. | ✅ Running | [→](mcps/qdrant-mcp/README.md) |
| [memory](mcps/memory/readme.md) | Standalone | Knowledge graph (singleton shared by both gateways) | ✅ Running | [→](mcps/memory/readme.md) |
| [sequential-thinking](mcps/sequential-thinking/readme.md) | stdio | Chain of thought reasoning | ✅ Running | [→](mcps/sequential-thinking/readme.md) |
| [kapture](mcps/kapture/readme.md) | stdio | Chrome extension bridge | ✅ Running | [→](mcps/kapture/readme.md) |
| [stdio-proxy](mcps/stdio-proxy/readme.md) | Template | stdio→SSE bridge (included by gateway stacks) | ✅ Running | [→](mcps/stdio-proxy/readme.md) |
| [playwright](mcps/playwright/readme.md) | Standalone | Browser automation | ⬚ Available | [→](mcps/playwright/readme.md) |
| [browser-use](mcps/browser-use/readme.md) | Standalone | AI browser automation | ⬚ Available | [→](mcps/browser-use/readme.md) |
| [hass-mcp](mcps/hass-mcp/readme.md) | Standalone | Home Assistant | ⬚ Available | [→](mcps/hass-mcp/readme.md) |

### Platform Services

| Service | Description | Status | Docs |
| ------- | ----------- | ------ | ---- |
| [Context Lens](platform/context-lens/README.md) | LLM API interception proxy + context window analysis UI | ✅ Running | [→](platform/context-lens/README.md) |
| [Watchtower](platform/watchtower/) | Label-based auto image updates (24h poll) | ✅ Running | [→](platform/watchtower/) |
| [Observability](platform/observability/readme.md) | Prometheus, Grafana, Jaeger, OTel Collector | ⬚ Available | [→](platform/observability/readme.md) |
| [Langfuse](platform/langfuse/README.md) | LLM observability, prompts, evals (includes postgres, redis, clickhouse, minio) | ⬚ Available | [→](platform/langfuse/README.md) |

### Clients

See [clients/readme.md](clients/readme.md) for configuration.

| Client | Config |
| ------ | ------ |
| VS Code Copilot | [copilot/](clients/copilot/) |
| Claude Desktop | [claude/](clients/claude/) |
| Cline | [cline/](clients/cline/) |

### Host-side Code Tools

These are NOT part of the Compose stack — they install on the host directly (CLI + Claude Code skill) but complement the in-stack services:

| Tool | Type | Role | Status |
| ---- | ---- | ---- | ------ |
| [graphify](https://github.com/safishamsi/graphify) | CLI + MCP + Claude skill | Structural code-graph (Tree-sitter AST → call/dep graph, community detection). Complements qdrant code collections — structural queries vs semantic similarity. Supports dual-mode deployment: workspace graph for coupled repo clusters + per-repo graphs for standalone repos. See [graphify-workspace-setup.md](docs/graphify-workspace-setup.md) for full setup. | ✅ Available via `uv tool install graphifyy` |

## Quick Start

### 1. Create shared Docker network

```bash
docker network create ai-shared
```

**Note**: The `ai-shared` network is created by the first stack that defines it. This step is only needed if you want to start stacks in a different order.

### 2. Start mcpx gateway

```bash
cd mcps/mcpx
cp .env.example .env   # Edit: set MCP_CONFIG, optionally CUSTOM_CA_CERT
docker compose up -d
```

### 3. Start agentgateway

```bash
cd gateways/agentgateway
docker compose up -d
```

### 4. Start Qdrant + semantic search MCP

```bash
cd mcps/qdrant-mcp
# Set vault + repos paths from local config (used by watcher sidecars)
export VAULT_PATH="$(yq '.obsidian.vault_path' ~/ai/local.yaml)"
export REPOS_BASE="$(yq '.repos.base_path' ~/ai/local.yaml)"
docker compose up -d --build
```

Brings up: `qdrant` (vector DB) + `qdrant-mcp` (MCP proxy) + watcher sidecars (`obsidian-watcher`, optional `repo-watcher-*` per scope) for auto-reindex. See [qdrant-mcp README](mcps/qdrant-mcp/README.md) for multi-collection routing and watcher configuration.

### 5. (Optional) Install graphify for structural code queries

```bash
uv tool install graphifyy
graphify install                  # Register as a Claude Code skill / MCP
graphify <path> --no-viz --directed   # Build an initial graph from any repo or workspace
graphify hook install             # Inside each repo: auto-rebuild on commit
```

Complements qdrant code collections — see [graphify](https://github.com/safishamsi/graphify) for the full CLI surface.

### 6. Start Context Lens (LLM traffic analysis)

```bash
cd platform/context-lens
docker compose up -d
```

Then set `ANTHROPIC_BASE_URL=http://127.0.0.1:4040/claude` in your shell profile or VS Code settings. See [Context Lens README](platform/context-lens/README.md#client-configuration) for per-client setup.

### 7. Start observability stack (optional)

```bash
cd platform/observability
docker compose up -d
```

### 8. Start Langfuse (optional)

```bash
cd platform/langfuse
docker compose up -d
```

### 9. Access

| Service | URL |
| ------- | --- |
| agentgateway MCP | `http://localhost:3847/mcp` |
| agentgateway Admin UI | `http://localhost:15001/ui` |
| mcpx MCP | `http://localhost:9000/mcp` |
| mcpx Control Plane | `http://localhost:5173` |
| Context Lens | `http://localhost:4041` |
| Grafana | `http://localhost:3000` (admin/admin) |
| Langfuse | `http://localhost:3100` (create account on first visit) |

### 10. Configure your AI client

See [clients/](clients/) for configuration examples for each AI client.

## Ports

Single sorted reference. `Stack` is the compose project the port belongs to; internal-only ports are marked in **Notes**.

| Port | Protocol | Service | Stack | Notes |
| ----:| -------- | ------- | ----- | ----- |
| 3000 | HTTP | Grafana | observability | Dashboards (admin/admin) |
| 3100 | HTTP | Langfuse | langfuse | LLM observability UI |
| 3100 | Prometheus | mcpx | mcpx | Metrics (remapped from container :3000) — **conflicts with Langfuse :3100** |
| 3101 | HTTP | langfuse-mcp-proxy | langfuse | MCP auth proxy for agentgateway |
| 3443 | HTTPS | nginx-proxy | agentgateway | TLS-wrapped MCP + SSE |
| 3847 | HTTP/MCP | agentgateway | agentgateway | **Main MCP endpoint** |
| 4040 | HTTP | context-lens | context-lens | Reverse proxy (clients set `ANTHROPIC_BASE_URL`) |
| 4041 | HTTP | context-lens | context-lens | Web UI + ingest API |
| 4317 | gRPC | OTel Collector | observability | OTLP (internal, Docker network) |
| 4318 | HTTP | OTel Collector | observability | OTLP (internal, Docker network) |
| 5173 | HTTP | mcpx | mcpx | Control Plane dashboard |
| 5175 | HTTP | context-lens | context-lens | Vite dev server (dev mode only, remapped from 5173) |
| 5443 | HTTPS | nginx-ssl | mcpx | TLS-wrapped Control Plane |
| 6333 | HTTP | qdrant | qdrant-mcp | Vector DB REST API |
| 6334 | gRPC | qdrant | qdrant-mcp | Vector DB gRPC API |
| 7007 | SSE/MCP | playwright | shared MCP | Standalone container (`mcps/playwright/`) — available |
| 7008 | HTTP/MCP | context7 | shared MCP | Library documentation MCP |
| 7010 | HTTP | hass-mcp | shared MCP | Home Assistant MCP — available |
| 7011 | SSE/MCP | browser-use | shared MCP | AI browser automation — available |
| 7020 | HTTP | qdrant-mcp | qdrant-mcp | Semantic search MCP |
| 7030 | HTTP | stdio-proxy | per-gateway | **Internal only** — stdio→SSE bridge inside each gateway stack |
| 7040 | HTTP | memory | shared MCP | Knowledge graph MCP (singleton) |
| 8000 | HTTP | lunar-proxy | mcpx | API gateway (not actively routed) |
| 8040 | HTTP | lunar-proxy | mcpx | Health check |
| 8080 | HTTP | mitmproxy | context-lens | HTTPS forward proxy (Copilot, Codex, etc.) |
| 8081 | HTTP | lunar-proxy | mcpx | Admin |
| 8889 | Prometheus | OTel Collector | observability | Span metrics (internal) |
| 9000 | HTTP/MCP | mcpx | mcpx | **Main MCP endpoint** (SSE + streamable HTTP) |
| 9001 | HTTP | mcpx | mcpx | Internal webserver |
| 9090 | HTTP | Prometheus | observability | Metrics UI & API |
| 9190 | HTTP | Langfuse MinIO | langfuse | S3-compatible object storage |
| 9222 | CDP | nginx-ssl | mcpx | Reverse proxy → host Chrome :9222 |
| 9223 | CDP | nginx-proxy | agentgateway | Reverse proxy → host Chrome :9222 |
| 9443 | HTTPS | nginx-ssl | mcpx | TLS-wrapped MCP + SSE |
| 15001 | HTTP | agentgateway | agentgateway | Admin UI (playground & config; internal :15000) |
| 15020 | Prometheus | agentgateway | agentgateway | Metrics endpoint |
| 15443 | HTTPS | nginx-proxy | agentgateway | TLS-wrapped Admin UI |
| 16686 | HTTP | Jaeger | observability | Trace visualization UI |
| 61822 | WebSocket | kapture-server | shared MCP | Chrome-extension bridge (standalone container; previously served by mcpx nginx-ssl) |

## Observability

The observability stack provides metrics, tracing, and visualization:

| Component | Port | Purpose |
| --------- | ---- | ------- |
| agentgateway Admin UI | [:15001](http://localhost:15001/ui) | Admin UI with playground |
| agentgateway Metrics | [:15020](http://localhost:15020/metrics) | Prometheus metrics endpoint |
| Prometheus | [:9090](http://localhost:9090) | Metrics storage and queries |
| Grafana | [:3000](http://localhost:3000) | Dashboards (admin/admin) |
| Jaeger | [:16686](http://localhost:16686) | Distributed tracing |
| Langfuse | [:3100](http://localhost:3100) | LLM observability & prompts |
| OpenTelemetry Collector | :4317/:4318 (internal) | Trace processing & span metrics |

**Trace Flow:**

```text
agentgateway → OTel Collector → Jaeger (traces)
                             → Prometheus (span metrics)
```

**Metrics include:**

- `agentgateway_requests_total` - HTTP requests by client, method, status
- `agentgateway_mcp_requests` - MCP tool calls
- `tool_calls_total` - Tool calls by server and tool name
- `list_calls_total` - List operations
- Span-derived metrics (latency histograms, call counts) from OTel Collector

## TODO

- [ ] Fix langfuse-prompts MCP backend - Langfuse stack (:3101) not running; agentgateway fails to initialize when this upstream is unreachable. Need to either ensure langfuse starts with the gateway or handle gracefully.
- [ ] Fix obsidian MCP backend - Obsidian semantic plugin (:3001) not running; same issue as langfuse. Need to either auto-start or make the gateway tolerant of missing optional backends.
- [ ] Evaluate using agentgateway's native TLS instead of nginx-proxy for HTTPS termination
- [ ] Configure Playwright MCP with CDP proxy (nginx-proxy on 9223 needed for browser-use MCPs to connect to host Chrome)
- [ ] Recreate remaining containers with Watchtower labels (agentgateway, playwright, qdrant, observability stack) — labels added to compose files but containers need `docker compose up -d --force-recreate` to pick them up
- [x] Add client identification headers for per-client tracking
- [x] Set up Jaeger for distributed tracing
- [x] Configure agentgateway to send traces to OpenTelemetry Collector
- [x] Create Grafana dashboard for metrics visualization
- [x] Set up Langfuse for LLM observability and prompt management

## Workflows

### Fork Contribution: Cherry-Pick Staged Changes

Used for contributing to upstream open-source projects (e.g., Context Lens). Maintains a local `main` with all in-flight fixes applied while each fix lives on its own branch as a separate PR to upstream.

```
upstream/main ← PRs from your fork branches
    ↑
origin/main (your fork, tracks upstream)
    ↑
local main (staged cherry-picks from all active branches)
    ↑
┌───┴───┬──────────┬──────────┐
fix/a   fix/b   feat/c   fix/d    ← worktree branches, each = 1 PR
```

**Key invariant**: Local `main` is never committed ahead of `origin/main`. All local-only changes live as **staged but uncommitted** cherry-picks.

**Develop** on worktree branches (each branch = one PR):

```bash
git worktree add ../repo-fix-foo fix/foo
cd ../repo-fix-foo
# ... make changes, commit, push ...
git push origin fix/foo   # open PR against upstream/main
```

**Stack** changes on local main:

```bash
git checkout main
git cherry-pick --no-commit origin/main..<branch-name>
# Repeat for each active branch — all fixes are now applied but uncommitted
```

**Sync** with upstream (chain: upstream → origin/main → branches):

```bash
git stash push -m "staged cherry-picks"
git checkout main && git fetch --all
git rebase upstream/main
git push origin main                    # --force-with-lease if rebased

# Rebase active branches onto synced main
git rebase main fix/still-open-a
git push --force-with-lease origin fix/still-open-a

# Rebuild staged state from remaining open branches
git checkout main
git cherry-pick --no-commit origin/main..fix/still-open-a
git stash drop
```

**Switch machines** — clone fork, fetch, cherry-pick open branches:

```bash
git clone <fork-url> && cd repo
git remote add upstream <upstream-url>
git fetch --all && git rebase upstream/main
git cherry-pick --no-commit origin/main..origin/fix/branch-a
git cherry-pick --no-commit origin/main..origin/fix/branch-b
```

**Tips**:
- `git branch --no-merged origin/main` — list branches that still need cherry-picking
- `git diff --cached --stat` — see your current cherry-pick stack
- `git restore --staged .` — abort and rebuild if staged state gets messy

See [Context Lens workflow details](docs/context-lens-cherry-pick-workflow.md) for project-specific branch status and machine resume recipes.

## Platform-Specific Setup

- **[Windows](docs/windows-setup.md)** — WSL repo locations, cross-filesystem gotchas, SSH keys, Docker Desktop specifics

## Resources

- [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro)
- [agentgateway](https://agentgateway.dev/docs/)
- [agentgateway Observability](https://agentgateway.dev/docs/reference/observability/metrics/)
- [Langfuse](https://langfuse.com/docs)
- [mcpx / Lunar.dev](https://docs.lunar.dev/mcpx/architecture)
- [Context Lens](https://github.com/larsderidder/context-lens)

