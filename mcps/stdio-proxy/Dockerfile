# stdio-proxy: Multiple stdio MCP servers exposed via SSE
FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install Node.js for npx-based MCP servers
RUN apk add --no-cache nodejs npm

# Set working directory
WORKDIR /app

# Copy server configuration
COPY servers.json /config/servers.json

# Expose the proxy port
EXPOSE 7030

# Run mcp-proxy with named server config
# mcp-proxy eagerly initializes all MCPs at startup before listening
ENTRYPOINT ["mcp-proxy"]
CMD ["--host", "0.0.0.0", "--port", "7030", "--named-server-config", "/config/servers.json", "--debug"]
