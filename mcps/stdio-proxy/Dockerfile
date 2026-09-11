# stdio-proxy: Multiple stdio MCP servers exposed via SSE
# Supports both Node.js (npx) and Python (uvx) based MCPs
# Deliberately :latest. Rebuild with `docker compose build --pull` — a plain
# build reuses the cached base layer and silently stays on an old release.
FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install Node.js for npx-based MCP servers.
# libsecret is required at *require* time by keytar, which @azure-devops/mcp
# pulls in transitively via @azure/msal-node-extensions (absent in 2.7.0, present by 2.10.0).
# keytar dlopens libsecret-1.so.0; on Alpine that file is absent, node aborts
# with ERR_DLOPEN_FAILED, and mcp-proxy -- which initialises every named server
# eagerly and fatally -- exits 1, taking the healthy servers down with it.
RUN apk add --no-cache nodejs npm libsecret

# Install Python and uv for Python-based MCP servers
ENV PATH="/root/.local/bin:$PATH"
RUN apk add --no-cache python3 py3-pip curl bash && \
    curl -LsSf https://astral.sh/uv/install.sh | bash && \
    uv --version && uvx --version

# Install Azure CLI for azure-devops MCP (azcli auth mode)
RUN uv tool install azure-cli --extra-index-url https://azcliprod.blob.core.windows.net/pip --prerelease=allow

# servers.json must be provided via volume mount (per-machine config)

# Expose the proxy port
EXPOSE 7030

# Run mcp-proxy with named server config
# mcp-proxy eagerly initializes all MCPs at startup before listening
ENTRYPOINT ["mcp-proxy"]
CMD ["--pass-environment", "--host", "0.0.0.0", "--port", "7030", "--named-server-config", "/config/servers.json", "--debug"]
