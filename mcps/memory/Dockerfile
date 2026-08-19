# Memory MCP Server - Dedicated stateful container
# Single instance shared by all gateway stacks to avoid concurrent-write races
FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install Node.js for the MCP server
RUN apk add --no-cache nodejs npm

# Pin the server at BUILD time instead of resolving `npx -y ...` at every
# container start. Unpinned npx re-resolves "latest" on each start, which means
# an upstream release silently lands in production AND re-inherits the
# non-atomic saveGraph() bug that this image patches out below.
ARG SERVER_MEMORY_VERSION=2026.7.4
RUN npm install -g @modelcontextprotocol/server-memory@${SERVER_MEMORY_VERSION}

# Make saveGraph() write atomically (temp file + rename). The script exits
# non-zero if the upstream anchor is missing, so an upstream refactor breaks
# the build loudly rather than shipping an unprotected writer.
COPY patch-atomic-write.cjs /patch/patch-atomic-write.cjs
RUN node /patch/patch-atomic-write.cjs

# Copy server configuration (compose also bind-mounts this read-only)
COPY servers.json /config/servers.json

# Expose the proxy port
EXPOSE 7040

# Run mcp-proxy with named server config
ENTRYPOINT ["mcp-proxy"]
CMD ["--pass-environment", "--host", "0.0.0.0", "--port", "7040", "--named-server-config", "/config/servers.json", "--debug"]
