# azure-devops

Per-server overlay for the [`@azure-devops/mcp`](https://www.npmjs.com/package/@azure-devops/mcp) server that runs inside the shared `stdio-proxy` container.

## What lives here

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Additive Compose overlay — adds the `~/.azure` mount to `stdio-proxy` |
| `servers.partial.json` | Reference snippet for the MCP launch entry (`command`, `args`, `env`) |

This directory is **not a standalone stack**. It exists so that the bytes specific to the Azure DevOps MCP — its credential mount and its launch args — live in one place instead of being scattered across the gateway stack.

## How it's used

The outer stack (today: `mcps/mcpx/docker-compose.yml`) brings both `stdio-proxy` and this overlay in as siblings:

```yaml
include:
  - path: ../../mcps/stdio-proxy/docker-compose.yml   # base proxy
  - path: ../../mcps/azure-devops/docker-compose.yml  # mount overlay
```

Compose merges service definitions by name, so the `volumes:` list from this overlay is appended to the proxy's existing mounts rather than replacing them.

The actual aggregated `servers.json` that the proxy reads (e.g. `mcps/stdio-proxy/servers.windows-work.json`) still has to include the `azure-devops` entry from `servers.partial.json`. There is no auto-merge step today; that file is a template, not an input.

## Why a mount, not a PAT

The MCP launches with `-a azcli`, which tells the Azure SDK to prefer `AzureCliCredential`. Inside the container the `az` binary is installed but has no token cache, so the credential reports unavailable and the SDK falls through `ChainedTokenCredential` to nothing. Mounting `~/.azure` lets the container reuse the host's existing `az login` instead of needing a separate PAT or service principal.
