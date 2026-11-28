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
| `bin/playwright-chrome-mcp` | stdio launcher for Claude Desktop (`claude_desktop_config.json` entry `playwright-chrome` with `"command": "/Users/<you>/.local/bin/playwright-chrome-mcp"`). Desktop starts one per chat, each with its own extension connection and tab group |
| `bin/playwright-chrome-open` | Opens the extension's connect page through LaunchServices (macOS blocks these processes from reading Chrome's profile folder) |
| `com.bobthearsonist.playwright-chrome-mcp.plist` | LaunchAgent that keeps the launcher running |

The extension token lives in `~/.config/playwright-mcp/token.env`
(`PLAYWRIGHT_MCP_EXTENSION_TOKEN`), outside the repo.

## Install

```bash
cp bin/playwright-chrome-mcp-http bin/playwright-chrome-mcp bin/playwright-chrome-open ~/.local/bin/
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

## Connection stability

- **Heartbeat disabled** (`PLAYWRIGHT_MCP_PING_TIMEOUT_MS=0` in both launchers).
  By default Playwright MCP pings each client and closes its session when one
  ping goes unanswered for 5 s. A single busy moment in mcpx or Claude Desktop
  then drops the session; on the shared bridge, losing the last client closes
  the extension connection and releases every agent tab group. With the default,
  a client that stops answering for 20 s loses its session (HTTP 404 on the next
  call); with the heartbeat off it keeps its session and tab. Clients that really
  go away still end their session: the HTTP stream or stdin closes.
- **Tabs do not survive the last client leaving.** When no client is connected,
  the bridge closes its extension connection; the extension greys the tab group
  and the next client gets a new group with a blank tab. Agents should reopen
  pages by URL rather than look for an old tab.
- **Use real URLs.** Navigating a tab to an `about:blank#...` URL makes Chrome
  close the extension's connection (WebSocket close 1001) within half a second,
  dropping that client and its tab group. `data:` URLs fail with
  `net::ERR_ABORTED`.
- **Protocol versions must match exactly.** The extension rejects both older and
  newer Playwright MCP clients, so the launchers use `@playwright/mcp@latest`
  instead of a pinned version. If the connect page reports an unsupported
  protocol version after Chrome updates the extension, restart the bridge
  (`launchctl kickstart -k gui/$(id -u)/com.bobthearsonist.playwright-chrome-mcp`)
  so `npx` resolves the matching release.
- **Known extension bug** ([microsoft/playwright#44399](https://github.com/microsoft/playwright/issues/44399)):
  when Chrome detaches the debugger from a tab twice within 3 s (for example a
  page where a password manager injects its frames), the extension stops
  announcing that tab. It stays in the group but agents can no longer see it.
  Dragging the tab out of the group and back in restores it. A fix is pending
  upstream.
