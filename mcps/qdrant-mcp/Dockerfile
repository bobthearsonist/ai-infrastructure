# Qdrant RAG MCP Server
# Uses Debian-based image (glibc required for onnxruntime/fastembed)
FROM python:3.12-slim

# Install mcp-proxy to expose stdio MCP as SSE
# Install mcp-server-qdrant for RAG capabilities
# mcp-proxy is pinned: minor releases have changed request handling (0.14 added
# Host-header enforcement), so upgrade deliberately and re-check the CMD flags.
RUN pip install --no-cache-dir mcp-proxy==0.14.0 mcp-server-qdrant

# Copy server configuration
COPY servers.json /config/servers.json

EXPOSE 7020

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7020/status')" || exit 1

# mcp-proxy >= 0.14 rejects any Host header not on its allowlist (DNS-rebinding
# protection). mcpx reaches this container as qdrant-mcp (shared network) or
# host.docker.internal, so both must be trusted explicitly.
CMD ["mcp-proxy", "--pass-environment", "--host", "0.0.0.0", "--port", "7020", \
     "--allowed-host", "qdrant-mcp:*", "--allowed-host", "host.docker.internal:*", \
     "--named-server-config", "/config/servers.json"]
