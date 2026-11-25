# neko: logged-in personal browser for agents

A Chromium you sign in to by hand (Google, Amazon, ...) through a web viewer,
which agents then drive as you through Playwright MCP over CDP. mcpx exposes it
as `playwright-personal` (tool group `browser-personal`; `mcps/mcpx/app.yaml`
lists the consumers granted it). Untrusted browsing belongs on the clean
`mcps/playwright` browser instead.

Google refuses sign-in in Playwright-launched browsers; a normally launched
browser that a human signs in to, attached to later over CDP, is not flagged.

## Layout

| Path | Purpose |
|---|---|
| `docker-compose.yml` | `chromium-personal` (linuxserver/chromium, Selkies viewer) and the `mcp-playwright-personal` sidecar sharing its network namespace |
| `config/policies.json` | Managed Chrome policy: Keeper force-installed, other extensions and downloads blocked |
| `config/wrapped-chromium` | Replaces the image's launcher: Chromium sandbox on, stale profile locks cleared |
| `config/google-chrome.conf` | Unused here: the neko (WebRTC) image's launcher, kept for hosts with real host networking |
| `secrets/chromium.env` | Gitignored. `CUSTOM_USER` / `PASSWORD` for the viewer's basic auth |
| `.env` | Gitignored. `NEKO_TAILNET_ORIGIN`, the machine's tailnet viewer origin (optional) |
| `data/chromium-config/` | Gitignored. Browser home and profile (`profile/`); holds live sessions |

## Run

```bash
docker compose up -d
# Recreating the stack recreates the sidecar and orphans mcpx's session to it:
docker stop -t 30 mcpx && docker start mcpx
# Claude Desktop's mcp-remote bridge stops retrying after an mcpx restart:
# quit and reopen Claude Desktop afterwards.
```

When bumping the image, diff `config/wrapped-chromium` against the image's
`/usr/bin/wrapped-chromium` and carry over upstream changes.

## Viewer access

- On the Mac: `http://localhost:8091` (basic auth from `secrets/chromium.env`).
- From a phone or other tailnet device, tailnet only (never Funnel):

  ```bash
  tailscale serve --bg --https=8443 http://127.0.0.1:8091
  echo 'NEKO_TAILNET_ORIGIN=https://<machine>.<tailnet>.ts.net:8443' > .env
  docker compose up -d
  ```

  Remove with `tailscale serve --https=8443 off`. Without `NEKO_TAILNET_ORIGIN`
  the viewer page loads but its stream websocket is refused (403).

## Security model

- Nothing is published beyond `127.0.0.1`; the tailnet viewer goes through
  Tailscale Serve. CDP (9222) is never published: only the sidecar, inside the
  browser's network namespace, reaches it.
- `SELKIES_ALLOWED_ORIGINS` blocks cross-site WebSocket hijacking of the viewer.
  The image's default (`*`) would let any page in a browser holding the
  viewer's basic auth drive this browser.
- The Chromium sandbox is on, which requires `seccomp:unconfined` on Docker
  Desktop. `HARDEN_DESKTOP` removes the viewer desktop's terminal, sudo and file
  transfer.
- `127.0.0.1:7016` (the MCP endpoint) has no authentication, and every
  container on the host can reach it through `host.docker.internal`. Anything
  that reaches it can act as you on every signed-in site.
- mcpx exposes `playwright-personal` through an explicit tool list in
  `mcps/mcpx/app.yaml` (group `browser-personal`) that withholds
  `browser_run_code_unsafe` (arbitrary code, can reach the Keeper extension)
  and `browser_network_request(s)` (full headers and bodies). New upstream
  tools stay hidden until listed there.
- Page snapshots include form field values, passwords included, so an agent
  must not snapshot a page where a credential has been filled in.
- Keeper stays usable in this browser by design. Agent behaviour around it,
  sign-in hand-off and page-content prompt injection is governed by prompt
  guardrails: a user-level Claude Code rule (`~/.claude/rules/`) and the same
  text in Claude Desktop's personal preferences. They are guidance, not a
  security boundary.
