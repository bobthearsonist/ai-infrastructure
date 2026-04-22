# Memory MCP

Persistent memory storage for conversations and context.

## Source

- Package: `@modelcontextprotocol/server-memory`
- Repository: https://github.com/modelcontextprotocol/servers

## Architecture

**Dedicated stateful container** — runs as a single shared instance across all gateway stacks
to avoid concurrent-write race conditions on `memory.jsonl`.

- Transport: stdio → SSE via `mcp-proxy` wrapper
- Port: `7040`
- SSE endpoint: `/servers/memory/sse`
- Data: `/data/memory/memory.jsonl` (bind-mounted from host)

## Usage

Both gateway stacks (mcpx, agentgateway) reference this container by its name
`memory_mcp` on the shared `ai-shared` Docker network.
