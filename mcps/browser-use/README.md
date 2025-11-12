# Browser-Use MCP Server

This is a containerized setup for the browser-use MCP server that enables AI-driven browser automation. It provides a Model Context Protocol (MCP) interface for intelligent web browser interactions.

## Quick Start

1. **Build and start the container:**

   ```bash
   ./manage.sh setup
   ```

2. **Check health status:**

   ```bash
   curl http://localhost:7009/health
   ```

3. **Test the MCP endpoint:**

   ```bash
   curl http://localhost:7009/mcp
   ```

## Features ✨

- 🤖 **AI-Driven Browser Automation**: Uses browser-use library for intelligent web interactions
- � **MCP Compatible**: Full Model Context Protocol implementation
- 🐳 **Containerized**: Easy deployment with Docker
- 🌐 **Multi-Browser Support**: Chromium and Firefox support
- 📊 **Health Monitoring**: Built-in health check endpoint
- ⚡ **High Performance**: Optimized for automated workflows

## Setup

### 1. Environment Variables

Create a `.env` file with your API keys:

```bash
# Required: Choose one or both
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Optional: Browser settings
BROWSER_USE_HEADLESS=true
BROWSER_USE_LOGGING_LEVEL=WARNING
```

### 2. Build and Start

```bash
# Build the container
docker-compose build

# Start the service
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs browser-use-mcp
```

### 3. Configure MCP Clients

#### MCPX Gateway Configuration

The container will be automatically configured in the MCPX gateway. The service is available at:

- HTTP: `http://browser-use-mcp:7009/mcp`
- Health Check: `http://browser-use-mcp:7009/health`

## Usage

### Available MCP Tools

The server provides standard browser-use MCP tools:

- `browser_navigate`: Navigate to URLs
- `browser_click`: Click elements
- `browser_type`: Type text into forms
- `browser_extract_content`: Extract page content
- `browser_take_screenshot`: Capture screenshots
- `retry_with_browser_use_agent`: Use AI agent for complex tasks

### MCP Client Integration

Access the server through any MCP-compatible client:

```bash
# MCP endpoint
http://localhost:7009/mcp

# Health check
http://localhost:7009/health
```

## Advanced Workflows

For job application automation and other specialized workflows, see the separate workflow repositories that utilize this MCP server as their automation backend.

## Data Persistence

The container supports optional data persistence through mounted volumes:

```bash
# Browser profiles (optional)
./data/profiles:/app/profiles

# Custom scripts (optional)
./data/scripts:/app/scripts

# Logs and screenshots
./data/logs:/app/logs
```

## Troubleshooting

### Container Issues

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f browser-use-mcp

# Restart service
docker-compose restart browser-use-mcp

# Rebuild if needed
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Browser Issues

- Ensure sufficient memory (2GB+ recommended)
- Check Chrome/Chromium dependencies are installed
- Verify headless mode is working
- Test with simple navigation commands

### MCP Connection Issues

- Verify API keys are set correctly in `.env`
- Check network connectivity between containers
- Ensure health endpoint responds: `curl http://localhost:7009/health`
- Test MCP endpoint: `curl http://localhost:7009/mcp`

## Security Notes

- API keys are passed through environment variables only
- Browser runs in a sandboxed container environment
- No persistent browser data stored by default
- Network isolated through Docker networks
- Container runs as non-root user

## Development

### Testing Browser Functionality

```bash
# Test basic browser automation
docker exec -it browser-use-mcp python3 -c "
from browser_use import Agent
from browser_use.llm.openai.chat import ChatOpenAI
import asyncio

async def test():
    agent = Agent(
        task='Navigate to https://httpbin.org/get and take a screenshot',
        llm=ChatOpenAI(model='gpt-4o-mini')
    )
    await agent.run()

asyncio.run(test())
"
```

### Extending the Server

1. Add custom MCP tools by modifying the server implementation
2. Create specialized automation modules
3. Test with your preferred MCP client

## Integration Examples

### With Claude Desktop

Configure in your Claude Desktop MCP settings:

```json
{
  "browser-use": {
    "command": "curl",
    "args": ["-X", "POST", "http://localhost:7009/mcp"]
  }
}
```

### With MCPX Gateway

The server integrates automatically with MCPX gateway for multi-client access.

## Container Approach vs MCPX Integration

### Current MCPX Integration Status

**Important Note**: Browser-use MCP is currently integrated with MCPX using the `uvx` approach that runs directly in the MCPX container, not through this containerized setup.

**Reason**: Browser-use MCP only supports stdio transport (stdin/stdout communication), not HTTP/SSE endpoints like other MCP containers.

**Current Working Solution**:

- MCPX runs `uvx browser-use[cli] --mcp` directly in its container
- This bypasses the containerized browser-use setup entirely

### To Use Container Approach (Future Enhancement)

To properly use the containerized browser-use MCP server with MCPX, we would need to implement a **sidecar container** that:

1. **Translates HTTP/SSE to stdio**: Acts as a bridge between MCPX's HTTP/SSE transport and browser-use's stdio transport
2. **Manages the stdio process**: Starts and manages the `browser-use --mcp` process
3. **Exposes HTTP endpoints**: Provides `/sse` endpoint that MCPX can connect to
4. **Handles MCP protocol**: Translates MCP messages between HTTP and stdio formats

**Potential Architecture**:

```text
MCPX Container -> HTTP/SSE -> Sidecar Container -> stdio -> Browser-Use Container
```

**Current Workaround Assessment**:

The current `uvx` approach works well for now because:

- ✅ Simple to configure and maintain
- ✅ No additional containers needed
- ✅ Direct integration with MCPX
- ❌ Less isolation than container approach
- ❌ Dependencies installed in MCPX container
- ❌ Different pattern from other MCP servers

**Future Consideration**: Implement the sidecar approach when we need better isolation, consistent container patterns, or scaling capabilities.
