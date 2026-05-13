# docker-proxy: Planned Second Router for Containerized MCPs

**Status:** Proposed, not implemented. Trigger to build is "the first MCP we genuinely need to run as a Docker container."
**Last updated:** 2026-05-13

---

## Why This Exists

`stdio-proxy` (today) hosts MCPs as `uvx`/`npx` subprocesses inside its own container — no Docker socket, no `docker-cli`, low blast radius. That works for the majority of MCP servers because most ship to PyPI or npm in addition to Docker Hub. The 2026-05 hass-mcp migration validated this: we eliminated a docker-in-docker stack by switching to `uvx hass-mcp`, with zero functional regression.

But there's a real class of MCPs that need genuine container isolation, not just convenient packaging:

- **Browser automation MCPs** (browser-use, others) — drag in chromium with specific versions of native libs.
- **GPU / ML workloads** — need CUDA toolchains that don't belong in `stdio-proxy`.
- **MCPs requiring hard isolation** — untrusted code, separate network namespaces, resource caps.
- **MCPs without PyPI/npm distribution** — Docker image is the only artifact the upstream publishes.

For these, we need a router that knows how to spawn / exec into Docker containers. That router should NOT be `stdio-proxy` — adding `/var/run/docker.sock` to stdio-proxy widens its blast radius to every uvx/npx MCP it hosts. The right shape is a *separate* router with the same interface (mcp-proxy + `--named-server-config` + SSE) but with the Docker capabilities scoped to one container.

## Naming and Placement

