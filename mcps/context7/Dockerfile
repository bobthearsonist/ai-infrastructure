# Context7 MCP Server Dockerfile
# Based on official upstash/context7 repository
FROM node:18-alpine

WORKDIR /app

# Install the latest version of Context7 MCP globally
RUN npm install -g @upstash/context7-mcp@latest

# Expose the Context7 HTTP port
EXPOSE 7008

# Health check to ensure the service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:7008/health || exit 1

# Default command to run the server with HTTP transport
CMD ["context7-mcp", "--transport", "http", "--port", "7008"]
