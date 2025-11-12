# Context7 MCP Server

Context7 MCP provides up-to-date code documentation and examples for LLMs and AI code editors.

## What is Context7?

Context7 MCP pulls up-to-date, version-specific documentation and code examples straight from the source and places them directly into your prompt context. This eliminates the problem of outdated code examples and hallucinated APIs.

## Features

- ✅ Up-to-date documentation from official sources
- ✅ Version-specific code examples
- ✅ No more hallucinated APIs
- ✅ Seamless integration with MCP clients

## Available Tools

- `resolve-library-id`: Resolves a general library name into a Context7-compatible library ID
- `get-library-docs`: Fetches documentation for a library using a Context7-compatible library ID

## Usage

Add `use context7` to your prompts in supported MCP clients like Cursor, Claude Code, VS Code, etc.

Example:

```text
Create a Next.js middleware that checks for a valid JWT in cookies and redirects unauthenticated users to /login. use context7
```

## Configuration

This container runs Context7 MCP server on HTTP transport at port 7008, making it accessible via HTTP endpoint for the MCPX gateway.

## Links

- [Official Repository](https://github.com/upstash/context7)
- [Context7 Website](https://context7.com/)
- [Documentation](https://github.com/upstash/context7#readme)
