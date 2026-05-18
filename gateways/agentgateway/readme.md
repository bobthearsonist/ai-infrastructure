# agentgateway

Open-source MCP gateway from the Linux Foundation. Federates multiple MCP backends behind one endpoint via a multiplexed `mcp:` route in `config.yaml`.

📖 [Docs](https://agentgateway.dev/docs/) · 🔗 [GitHub](https://github.com/agentgateway/agentgateway) · [Multiplexing](https://agentgateway.dev/docs/mcp/connect/multiplex/)

## Status

Image: `ghcr.io/agentgateway/agentgateway:latest` (watchtower-enabled). Lazy initialization — backends only connect on first MCP client request. Tool names are prefixed with the target name (e.g., `context7_resolve-library-id`).

## Endpoints

| Use                  | HTTP                       | HTTPS                  |
| -------------------- | -------------------------- | ---------------------- |
| MCP                  | `localhost:3847/mcp`       | `localhost:3443/mcp`   |
| Admin UI             | `localhost:15001/ui`       | `localhost:15443`      |
| Metrics (Prometheus) | `localhost:15020`          | —                      |
| CDP proxy            | containers → host:9222     | `localhost:9223`       |

## Backends (config.yaml)

All targets live inside one `backends[0].mcp.targets` array (single block — see operational notes).

| Target                      | Transport       | URL                                                                |
| --------------------------- | --------------- | ------------------------------------------------------------------ |
| sequential-thinking         | SSE             | `agentgateway-stdio-proxy:7030/servers/sequential-thinking/sse`    |
| kapture                     | SSE             | `agentgateway-stdio-proxy:7030/servers/kapture/sse`                |
| azure-devops                | SSE             | `agentgateway-stdio-proxy:7030/servers/azure-devops/sse`           |
| memory                      | SSE             | `memory_mcp:7040/servers/memory/sse`                               |
| qdrant-{work,personal,code} | SSE             | `qdrant-mcp:7020/servers/qdrant-*/sse`                             |
| context7                    | streamable-http | `context7_mcp:7008/mcp`                                            |
| playwright                  | SSE             | `host.docker.internal:7007/sse`                                    |
| hass-mcp                    | SSE             | `agentgateway-stdio-proxy:7030/servers/hass-mcp/sse`               |
| browser-use                 | SSE (disabled)  | `host.docker.internal:7011/sse`                                    |

## Configuration

| File                 | Purpose                                                                  |
| -------------------- | ------------------------------------------------------------------------ |
| `config.yaml`        | Listeners, backends (single `mcp:` block), routes. xDS-hot-reloadable in theory. |
| `docker-compose.yml` | Orchestration. `include:`s `mcps/stdio-proxy/docker-compose.yml`.        |
| `nginx.conf`         | HTTPS termination + CDP proxy (9223 → host:9222) for playwright/browser-use. |
| `memory.json`        | Persistent store for the `memory` MCP backend.                           |
| `certs/`             | TLS certs for the nginx sidecar (optional).                              |

## Operational notes

- **One `- mcp:` block. Always.** All MCP targets go in `backends[0].mcp.targets`. Adding a second `- mcp:` block **replaces** — only the last block's tools surface. The `backends` array is for distinct protocol classes (MCP / A2A / OpenAPI), not for separating MCP targets. (Source: `router.rs` — `McpBackendGroup` has a single `targets: Vec<...>`.)
- **`statefulMode: stateless` is required on the mcp block** when targets use SSE. SSE connections are short-lived HTTP GETs; closing the connection destroys the upstream session. Stateless mode auto-wraps every request with a fresh `initialize`. Without it, follow-up requests fail with *"Received request before initialization was complete."*
- **`resources/list` returns HTTP 500 in multiplexing mode** (any setup with >1 target). Expected, not a bug — URL mapping for resources across multiplexed targets isn't implemented. Tracking [agentgateway#404](https://github.com/agentgateway/agentgateway/issues/404). Tool discovery is unaffected.
- **`prompts/list` 500s are noise.** Some upstreams don't implement prompts. Ignore.
- **Hostname rule: no underscores.** agentgateway uses `hickory-dns` which is strict per RFC 1035 and rejects underscores in hostnames with `"Label contains invalid characters"`. Docker tolerates underscore-named containers fine, but agentgateway will fail to resolve them. Use the hyphen aliases that compose containers already declare (`memory-mcp` not `memory_mcp`, `context7-mcp` not `context7_mcp`).
- **All targets must initialize together.** A single 404 or DNS failure on ANY target aborts the entire multiplex init — the gateway returns 500 to every client request. If you see `backends required DNS resolution which failed` or upstream 404s, the bad target isn't named in the error — check the debug log (`docker logs agentgateway` filtered to non-otel lines) for the actual `client::dns resolution failed` or `upstream error` entry. Comment out broken targets until they're really fixed.
- **Three hostname patterns** in config.yaml URLs:
  - `agentgateway-stdio-proxy:7030/servers/<name>/sse` for stdio MCPs through the proxy (deliberate alias; the bare `stdio-proxy` alias collides on ai-shared; see memory note `reference_mcp_router_architecture`)
  - `<service>-mcp:<port>` for sibling HTTP services on ai-shared — *hyphenated, never underscored* (`memory-mcp`, `context7-mcp`, `qdrant-mcp`)
  - `host.docker.internal:<port>` for services that only publish to the host (e.g., `playwright` at 7007)
- **playwright needs `--allowed-hosts '*'`** on the playwright container (set in `mcps/playwright/docker-compose.yml`). Without it the server returns 403 to non-localhost Host headers.

## Adding a backend

1. Confirm reachability from inside the gateway container (use the appropriate hostname pattern above).
2. Add a single `- name: ... sse: host: ...` (or `mcp: host: ...` for streamable-http) entry to `backends[0].mcp.targets` in `config.yaml`. **Don't create a new `- mcp:` block.**
3. `docker compose restart agentgateway`.

## nginx-proxy sidecar

Custom (not part of agentgateway upstream). Provides HTTPS termination AND a CDP forwarder mapping `host.docker.internal:9223` → host's Chrome on `:9222`, letting containerized playwright/browser-use drive host Chrome.

> Kapture is the reverse direction — the Chrome extension on the host opens a WebSocket to the kapture-mcp container directly (port 61822). No nginx hop.

## TODO

- [ ] Add azure-devops MCP to stdio-proxy/servers.home.json and re-enable the target in config.yaml (commented out: stdio-proxy 404 was aborting all multiplex init)
- [ ] Make `config.yaml` per-machine-overridable (env-var-selected mount, matching the pattern stdio-proxy and mcpx use for their configs). Tracked in root [TODO.md](../../TODO.md) under "Conventions".
- [ ] Configure authentication (JWT/OAuth2)
- [ ] Set up CEL-based RBAC policies
- [ ] Configure rate limiting
- [ ] Set up xDS for hot-reload
- [ ] Restrict sequential-thinking MCP to local models only (hosted clients like Cline/Copilot have native chain-of-thought)
- [ ] Track upstream roadmap: <https://github.com/orgs/agentgateway/projects/1/views/1>

## See also

- [MCPX](../../mcps/mcpx/readme.md) — sibling MCP gateway (Lunar.dev; simpler but with its own `app.yaml` permissions gate)
- [stdio-proxy](../../mcps/stdio-proxy/readme.md) — stdio→SSE bridge for uvx/npx MCPs
- [Langfuse](../../platform/langfuse/README.md) — LLM observability
- [Client config](../../clients/) — how AI clients connect to the gateways
