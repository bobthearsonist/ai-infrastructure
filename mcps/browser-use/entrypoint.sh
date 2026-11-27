#!/bin/bash

# Set up environment
export PYTHONUNBUFFERED=1
export DISPLAY=${DISPLAY:-:99}

# API keys arrive as files named after their env var (OPENAI_API_KEY, ...)
# so they stay out of the container config that `docker inspect` shows.
SECRETS_DIR=${SECRETS_DIR:-/run/secrets/browser-use}
if [ -d "$SECRETS_DIR" ]; then
    for f in "$SECRETS_DIR"/*; do
        [ -f "$f" ] || continue
        name=$(basename "$f")
        [[ "$name" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
        export "$name=$(<"$f")"
    done
fi

# If running in MCP-only mode (for proxy), just run browser-use --mcp
if [ "$1" = "browser-use" ] && [ "$2" = "--mcp" ]; then
    echo "Running in MCP-only mode for proxy"
    exec browser-use --mcp
fi

# Start Xvfb for headless display (in case we need it)
if [ "$BROWSER_USE_HEADLESS" = "false" ]; then
    echo "Starting Xvfb for display..."
    Xvfb :99 -screen 0 1920x1080x24 &
    export DISPLAY=:99
fi

echo "Browser-use MCP container started"
echo "Health check available at :7009/health"
echo "Ready for MCP connections..."


# Start health server in background using a separate script
python3 /app/health_server.py &
HEALTH_PID=$!

# Start the browser-use MCP server in background
browser-use --mcp &
BROWSER_USE_PID=$!

# Wait for both processes
wait $HEALTH_PID $BROWSER_USE_PID
