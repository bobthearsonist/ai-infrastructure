# MCPX

MCP gateway by [Lunar.dev](https://docs.lunar.dev/mcpx/architecture). Single entrypoint for multiple MCP backends; `mcp.json` controls what mcpx **connects to**, `app.yaml` controls what it **exposes** per consumer.

📖 [Lunar docs](https://docs.lunar.dev/) · [Architecture](https://docs.lunar.dev/mcpx/architecture) · [Changelog](https://github.com/TheLunarCompany/lunar/blob/main/mcpx/CHANGELOG.md)

## Status

Image: `us-central1-docker.pkg.dev/prj-common-442813/mcpx/mcpx:latest` (0.4.x line; identity mode `personal`). Surfaces 136 tools across 10 backends as of last verification.

## Endpoints

| Use                  | HTTP                         | HTTPS                       |
| -------------------- | ---------------------------- | --------------------------- |
| MCP (SSE + HTTP)     | `localhost:9000/{sse,mcp}`   | `localhost:9443/{sse,mcp}`  |
| Control Plane UI     | `localhost:5173/dashboard`   | `localhost:5443`            |
| Metrics (Prometheus) | `localhost:3100`             | —                           |

## Backends (mcp.json)

| Server                | Group              | Transport         | URL / Source                                                  |
| --------------------- | ------------------ | ----------------- | ------------------------------------------------------------- |
| sequential-thinking   | core               | stdio (local npx) | spawned by mcpx                                               |
| memory                | core               | stdio (local npx) | spawned by mcpx                                               |
| kapture               | browser            | stdio (local npx) | spawned by mcpx                                               |
| context7              | coding             | streamable-http   | `host.docker.internal:7008/mcp`                               |
| qdrant-work           | knowledge-work     | SSE               | `host.docker.internal:7020/servers/qdrant-work/sse`           |
| qdrant-code           | knowledge-code     | SSE               | `host.docker.internal:7020/servers/qdrant-code/sse`           |
| qdrant-personal       | knowledge-personal | SSE               | `host.docker.internal:7020/servers/qdrant-personal/sse`       |
| hass-mcp              | homelab            | SSE               | `mcpx-stdio-proxy:7030/servers/hass-mcp/sse` (uvx via proxy)  |
| photoshop             | creative           | SSE               | `mcpx-stdio-proxy:7030/servers/photoshop/sse` (uvx via proxy) |
| playwright            | browser            | SSE               | `mcp_playwright:7007/sse`                                     |
| browser-use           | —                  | (disabled)        | in `_disabledMcpServers`                                      |

## Tool groups (app.yaml)

| Group              | Tools allowed to | Servers                       |
| ------------------ | ---------------- | ----------------------------- |
| core               | all consumers    | sequential-thinking, memory   |
| coding             | all consumers    | context7                      |
| knowledge-work     | all consumers    | qdrant-work                   |
| knowledge-code     | all consumers    | qdrant-code                   |
| knowledge-personal | all consumers    | qdrant-personal               |
| devops             | all consumers    | azure-devops (not configured) |
| diagrams           | all consumers    | mermaid (not configured)      |
| homelab            | all consumers    | hass-mcp                      |
| browser            | all consumers    | playwright, kapture           |
| creative           | all consumers    | photoshop                     |

## Configuration

| File                 | Purpose                                                                       |
| -------------------- | ----------------------------------------------------------------------------- |
| `mcp.json`           | Backends to connect to. Bind-mounted; restart mcpx after edits.               |
| `app.yaml`           | Tool groups + per-consumer `allow` lists. Bind-mounted; restart mcpx.         |
| `docker-compose.yml` | Orchestration. `include:`s `mcps/stdio-proxy/docker-compose.yml`.             |
| `nginx.conf`         | HTTPS termination via sidecar (only if you actually serve TLS).               |
| `.env`               | Optional `MCP_CONFIG`, `CUSTOM_CA_CERT` overrides.                            |

## Operational notes

- **Two-layer visibility gate.** A backend in `mcp.json` but missing from a `toolGroups` entry, OR in a group not in the consumer's `allow` list, gets **silently dropped** from `tools/list` — no error at INFO. mcpx will still log `Client connected` + `UpstreamHandler initialized count=N`, which is misleading.
- **0.2.x → 0.4.x is a behavioral regression for permissive setups.** Older mcpx exposed everything in mcp.json. The gate is new. See memory note `reference_mcpx_permissions_gate` memory for the full diagnostic recipe.
- **`mcpx-stdio-proxy` is a deliberate compose alias**, not the auto-generated `stdio-proxy` (which collides with agentgateway's stdio-proxy on ai-shared). See memory note `reference_mcp_router_architecture` memory.
- **Diagnostic shortcut.** Set `LOG_LEVEL=debug` in compose env, restart; the first log line after startup is `Config loaded successfully permissions=... toolGroups=...` — the full parsed view. Revert to default after.
- **Hub strictness gate is separate** (`STRICTNESS_REQUIRED` env). Defaults `false` for personal mode and doesn't affect us. Watch for `NotAllowedError: Server "X" is not in catalog` if it ever flips on.

## Adding a backend

1. Add entry to `mcp.json` → `mcpServers`.
2. Add it to a `toolGroups` entry in `app.yaml`. If new group, add the group name to `permissions.default.allow` and any consumer's `allow` that needs it.
3. `docker compose restart mcpx`. Verify with `docker logs mcpx --tail 50 | grep -E "UpstreamHandler initialized|<your-name>"`.

## HTTPS (optional)

The `nginx-ssl` sidecar terminates TLS on `:9443` / `:5443`. Needs certs at `./certs/tls/{cert,key}.pem`:

```bash
mkdir -p certs/tls
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/tls/key.pem -out certs/tls/cert.pem \
  -subj "/CN=localhost"
```

## TODO

- [ ] Configure authentication (API key or OAuth)
- [ ] Test disconnection-safe caching with OpenCode
- [ ] Set up consumer tags for per-client metrics
- [ ] Compare to Atrax and MetaMCP as alternatives

## See also

- [stdio-proxy](../stdio-proxy/readme.md) — uvx/npx subprocess host, included by this stack
- [agentgateway](../../gateways/agentgateway/readme.md) — sibling MCP gateway (Linux Foundation, more enterprise features)
- [TheLunarCompany/lunar](https://github.com/TheLunarCompany/lunar)
