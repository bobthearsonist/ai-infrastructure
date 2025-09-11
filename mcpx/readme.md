# MCPX

MCPX is a MCP gateway/proxy. It acts a common entrypoint for multiple MCP servers, routing requests to the appropriate backend based on the request parameters. It solves the problem of ai clients creating their own containers for each instance and instead allows the creation of a single container that can then be sahred between clients.

it also offers the ability to group tools from your MCP sets.

## TODO

- [ ] Add authentication support
- [ ] add tool groups
- [ ] compare to Atrax and MetaMCP to see if they are alternatives

## Usage

the <http://localhost:5173/dashboard> page shows the available MCP servers and their tools.
