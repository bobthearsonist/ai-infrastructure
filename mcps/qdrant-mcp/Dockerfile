# Qdrant RAG MCP Server
# Uses Debian-based image (glibc required for onnxruntime/fastembed)
FROM python:3.12-slim

# Install mcp-proxy to expose stdio MCP as SSE
# Install mcp-server-qdrant for RAG capabilities
RUN pip install --no-cache-dir mcp-proxy mcp-server-qdrant

# Copy server configuration
COPY servers.json /config/servers.json

EXPOSE 7020

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7020/status')" || exit 1

CMD ["mcp-proxy", "--pass-environment", "--host", "0.0.0.0", "--port", "7020", "--named-server-config", "/config/servers.json"]
