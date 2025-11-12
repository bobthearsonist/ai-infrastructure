# MCPX

MCPX is a MCP gateway/proxy. It acts a common entrypoint for multiple MCP servers, routing requests to the appropriate backend based on the request parameters. It solves the problem of ai clients creating their own containers for each instance and instead allows the creation of a single container that can then be sahred between clients.

it also offers the ability to group tools from your MCP sets.

see <https://docs.lunar.dev/> and <https://docs.lunar.dev/mcpx/architecture>

## TODO

- [ ] Add authentication support
- [ ] add tool groups
- [ ] compare to Atrax and MetaMCP to see if they are alternatives

## Usage

the <http://localhost:5173/dashboard> page shows the available MCP servers and their tools.

## Setup

```bash
docker build -t mcpx .
docker run -p 5173:5173 mcpx
```

the server needs to be restarted after changes to the [mcp.json](mcp.json) file.

## Configuration

i had to modify the setup for claude desktop form the official docs.

## HTTPS Support

Some clients require HTTPS connections - the nginx SSL proxy provides this by terminating SSL and forwarding to MCPX.

```bash
# Start with SSL proxy
docker-compose up -d

# HTTPS endpoints
https://localhost:9443/mcp   # MCP endpoint
https://localhost:9443/sse   # SSE endpoint
https://localhost:5443       # Dashboard
```
