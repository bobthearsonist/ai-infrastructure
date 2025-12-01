# AI Infrastructure

Central infrastructure for AI tools, MCP servers, gateways, and platform services.

## Architecture

```plantuml
@startuml ai-infrastructure
!theme plain
skinparam backgroundColor #FEFEFE
skinparam componentStyle rectangle
skinparam defaultFontName Consolas

title AI Infrastructure Architecture

' === AI Clients ===
package "AI Clients" as clients #E3F2FD {
  [VS Code Copilot] as vscode
  [Claude Desktop] as claude
  [Cline] as cline
  [Other Clients] as other
}

' === Gateway Layer ===
package "Gateway Layer" as gateway_layer #E8F5E9 {
  component "agentgateway\n:3847 (HTTP)\n:15000 (Admin UI)" as agentgateway #C8E6C9
  component "nginx-proxy\n:3443 (HTTPS)\n:9223 (CDP)" as nginx #A5D6A7
}

' === MCP Backends - Currently Running ===
package "Running MCPs" as running #FFF3E0 {
  component "stdio-proxy\n:7030 (SSE)\n:61822 (Kapture WS)" as stdio_proxy #FFCC80

  package "stdio MCPs" as stdio_mcps #FFE0B2 {
    [sequential-thinking\n(1 tool)] as seq_think
    [memory\n(8 tools)] as memory
    [kapture\n(15+ tools)] as kapture_mcp
  }
}

' === MCP Backends - Planned ===
package "Planned MCPs" as planned #ECEFF1 {
  [context7\n:7008] as context7 #CFD8DC
  [playwright\n:7007] as playwright #CFD8DC
  [browser-use\n:7011] as browser_use #CFD8DC
  [hass-mcp\n:7010] as hass_mcp #CFD8DC
  [langfuse-mcp\n:7012 (prompts)] as langfuse_mcp #CE93D8
}

' === Platform Services ===
package "Platform Services (Planned)" as platform #F3E5F5 {
  [Langfuse\n:3000 (UI/API)] as langfuse #CE93D8
}

' === Connections ===
' Clients to Gateway
vscode --> agentgateway : HTTP
claude --> agentgateway : HTTP
cline --> agentgateway : HTTP
other --> nginx : HTTPS

' nginx to agentgateway
nginx --> agentgateway : proxy

' agentgateway to MCPs
agentgateway --> stdio_proxy : SSE
agentgateway ..> context7 : SSE (planned)
agentgateway ..> playwright : SSE (planned)
agentgateway ..> browser_use : SSE (planned)
agentgateway ..> hass_mcp : SSE (planned)
agentgateway ..> langfuse_mcp : SSE (planned)

' stdio-proxy to stdio MCPs
stdio_proxy --> seq_think : stdio
stdio_proxy --> memory : stdio
stdio_proxy --> kapture_mcp : stdio

' Langfuse MCP to Langfuse platform
langfuse_mcp ..> langfuse : API (planned)

' Legend
legend right
  |= Color |= Status |
  | <#C8E6C9> | Gateway |
  | <#FFCC80> | Running |
  | <#CFD8DC> | Planned MCP |
  | <#CE93D8> | Planned Platform |
endlegend

@enduml
```

## Current Status

| Component | Status | Tools |
| --------- | ------ | ----- |
| agentgateway | ✅ Running | - |
| sequential-thinking | ✅ Running | 1 |
| memory | ✅ Running | 8 |
| kapture | ✅ Configured | 15+ |
| **Total** | | **24+ tools** |

## Network Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│ HOST                                                                │
│                                                                     │
│   Chrome ─────────────────────────┐                                 │
│     ├─ Kapture Extension ─────────┼─── ws://localhost:61822 ────┐   │
│     └─ DevTools (:9222) ◄─────────┼─── (CDP from containers) ◄──┼─┐ │
│                                   │                             │ │ │
│   AI Clients ─────────────────────┼─── http://localhost:3847 ───┼─┼─┤
│                                   │                             │ │ │
└───────────────────────────────────┼─────────────────────────────┼─┼─┘
                                    │                             │ │
