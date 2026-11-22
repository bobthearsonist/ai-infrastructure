# MCPX

MCP gateway by [Lunar.dev](https://docs.lunar.dev/mcpx/architecture). Single entrypoint for multiple MCP backends; `mcp.json` controls what mcpx **connects to**, `app.yaml` controls what it **exposes** per consumer.

📖 [Lunar docs](https://docs.lunar.dev/) · [Architecture](https://docs.lunar.dev/mcpx/architecture) · [Changelog](https://github.com/TheLunarCompany/lunar/blob/main/mcpx/CHANGELOG.md)

## Status

Image: `us-central1-docker.pkg.dev/prj-common-442813/mcpx/mcpx:latest` (0.4.x line; identity mode `personal`). Surfaces 136 tools across 10 backends as of last verification.

## Endpoints

| Use                  | HTTP                         | HTTPS                       |
| -------------------- | ---------------------------- | --------------------------- |
| MCP (SSE + HTTP)     | `127.0.0.1:9000/{sse,mcp}`   | `localhost:9443/{sse,mcp}`  |
| Control Plane UI     | `127.0.0.1:15173/dashboard` (off by default, see Security) | not supported |
| Metrics (Prometheus) | `127.0.0.1:3100`             | —                           |

Everything is bound to `127.0.0.1`. The API on 9000/9443 requires the key. Metrics and the static UI files don't. The dashboard is on 15173, not mcpx's default 5173, because 5173 is Vite's default dev port. The HTTPS UI on 5443 can't work: its Origin isn't allowed.

## Connecting Claude Code

Claude Code connects natively over streamable HTTP (no `mcp-remote` bridge). The `x-lunar-consumer-tag` header selects the `claude-code` consumer in `app.yaml`. The `x-lunar-api-key` header is required (see Security below):

```bash
claude mcp add -t http -s user mcpx http://127.0.0.1:9000/mcp \
  -H "x-lunar-consumer-tag: claude-code" \
  -H "x-lunar-api-key: <AUTH_KEY from secrets/mcpx-auth.env>"
```

A client that reports `Dynamic Client Registration rejected ... Cannot POST /register` is missing or sending the wrong key: it got a 401 and fell back to OAuth discovery. Clients read their MCP config at startup, so restart them after changing it.

Use `127.0.0.1`, not `localhost`: on Windows with WSL, `localhost` resolves to `::1` first, where `wslrelay` holds `:9000` and resets the connection. Other clients: see [clients/](../../clients/readme.md).

## Backends (mcp.json)

| Server                | Group              | Transport         | URL / Source                                                  |
| --------------------- | ------------------ | ----------------- | ------------------------------------------------------------- |
| sequential-thinking   | core               | stdio (local npx) | spawned by mcpx                                               |
| memory                | core               | stdio (local npx) | spawned by mcpx                                               |
| kapture               | browser            | stdio (local npx) | spawned by mcpx                                               |
| context7              | coding             | streamable-http   | `host.docker.internal:7008/mcp`                               |
| qdrant-notes-work     | knowledge-notes-work  | SSE               | `host.docker.internal:7020/servers/qdrant-notes-work/sse`     |
| qdrant-code-work      | knowledge-code-work   | SSE               | `host.docker.internal:7020/servers/qdrant-code-work/sse`      |
| qdrant-code-public    | knowledge-code-public | SSE               | `host.docker.internal:7020/servers/qdrant-code-public/sse`    |
| qdrant-personal       | knowledge-personal | SSE               | `host.docker.internal:7020/servers/qdrant-personal/sse`       |
| hass-mcp              | homelab            | SSE               | `mcpx-stdio-proxy:7030/servers/hass-mcp/sse` (uvx via proxy)  |
| photoshop             | creative           | SSE               | `mcpx-stdio-proxy:7030/servers/photoshop/sse` (uvx via proxy) |
| playwright            | browser            | SSE               | `host.docker.internal:7007/sse` (not on ai-shared; see Security) |
| browser-use           | —                  | (disabled)        | in `_disabledMcpServers`                                      |

## Tool groups (app.yaml)

| Group              | Tools allowed to | Servers                       |
| ------------------ | ---------------- | ----------------------------- |
| core               | all consumers    | sequential-thinking, memory   |
| coding             | all consumers    | context7                      |
| knowledge-notes-work  | all consumers    | qdrant-notes-work             |
| knowledge-code-work   | all consumers    | qdrant-code-work              |
| knowledge-code-public | all consumers    | qdrant-code-public            |
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

## Security

mcpx is the front door to finance, Paperless and Home Assistant tools. The main hazard is mcpx's dashboard websocket (`/ws-ui`): it has no authentication, and it can rewrite tool permissions and add stdio servers, which means running commands inside mcpx. mcpx's own API-key guard does not cover it.

| Layer | Where | What it stops | What it does not stop |
| --- | --- | --- | --- |
| Loopback-only ports | `docker-compose.yml` | LAN and tailnet hosts | Local processes and containers: any container can reach `host.docker.internal:9000` |
| Host allowlist (421) | `nginx.conf` | DNS rebinding from web pages | Non-browser callers, which can send any Host |
| Origin allowlist (403) | `nginx-templates/` | Every browser page; no browser Origin is allowed by default | Non-browser callers, which can forge Origin |
| Key required without Origin (401) | `nginx-templates/` | CLIs, scripts and containers without the key, on every path including `/ws-ui` | A caller forging the dashboard Origin while the dashboard is enabled |
| mcpx API key (`auth.enabled`) | `app.yaml` | Keyless calls to `/mcp`, `/sse` and REST that bypass nginx, e.g. `mcpx:9000` from `ai-shared` | `/ws-ui` reached directly on `mcpx:9000`; mcpx never checks it |
| Not privileged | `docker-compose.yml` | Container escape after a compromise. `privileged` only served Docker-in-Docker, which no backend uses | |

**Rule: nothing that renders untrusted content joins `ai-shared`.** Any container on `ai-shared` can open `mcpx:9000/ws-ui` directly, bypassing nginx and the key, and take over mcpx and with it every backend credential, including Paperless documents. It can also call `paperless-mcp:7015` directly with no auth. That is why the headless browsers (`mcps/playwright`, `mcps/browser-use` and the containers browser-use starts) stay on their own project networks. The gateways reach them on 127.0.0.1 through `host.docker.internal`. Every container that remains on `ai-shared` is trusted with all of the above.

Off `ai-shared` is not the same as isolated. Through `host.docker.internal`, any container, the browsers included, can reach every port published on the host, even ports bound to 127.0.0.1. Only services that check Host and Origin or require a key are safe from them. mcpx on 9000 does. Never publish a forwarder that can reach `ai-shared`. (The unused `lunar-proxy` was removed for this reason: it relays to whatever host the `x-lunar-host` header names.) mcpx also mounts this whole directory read-write, so a compromised mcpx could rewrite `nginx.conf`.

**Using the dashboard.** The dashboard can't send the key, so nginx injects it for the dashboard's Origin, and only while that is enabled:

```bash
MCPX_DASHBOARD_ORIGIN=http://127.0.0.1:15173 docker compose up -d nginx-ssl   # on
# open http://127.0.0.1:15173/dashboard
docker compose up -d nginx-ssl                                               # off
```

While it is on, any caller that can reach nginx, including a container via `host.docker.internal`, can forge that Origin and get the key.

**The key.** It lives in `secrets/mcpx-auth.env` (gitignored), with Keeper's `homelab` folder as the source of truth ("mcpx gateway API key"). It reaches nginx through `nginx-templates/`, which the stock image renders at start. It is visible in `docker inspect` for `mcpx` and `mcpx-ssl-proxy`. If `AUTH_KEY` or `MCPX_DASHBOARD_ORIGIN` is empty, nginx refuses to start rather than letting everything through. Consumer tags (`x-lunar-consumer-tag`) are client-supplied labels: any key holder can claim any consumer.

## HTTPS (optional)

The `nginx-ssl` sidecar terminates TLS on `:9443` / `:5443`. Needs certs at `./certs/tls/{cert,key}.pem`:

```bash
mkdir -p certs/tls
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/tls/key.pem -out certs/tls/cert.pem \
  -subj "/CN=localhost"
```

## TODO

- [ ] Make `app.yaml` per-machine-overridable like `mcp.json` already is (env-var-selected mount). Tracked in root [TODO.md](../../TODO.md) under "Conventions" alongside the agentgateway equivalent.
- [ ] Test disconnection-safe caching with OpenCode
- [ ] Set up consumer tags for per-client metrics
- [ ] Compare to Atrax and MetaMCP as alternatives

## See also

- [stdio-proxy](../stdio-proxy/readme.md) — uvx/npx subprocess host, included by this stack
- [agentgateway](../../gateways/agentgateway/readme.md) — sibling MCP gateway (Linux Foundation, more enterprise features)
- [TheLunarCompany/lunar](https://github.com/TheLunarCompany/lunar)
