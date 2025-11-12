#!/bin/bash

# Test browser-use MCP via direct container exec
echo "Testing browser-use MCP functionality..."

# Test direct MCP communication
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | docker exec -i browser-use-mcp browser-use --mcp

echo "Test completed."
