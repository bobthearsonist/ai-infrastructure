# playwright-chrome: shared Playwright MCP for your everyday Chrome

One Playwright MCP server, in extension mode, that drives your own signed-in
Chrome through the Playwright MCP Bridge extension. It runs once on the host and
every agent reaches it through mcpx as `playwright-chrome`, so no client needs
its own bridge.

Compare `mcps/neko`, a separate Chromium you sign in to on purpose. Prefer that
one; use this when the session you need exists only in your everyday Chrome.

## Layout

| Path | Purpose |
|---|---|
| `bin/playwright-chrome-mcp-http` | Launcher, installed to `~/.local/bin`. HTTP on `127.0.0.1:7017`, `--shared-browser-context` |
| `bin/playwright-chrome-open` | Opens the extension's connect page through LaunchServices (macOS blocks these processes from reading Chrome's profile folder) |
| `com.bobthearsonist.playwright-chrome-mcp.plist` | LaunchAgent that keeps the launcher running |

The extension token lives in `~/.config/playwright-mcp/token.env`
(`PLAYWRIGHT_MCP_EXTENSION_TOKEN`), outside the repo.

## Install

```bash
cp bin/playwright-chrome-mcp-http bin/playwright-chrome-open ~/.local/bin/
cp com.bobthearsonist.playwright-chrome-mcp.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.bobthearsonist.playwright-chrome-mcp.plist
lsof -nP -iTCP:7017 -sTCP:LISTEN   # expect node listening on 127.0.0.1
```

Remove with `launchctl bootout gui/$(id -u)/com.bobthearsonist.playwright-chrome-mcp`.

## mcpx registration

- `mcps/mcpx/mcp.json`: `playwright-chrome` → `http://host.docker.internal:7017/sse`.
  Docker Desktop forwards `host.docker.internal` to the host's loopback, so the
  server never listens beyond `127.0.0.1`.
- `mcps/mcpx/app.yaml`: tool group `browser-chrome`, an explicit tool list that
  withholds `browser_run_code_unsafe` and `browser_network_request(s)`, granted
  to the same consumers as `browser-personal`.
- Restart mcpx after changes, then restart Claude Desktop (its `mcp-remote`
  bridge stops retrying after an mcpx restart).

## Behaviour and security

- `--shared-browser-context`: all clients share one extension connection and one
  tab group in Chrome. Agents must open and close their own tabs; nothing stops
  two agents working at once.
- Anything that reaches `127.0.0.1:7017`, or any mcpx consumer granted
  `browser-chrome`, can act as you on every site signed in to in your Chrome.
- Clicks in a background Chrome tab time out (Chrome throttles animation frames
  there, so Playwright's stability check never passes); act through the page or
  bring the tab to the front.
- Agent guardrails are prompt-level (`~/.claude/rules/` and Claude Desktop
  personal preferences), not a security boundary.
