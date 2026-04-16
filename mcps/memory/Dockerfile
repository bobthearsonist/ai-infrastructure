# Memory MCP Server - Dedicated stateful container
# Single instance shared by all gateway stacks to avoid concurrent-write races
FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install Node.js for npx-based MCP server
RUN apk add --no-cache nodejs npm

# Copy server configuration
COPY servers.json /config/servers.json

# Expose the proxy port
EXPOSE 7040

# Run mcp-proxy with named server config
ENTRYPOINT ["mcp-proxy"]
CMD ["--pass-environment", "--host", "0.0.0.0", "--port", "7040", "--named-server-config", "/config/servers.json", "--debug"]
