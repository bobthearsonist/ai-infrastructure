# TODO

Tracking outstanding work, in roughly decreasing order of architectural weight.

---

## Architecture Plans

Major proposed changes with detailed plan docs in `docs/`. Each plan has an explicit trigger condition — don't act until the trigger fires.

- [ ] **[`docker-proxy`: second router for containerized MCPs](docs/docker-proxy-plan.md)**
  Build trigger: first MCP that genuinely needs Docker (browser sandboxing, native deps, hard isolation) and that isn't available via PyPI/npm. Mirrors `stdio-proxy` with `docker-cli` + `docker.sock` scoped to one container.

- [ ] **[Single shared `stdio-proxy` refactor](docs/single-shared-stdio-proxy-plan.md)**
  Build trigger: a third gateway joins OR duplication starts causing visible pain (HA rate-limiting from N copies of `uvx hass-mcp`, memory pressure, etc.). Eliminates the per-gateway `include:` pattern in favor of a single shared platform stack.

---

## Deferred Work From Recent Sessions

- [ ] **Re-enable `browser-use` in `mcps/mcpx/mcp.json`** when it becomes useful again. Before doing the work, check whether the upstream has a PyPI/npm package — same recipe we used for hass-mcp (`uvx hass-mcp` entry in `stdio-proxy/servers.home.json`). If genuinely Docker-only, that's the trigger for the `docker-proxy` plan above.

- [ ] **Autoheal sidecar** for any future Pattern A MCPs (docker-in-docker via `mcp-proxy`). Not needed for the current stack (all hosts are uvx/npx Pattern B now). See memory `reference_mcp_proxy_zombie_bug` for context. Stub deferred indefinitely; revisit only if `browser-use` comes back as Pattern A.

- [ ] **Retire `mcps/hass-mcp/`** standalone stack directory. Stack was brought down 2026-05-13 but the directory and `.env` are still on disk. Delete after the uvx-based migration has run for a week without regression.

---

## Smaller Cleanups

- [ ] Remove obsolete `version: '3.9'` field from `mcps/playwright/docker-compose.yml`. Compose warns: *"the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"*. Check other compose files for the same.

- [ ] Consider migrating older operational TODOs from `README.md` (langfuse-prompts MCP, obsidian MCP, Watchtower labels, agentgateway TLS) into this file so there's a single source of truth. Currently split across both.

---

## Done Recently (Reference)

For context on recent architectural decisions and their evidence base:

- 2026-05-13 — mcpx upgraded to `:latest` (was pinned to `:stable` for 6 months due to a different mcpx-side bug we'd misdiagnosed; root cause was actually upstream proxy zombies).
- 2026-05-13 — `hass-mcp` migrated from docker-in-docker (`mcps/hass-mcp/` stack) to `uvx hass-mcp` via `stdio-proxy/servers.home.json`. Validated the "check upstream PyPI/npm before assuming Docker" rule.
- 2026-05-13 — Per-gateway alias rule established for `stdio-proxy` (see memory `reference_mcp_router_architecture`). Resolves cross-stack DNS collision on `ai-shared`.
- 2026-05-13 — Photoshop URL fixed (`host.docker.internal:7030` was never reachable; should have been `mcpx-stdio-proxy:7030`).
- 2026-05-13 — Playwright `--allowed-hosts '*'` flag added; routes via `mcp_playwright:7007` direct on ai-shared instead of through host port-forward.

---

## See Also

- `README.md` — older operational TODOs not yet consolidated here.
- `docs/` — full plan docs and architecture notes.
- Memory: `reference_mcp_router_architecture`, `reference_mcp_proxy_zombie_bug` — empirical learnings cited by the plans above.
