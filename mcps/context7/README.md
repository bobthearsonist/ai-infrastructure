# Context7 MCP Server

Context7 MCP provides up-to-date code documentation and examples for LLMs and AI code editors.

- 📖 **Docs**: <https://github.com/upstash/context7>
- 🌐 **Website**: <https://context7.com/>

## What is Context7?

Context7 MCP pulls up-to-date, version-specific documentation and code examples straight from the source and places them directly into your prompt context. This eliminates the problem of outdated code examples and hallucinated APIs.

## Features

- ✅ Up-to-date documentation from official sources
- ✅ Version-specific code examples
- ✅ No more hallucinated APIs
- ✅ Seamless integration with MCP clients

## Port

| Port | Protocol | Description |
|------|----------|-------------|
| 7008 | HTTP     | MCP endpoint (`/mcp`) and SSE (`/sse`) |

## Available Tools

- `resolve-library-id`: Resolves a general library name into a Context7-compatible library ID
- `get-library-docs`: Fetches documentation for a library using a Context7-compatible library ID

## Usage

Add `use context7` to your prompts in supported MCP clients like Cursor, Claude Code, VS Code, etc.

Example:

```text
Create a Next.js middleware that checks for a valid JWT in cookies and redirects unauthenticated users to /login. use context7
```

## Healthcheck

Context7 has no dedicated `/health` endpoint. We use a **TCP port check** (`nc -z localhost 7008`) for the healthcheck because:

1. **No side effects** - TCP handshake doesn't trigger MCP protocol or create sessions
2. **No orphaned connections** - Unlike SSE which holds connections open
3. **No log spam** - Doesn't hit application-level logging
4. **Minimal overhead** - Kernel-level check only

The tradeoff is it only confirms "process is listening" not "application logic is working", but for this simple Node.js server, if the HTTP server is listening, the MCP logic is ready.

## Links

- [Official Repository](https://github.com/upstash/context7)
- [Context7 Website](https://context7.com/)
- [Documentation](https://github.com/upstash/context7#readme)
