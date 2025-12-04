# stdio-proxy: Multiple stdio MCP servers exposed via SSE
# Supports both Node.js (npx) and Python (uvx) based MCPs
FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install Node.js for npx-based MCP servers
RUN apk add --no-cache nodejs npm

# Install Python and uv for Python-based MCP servers
ENV PATH="/root/.local/bin:$PATH"
RUN apk add --no-cache python3 py3-pip curl bash && \
    curl -LsSf https://astral.sh/uv/install.sh | bash && \
    uv --version && uvx --version

# Copy server configuration
COPY servers.json /config/servers.json

# Expose the proxy port
EXPOSE 7030

# Run mcp-proxy with named server config
# mcp-proxy eagerly initializes all MCPs at startup before listening
ENTRYPOINT ["mcp-proxy"]
CMD ["--pass-environment", "--host", "0.0.0.0", "--port", "7030", "--named-server-config", "/config/servers.json", "--debug"]
