# 🚀 Quick Start Guide - Browser-Use MCP Server

## What This Provides

✅ **Browser-Use MCP Server**: AI-powered browser automation through Model Context Protocol
✅ **MCPX Integration**: Connected via `uvx` approach (not container-based)
✅ **Container Setup**: Available for standalone testing and development
✅ **Management Tools**: Scripts for container management and testing

## 🏗️ Current Architecture

### MCPX Integration (Active)

Browser-use is integrated with MCPX gateway using the `uvx` approach:

- **Location**: Runs inside MCPX container via `uvx browser-use[cli] --mcp`
- **Transport**: stdio (stdin/stdout communication)
- **Tools Available**: 14 browser automation tools accessible through MCPX
- **Configuration**: `./mcps/mcpx/mcp.json`

### Container Setup (Development/Testing)

The containerized version is available for development and testing:

```bash
cd ./mcps/browser-use

# Setup container for testing
./manage.sh setup
```

**Note**: This container is NOT used by MCPX. See "Container Approach vs MCPX Integration" in README.md for details.

## 🎯 Using Browser-Use MCP

### Through MCPX Gateway

Browser-use tools are available through MCPX at `http://localhost:9000`:

**Available Tools**:

- `browser_navigate` - Navigate to URLs
- `browser_click` - Click elements on pages
- `browser_type` - Type text into form fields
- `browser_get_state` - Get current page state and elements
- `browser_extract_content` - Extract structured content from pages
- `browser_scroll` - Scroll page up or down
- `browser_go_back` - Navigate back in browser history
- `browser_list_tabs` - List all open browser tabs
- `browser_switch_tab` - Switch to different tab
- `browser_close_tab` - Close specific tab
- `retry_with_browser_use_agent` - Use AI agent for complex tasks
- `browser_list_sessions` - List active browser sessions
- `browser_close_session` - Close specific browser session
- `browser_close_all` - Close all browser sessions

### Through Direct MCP Clients

Configure in Claude Desktop or other MCP clients:

```json
{
  "mcpServers": {
    "browser-use": {
      "command": "uvx",
      "args": ["browser-use[cli]", "--mcp"],
      "env": {
        "OPENAI_API_KEY": "your-api-key-here",
        "BROWSER_USE_HEADLESS": "true"
      }
    }
  }
}
```

## 🛠️ Container Management (Development)

### Setup and Testing

```bash
# Initial setup
./manage.sh setup

# Start container services
./manage.sh start

# Check status
./manage.sh status

# View logs
./manage.sh logs

# Stop services
./manage.sh stop
```

### Testing Container MCP

```bash
# Test health endpoint
curl http://localhost:7009/health

# Test MCP endpoint (if configured for HTTP)
curl http://localhost:7009/mcp
```

## 📁 Infrastructure File Structure

```
browser-use/
├── docker-compose.yml          # Container configuration
├── Dockerfile                  # Container build instructions
├── manage.sh                   # Management script
├── .env.example               # Environment template
├── .env                       # API keys and configuration
├── README.md                  # Architecture and integration notes
├── QUICKSTART.md              # This file
└── data/                      # Container data storage
    ├── browser-cache/         # Browser cache
    └── profiles/             # Browser profiles
```

## 🔧 MCPX Gateway Status

Check browser-use integration status:

```bash
# View MCPX logs for browser-use connection
cd ./mcps/mcpx
docker compose logs mcpx --tail=20 | grep browser-use

# Check MCPX status
curl -s http://localhost:9000/status
```

## 🐛 Troubleshooting

### MCPX Integration Issues

```bash
# Check if browser-use is connected in MCPX logs
docker compose logs mcpx | grep "STDIO client connected.*browser-use"

# Restart MCPX to reload configuration
docker compose restart mcpx
```

### Container Issues

```bash
# Rebuild container if needed
./manage.sh stop
docker compose build --no-cache browser-use-mcp
./manage.sh start

# Check container logs
docker compose logs browser-use-mcp
```

### API Key Issues

```bash
# Verify API keys are set
grep OPENAI_API_KEY .env
grep ANTHROPIC_API_KEY .env

# Test API key works with uvx
uvx browser-use[cli] --help
```

## 🚀 For Job Application Workflows

**Note**: Job application automation has been moved to a separate repository:

- **Location**: `~/Repositories/job-hunt/ai job form filler/`
- **Workflow Scripts**: `manage_workflow.sh` for job application automation
- **Resume Management**: Dedicated resume data and application logic
- **Documentation**: See `QUICKSTART.md` in the job hunt repository

## 📝 Key Points

- **MCPX Integration**: Browser-use runs via `uvx` in MCPX container (not this container)
- **Container Purpose**: Development, testing, and standalone use cases
- **Tool Access**: 14 browser automation tools available through MCPX gateway
- **Separation**: Infrastructure (here) vs workflow automation (job hunt repo)
- **Transport**: stdio protocol only (no HTTP/SSE endpoints)

---

Browser-use MCP is ready and integrated with your AI infrastructure! Access tools through MCPX gateway at `http://localhost:9000`.

```

```