┌───────────────────────────────────┼─────────────────────────────┼─┼─┐
│ DOCKER                            │                             │ │ │
│                                   ▼                             │ │ │
│   ┌─────────────────────────────────────────────────────────┐   │ │ │
│   │ stdio-proxy                                             │   │ │ │
│   │   :7030 (SSE) ◄── agentgateway                          │◄──┘ │ │
│   │   :61822 (WS) ◄── Kapture extension connects here       │     │ │
│   └─────────────────────────────────────────────────────────┘     │ │
│                                                                   │ │
│   ┌─────────────────────────────────────────────────────────┐     │ │
│   │ agentgateway :3847 ◄──────────────────────────────────────────┘ │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │ nginx-proxy                                             │       │
│   │   :9223 ──► host.docker.internal:9222 (CDP to Chrome) ──────────┘
│   │   :3443 ──► agentgateway:3847 (HTTPS termination)       │
│   └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────┘

Connection directions:
  ──►  Outbound (container → host) - needs proxy
  ◄──  Inbound (host → container) - direct port exposure
```

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
│   ├── browser-use/   # Browser automation (planned)
│   ├── context7/      # Context7 (planned)
│   ├── hass-mcp/      # Home Assistant (planned)
│   ├── kapture/       # Chrome extension MCP (planned)
│   ├── mcpx/          # MCPX gateway (alternative)
│   ├── memory/        # Memory/knowledge graph
│   ├── playwright/    # Playwright browser automation
│   ├── sequential-thinking/ # Chain of thought reasoning
│   └── stdio-proxy/   # stdio→SSE bridge
├── services/          # Platform services
│   └── langfuse/      # LLM observability & prompts (planned)
└── workflows/         # Custom workflow definitions
```

## Components

### Gateways

| Gateway | Description | Status |
| ------- | ----------- | ------ |
| [agentgateway](gateways/agentgateway/readme.md) | Linux Foundation MCP gateway with auth, RBAC, rate limiting | ✅ Running |

### MCP Servers

| MCP | Description | Status | Docs |
| --- | ----------- | ------ | ---- |
| [sequential-thinking](mcps/sequential-thinking/readme.md) | Chain of thought reasoning | ✅ Running | [→](mcps/sequential-thinking/readme.md) |
| [memory](mcps/memory/readme.md) | Knowledge graph & memory | ✅ Running | [→](mcps/memory/readme.md) |
| [stdio-proxy](mcps/stdio-proxy/readme.md) | stdio→SSE bridge (mcp-proxy) | ✅ Running | [→](mcps/stdio-proxy/readme.md) |
| [playwright](mcps/playwright/readme.md) | Browser automation | ⏳ Planned | [→](mcps/playwright/readme.md) |
| [kapture](mcps/kapture/readme.md) | Chrome extension MCP | ⏳ Planned | [→](mcps/kapture/readme.md) |
| browser-use | AI browser automation | ⏳ Planned | - |
| context7 | Context7 library docs | ⏳ Planned | - |
| hass-mcp | Home Assistant | ⏳ Planned | - |

### Platform Services

| Service | Description | Status | Docs |
| ------- | ----------- | ------ | ---- |
| [Langfuse](services/langfuse/readme.md) | LLM observability, prompts, evals | ⏳ Planned | [→](services/langfuse/readme.md) |

### Clients

See [clients/readme.md](clients/readme.md) for configuration.

| Client | Config |
| ------ | ------ |
| VS Code Copilot | [copilot/](clients/copilot/) |
| Claude Desktop | [claude/](clients/claude/) |
| Cline | [cline/](clients/cline/) |

## Quick Start

### 1. Create Docker network

```bash
docker network create mcpx_ai-infrastructure
```

### 2. Start stdio-proxy (for stdio-based MCPs)

```bash
cd mcps/stdio-proxy
docker-compose up -d
```

### 3. Start agentgateway

```bash
cd gateways/agentgateway
docker-compose up -d
```

### 4. Access

- **MCP Endpoint**: `http://localhost:3847/mcp`
- **Admin UI**: `http://localhost:15001/ui`

### 5. Configure your AI client

See [clients/](clients/) for configuration examples for each AI client.

## Ports

| Port | Service | Protocol |
| ---- | ------- | -------- |
| 3847 | agentgateway MCP | HTTP |
| 15001 | agentgateway Admin UI | HTTP |
| 3443 | agentgateway MCP (SSL) | HTTPS |
| 7030 | stdio-proxy | SSE |
| 61822 | Kapture WebSocket | WebSocket |
| 3000 | Langfuse (planned) | HTTP |

## TODO

- [ ] Evaluate using agentgateway's native TLS instead of nginx-proxy for HTTPS termination
- [ ] Keep nginx-proxy for CDP proxy (9223) - needed for Playwright/browser-use MCPs to connect to host Chrome

## Resources

- [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro)
- [agentgateway](https://agentgateway.dev/docs/)
- [Langfuse](https://langfuse.com/docs)

