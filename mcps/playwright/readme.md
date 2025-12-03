# Playwright MCP

Microsoft's official Playwright MCP server for browser automation capabilities using [Playwright](https://playwright.dev/).

- 📖 **Docs**: <https://github.com/microsoft/playwright-mcp>
- 🐳 **Image**: `mcr.microsoft.com/playwright/mcp:latest`

## Features

- Fast and lightweight - uses Playwright's accessibility tree, not pixel-based input
- LLM-friendly - no vision models needed, operates on structured data
- Deterministic tool application - avoids ambiguity of screenshot-based approaches

## Port

| Port | Protocol | Description |
|------|----------|-------------|
| 7007 | HTTP     | MCP endpoint (`/mcp`) and SSE (`/sse`) |

## Healthcheck

The official Playwright MCP image intentionally has no `/health` endpoint to stay minimal ([rejected PR #1054](https://github.com/microsoft/playwright-mcp/pull/1054)).

We use a **TCP port check** for the healthcheck because:

1. **No side effects** - TCP handshake doesn't trigger MCP protocol or create sessions
2. **No orphaned connections** - Unlike SSE which holds connections open
3. **No log spam** - Doesn't hit application-level logging
4. **Minimal overhead** - Kernel-level check only

The tradeoff is it only confirms "process is listening" not "application logic is working", but for this simple Node.js server, if the HTTP server is listening, the MCP logic is ready.

## Links

- [GitHub Repository](https://github.com/microsoft/playwright-mcp)
- [Standalone MCP Server Docs](https://github.com/microsoft/playwright-mcp?tab=readme-ov-file#standalone-mcp-server)