- Repo path: `mcps/docker-proxy/`
- Service name: `docker-proxy` (in its own compose project also named `docker-proxy`)
- Port: `7031` (distinct from stdio-proxy's `7030`)
- Per-gateway alias: `<gateway>-docker-proxy` (same pattern as stdio-proxy — see `reference_mcp_router_architecture` memory)

## Architecture

```
   ┌──────────────────────────────────────┐
   │ docker-proxy container               │
   │  FROM ghcr.io/sparfenyuk/mcp-proxy   │
   │  + apk add docker-cli                │
   │  /var/run/docker.sock mounted        │
   │                                      │
   │  mcp-proxy --named-server-config     │
   │  Reads servers.json with entries:    │
   │                                      │
   │    "browser-use": {                  │
   │      "command": "docker",            │
   │      "args": ["exec", "-i",          │
   │        "browser-use-server",         │
   │        "python", "-m",               │
   │        "browser_use.mcp"]            │
   │    }                                 │
   └──────────────────────────────────────┘
              │ spawns (per stdio session)
              ▼ via mounted socket
   ┌──────────────────────────────────────┐
   │ Sibling MCP containers,              │
   │ managed by their OWN compose stacks: │
   │                                      │
   │  - browser-use-server (long-lived)   │
   │  - <future-docker-mcp> (long-lived)  │
   │                                      │
   │ Each idles with a long-running main  │
   │ process (e.g. `tail -f /dev/null` or │
   │ a real service). docker-proxy uses   │
   │ `docker exec -i` to get a fresh stdio│
   │ session against the running container│
   │ per MCP client connection.           │
   └──────────────────────────────────────┘
```

Two key choices in this design:

1. **`docker exec` over `docker run`.** `docker run -i --rm` would spawn a fresh container per startup — same lifecycle entanglement that caused the hass-mcp zombie bug (see `reference_mcp_proxy_zombie_bug`). `docker exec` against a long-lived sibling decouples container lifecycle from subprocess lifecycle. Container is owned by `docker compose`/`restart: unless-stopped` (which works on container exit). Subprocess is owned by mcp-proxy (normal SIGCHLD detection).
2. **Sibling MCPs are their own compose stacks, not spawned by docker-proxy.** Keeps lifecycle management on the standard compose tooling. docker-proxy just routes; it doesn't own the inner containers' lifecycle.

## Files

```
mcps/docker-proxy/
├── docker-compose.yml      # mcp-proxy container, sock mount, healthcheck
├── Dockerfile              # FROM mcp-proxy + apk add docker-cli
├── servers.json            # named-server-config entries (docker exec ...)
└── readme.md
```

Per-gateway integration:
```
mcps/mcpx/docker-compose.yml         # add: include: ../docker-proxy/docker-compose.yml
                                     # add: docker-proxy override with mcpx-docker-proxy alias
mcps/mcpx/mcp.json                   # add SSE URL: http://mcpx-docker-proxy:7031/servers/<name>/sse
gateways/agentgateway/docker-compose.yml  # same shape, with agentgateway-docker-proxy alias
```

## Migration Steps (When Triggered)

1. **Confirm the upstream genuinely needs Docker.** Check PyPI/npm first. If the upstream ships only as a Docker image AND the runtime can't be packaged into stdio-proxy's image without unreasonable cost, then docker-proxy is justified.
2. **Create the stack.**
   - `mcps/docker-proxy/Dockerfile`: `FROM ghcr.io/sparfenyuk/mcp-proxy:latest`, `RUN apk add --no-cache docker-cli`.
   - `mcps/docker-proxy/docker-compose.yml`: mount `/var/run/docker.sock`, expose 7031, `restart: unless-stopped`, pgrep-aware healthcheck (same shape as stdio-proxy's, see `reference_mcp_router_architecture`).
   - `mcps/docker-proxy/servers.json`: one entry per docker-spawned MCP.
3. **Stand up the sibling MCP container as its own compose stack** (e.g. `mcps/browser-use/` already exists for browser-use). Make sure it has a long-running main process and a sensible `container_name`.
4. **Per-gateway include + alias** (mcpx and agentgateway):
   ```yaml
   include:
     - path: ../docker-proxy/docker-compose.yml
   services:
     docker-proxy:
       networks:
         default:
           aliases:
             - mcpx-docker-proxy   # or agentgateway-docker-proxy
         ai-shared:
   ```
5. **Wire mcp.json / config.yaml** with `http://<gateway>-docker-proxy:7031/servers/<name>/sse`.
6. **Verify**: `docker exec mcpx getent hosts mcpx-docker-proxy` returns one IP, `wget /status` returns 200, `count` in mcpx logs reflects the new backend.

## Trade-offs to Sit With

- **Docker socket exposure.** docker-proxy gets `/var/run/docker.sock`, which is functionally root-on-host. Acceptable here because (a) it's scoped to one container with a narrow purpose, (b) the homelab threat model accepts trusting MCPs, (c) any future tightening (`docker.sock-proxy`, rootless docker) plugs in cleanly without changing the routing.
- **Container lifecycle coupling to sibling stacks.** docker-proxy depends on the inner MCP containers being up. If `browser-use-server` is down, `docker exec` fails and mcp-proxy logs an error. Mitigation: keep the sibling stacks on `restart: unless-stopped`, healthcheck them, and let mcpx's retry logic handle transient unavailability.
- **Same per-gateway-instance alias collision pattern as stdio-proxy.** Two gateways `include:`ing docker-proxy will both publish `docker-proxy` on `ai-shared`. The `<gateway>-docker-proxy` alias rule handles this — see `reference_mcp_router_architecture`.
- **`docker exec` adds a hop** through dockerd between mcp-proxy and the actual MCP process. Latency cost is real but small (<10ms typical). Failure modes are mostly transparent (exec exits when target process exits), so mcp-proxy's parent-child supervision still works.

## Out of Scope

- **Sharing inner containers across gateways.** Tempting (run one `browser-use-server`, both gateways `docker exec` into it) but introduces concurrency questions (cookies, browser state, session interference). Defer until there's a concrete use case demanding it.
- **Combining stdio-proxy and docker-proxy.** Would re-introduce the blast-radius problem we're avoiding. Two routers is the architecture.
- **Service mesh (Consul, Traefik).** Heavy for a homelab. Plain Compose + explicit aliases is sufficient.

## Related

- [single-shared-stdio-proxy-plan.md](single-shared-stdio-proxy-plan.md) — parallel refactor for the existing stdio-proxy, eliminating its include-pattern duplication. If both plans land, the resulting topology is two purpose-specific routers, each as a single shared instance.
- Memory: `reference_mcp_router_architecture` — alias collision rules, the negative empirical result on `aliases: []`.
- Memory: `reference_mcp_proxy_zombie_bug` — why `docker exec` is preferred over `docker run -i --rm` for the spawn pattern.
