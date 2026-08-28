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

# Report probable duplicate entities on create. Upstream dedupes on exact name
# equality, which cannot see the duplicates that actually occur: "Context Lens"
# vs "context-lens", or two entities sharing 47% of their observation text under
# names sharing no tokens at all. Advisory only - it changes no control flow,
# because an exact-name collision upstream drops the entity and its observations
# silently rather than merging them, so matching more loosely would lose data.
# Same fail-the-build-on-anchor-drift contract as the patch above.
COPY patch-dedupe-warn.cjs /patch/patch-dedupe-warn.cjs
RUN node /patch/patch-dedupe-warn.cjs

# Copy server configuration (compose also bind-mounts this read-only)
COPY servers.json /config/servers.json

# Expose the proxy port
EXPOSE 7040

# Run mcp-proxy with named server config
ENTRYPOINT ["mcp-proxy"]
CMD ["--pass-environment", "--host", "0.0.0.0", "--port", "7040", "--named-server-config", "/config/servers.json", "--debug"]
