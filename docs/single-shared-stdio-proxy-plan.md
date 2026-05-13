# Single Shared stdio-proxy: Planned Refactor

**Status:** Proposed. Not urgent; current per-gateway include pattern works after the alias-collision fix (see `reference_mcp_router_architecture` memory). Trigger to do this refactor is "a third gateway joins the stack" or "the duplication starts feeling like maintenance burden."
**Last updated:** 2026-05-13

---

## Why This Exists

Today, `mcps/stdio-proxy/docker-compose.yml` is `include:`d by every gateway. Each gateway gets its own private copy of stdio-proxy under its compose project (`mcpx-stdio-proxy-1`, `agentgateway-stdio-proxy-1`). This was the original pattern to avoid DNS collisions, but it has two consequences worth revisiting:

1. **Resource duplication.** Each include-spawned stdio-proxy runs its own copy of every defined MCP: 2× `mcp-proxy`, 2× `uvx hass-mcp`, 2× `uvx psmcp`, 2× `npx kapture`, 2× `npx sequential-thinking`. That's 10 processes when 5 would do. The HA_TOKEN is also passed through to two separate `uvx hass-mcp` processes that both authenticate against Home Assistant.
2. **Cross-instance alias collision on `ai-shared`.** Both stdio-proxy containers attach to `ai-shared` (legitimately — they need outbound to `kapture-server`, `adb-proxy`) and Compose auto-publishes the `stdio-proxy` service-name alias on every attached network. DNS lookups for `stdio-proxy` on `ai-shared` are non-deterministic — could return either gateway's instance. We worked around this by introducing per-gateway aliases (`mcpx-stdio-proxy`, `agentgateway-stdio-proxy`) and updating mcp.json / config.yaml accordingly.

A single shared stdio-proxy eliminates both at the root: one process tree, one config, one alias. Each gateway becomes a *consumer* rather than a *co-instantiator*.

## Architecture

```
   mcpx_default                  agentgateway_default
   ───────────────               ─────────────────────
   ┌──────┐                      ┌──────────────┐
   │ mcpx │                      │ agentgateway │
   └──┬───┘                      └──────┬───────┘
      │ via ai-shared                   │ via ai-shared
      └────────────┐         ┌──────────┘
                   ▼         ▼
       ─────────────── ai-shared ───────────────
                         │
                         ▼
              ┌─────────────────────────────┐
              │ stdio-proxy                 │
              │ (own compose stack at       │   ┌─ uvx hass-mcp
              │  mcps/stdio-proxy/)         │   │
              │                             ├───┼─ uvx psmcp
              │ alias: stdio-proxy ✓        │   │
              │ ONE instance for all        │   ├─ npx kapture-mcp
              │ gateways                    │   │
              │                             │   └─ npx sequential-thinking
              │ Reads servers.home.json,    │
              │ spawns 4 child processes    │
              │ (not 8 across two copies)   │
              └─────────────────────────────┘
```

## Files Changed

| File | Change |
|------|--------|
| `mcps/stdio-proxy/docker-compose.yml` | Add `networks: ai-shared: external: true` and attach stdio-proxy + mcp-status to it. Drop the `# Network: When included by a parent compose file ...` comment (no longer included). |
| `mcps/stdio-proxy/.env` | Keep as-is (HA_URL, HA_TOKEN, AUTO_APPROVE). |
| `mcps/mcpx/docker-compose.yml` | Remove the `include: ../../mcps/stdio-proxy/docker-compose.yml` and the `stdio-proxy:` service override. mcpx itself stays on `ai-shared` (already there). |
| `mcps/mcpx/mcp.json` | URL host changes from `mcpx-stdio-proxy` → `stdio-proxy` (the now-unambiguous alias on ai-shared). |
| `gateways/agentgateway/docker-compose.yml` | Same removal of include + override. |
| `gateways/agentgateway/config.yaml` | URL host changes from `agentgateway-stdio-proxy` → `stdio-proxy`. |

## Migration Steps

1. **Bring stdio-proxy up as a standalone stack** *before* breaking the includes:
   ```bash
   cd mcps/stdio-proxy
   docker compose up -d
   ```
   Verify it's healthy (`docker compose ps`, `wget /status`).
2. **For each gateway, in turn:**
   - Edit the gateway's compose to remove the `include:` and the `stdio-proxy:` service override.
   - Edit the gateway's config (`mcp.json` or `config.yaml`) to use `http://stdio-proxy:7030/servers/<name>/sse`.
   - `docker compose down stdio-proxy` for that gateway's project (removes the per-gateway included instance).
   - `docker compose restart <gateway>` so the gateway picks up the new config.
   - Verify the gateway's logs show clean connection to the shared stdio-proxy.
3. **Clean up the per-gateway aliases** in compose files (the `mcpx-stdio-proxy` / `agentgateway-stdio-proxy` aliases we added earlier become obsolete). Replace with comments documenting that the shared instance is at `stdio-proxy:7030` on ai-shared.
4. **Update or remove `reference_mcp_router_architecture` memory** to reflect the new topology — the per-gateway-alias rule no longer applies because there's only one instance.

## Trade-offs

- **Single point of failure.** If shared stdio-proxy is down, every gateway loses every stdio MCP. Today each gateway can survive the other's stdio-proxy failure (in theory; in practice they share state anyway). Mitigation: `restart: unless-stopped` + healthcheck. Failure window: seconds during a restart.
- **Loss of per-gateway customization.** All gateways consume the same `servers.json`. Today both already share `servers.home.json` via the mount, so this is a theoretical, not actual, loss. If a future gateway needs a different set of MCPs, options include (a) maintaining a second shared instance with a different config (e.g. `stdio-proxy-dev`), (b) per-gateway override via a flag/env passed to the proxy.
- **Compose include pattern goes away for this service.** The `include:` shorthand was convenient for "every gateway brings its own batteries." Trading it for an explicit external service contract. Documentation cost; the readme should make this clear.
- **The standalone stdio-proxy stack stops being a "dev convenience" and becomes the canonical instance.** Today it's been killed as accidental; under this refactor it's *the* one. That's a mental shift worth flagging in the repo readme.

## Why Defer (For Now)

The current per-gateway alias fix is stable and the duplication cost is small — a few hundred MB of RAM. The migration above is straightforward but takes a few coordinated edits across two gateway stacks plus the proxy itself. Worth doing when:
- A third gateway is added (multiplies the duplication cost).
- Operational pain from N copies of the same MCPs (HA rate-limiting from duplicate auth, e.g.) becomes visible.
- The docker-proxy plan from [docker-proxy-plan.md](docker-proxy-plan.md) lands as a *shared* second router — at that point we'd want the topology to match (both routers as shared platform services, not per-gateway includes).

## Related

- [docker-proxy-plan.md](docker-proxy-plan.md) — parallel proposal for a second router class for containerized MCPs. If both plans land, the topology becomes: each gateway consumes two shared platform routers (`stdio-proxy:7030` for uvx/npx, `docker-proxy:7031` for Docker-spawned), each addressed by a single unambiguous alias.
- Memory: `reference_mcp_router_architecture` — current per-gateway alias rule. Will need updating if this refactor lands.
- The standalone stdio-proxy stack (`mcps/stdio-proxy/`) — the base for this refactor. Was retired on 2026-05-13 as "accidentally running"; this plan resurrects it as the canonical instance.
