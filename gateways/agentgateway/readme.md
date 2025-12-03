# agentgateway

agentgateway is an open-source MCP gateway/proxy from the Linux Foundation. It serves as a central entrypoint for multiple MCP servers, routing requests to appropriate backends.

- 📖 **Docs**: <https://agentgateway.dev/docs/>
- 🔗 **GitHub**: <https://github.com/agentgateway/agentgateway>
- 🏗️ **Architecture**: See [root README](../../README.md)

## Current Status

✅ **Working** - Serving 24+ tools from 3 MCP backends.

## Ports

| Port  | Protocol   | Description              |
| ----- | ---------- | ------------------------ |
| 3847  | HTTP       | MCP endpoint             |
| 15001 | HTTP       | Admin UI Dashboard       |
| 15020 | Prometheus | Metrics endpoint         |
| 3443  | HTTPS      | MCP endpoint (via nginx) |

## Configured Backends

| MCP Server          | Status     | Transport       | Source                                          | Docs                                          |
| ------------------- | ---------- | --------------- | ----------------------------------------------- | --------------------------------------------- |
| sequential-thinking | ✅ Running | SSE             | [stdio-proxy](../../mcps/stdio-proxy/readme.md) | [→](../../mcps/sequential-thinking/readme.md) |
| memory              | ✅ Running | SSE             | [stdio-proxy](../../mcps/stdio-proxy/readme.md) | [→](../../mcps/memory/readme.md)              |
| kapture             | ✅ Running | SSE + WebSocket | [stdio-proxy](../../mcps/stdio-proxy/readme.md) | [→](../../mcps/kapture/readme.md)             |
| context7            | ✅ Running | SSE             | container                                       | [→](../../mcps/context7/readme.md)            |
| playwright          | ✅ Running | SSE             | container                                       | [→](../../mcps/playwright/readme.md)          |
| browser-use         | ✅ Running | SSE             | container                                       | [→](../../mcps/browser-use/readme.md)         |
| hass-mcp            | ✅ Running | SSE             | container                                       | [→](../../mcps/hass-mcp/readme.md)            |
| langfuse-prompts    | ✅ Running | MCP             | container                                       | [→](../../platform/langfuse/README.md)        |

## Setup

### Prerequisites

1. Create the shared Docker network:

   ```bash
   docker network create mcpx_ai-infrastructure
   ```

2. Start stdio-proxy (required for sequential-thinking and memory):

   ```bash
   cd ../../mcps/stdio-proxy
   docker-compose up -d
   ```

### Run

```bash
docker-compose up -d
```

### Access

- **Admin UI**: `http://localhost:15001/ui`
- **MCP Endpoint**: `http://localhost:3847/mcp`

## Configuration

### config.yaml

The `config.yaml` file defines which MCP backends to connect to:

```yaml
version: v1
listeners:
  - name: mcp-listener
    protocol: MCP
    address: 0.0.0.0:3847

backends:
  mcp:
    targets:
      - name: sequential-thinking
        sse:
          host: http://host.docker.internal:7030/servers/sequential-thinking/sse
      - name: memory
        sse:
          host: http://host.docker.internal:7030/servers/memory/sse
```

### Adding a New Backend

1. **SSE-based MCP** - Add directly to `config.yaml`:

   ```yaml
   - name: new-mcp
     sse:
       host: http://host.docker.internal:PORT/sse
   ```

2. **stdio-based MCP** - Add to [stdio-proxy](../../mcps/stdio-proxy/readme.md) first, then reference it here.

3. **Restart**:

   ```bash
   docker-compose restart agentgateway
   ```

### MCP Backend Architecture (Important!)

⚠️ **All MCP targets must be in a single `- mcp:` backend block.** This is by design.

**Why?** From the agentgateway source code (`router.rs`):

```rust
pub struct McpBackendGroup {
    pub targets: Vec<Arc<McpTarget>>,  // Vector of targets in ONE group
    pub stateful: bool,                 // Single stateful mode for whole group
}
```

**Design rationale:**

1. **Multiplexing Pattern**: agentgateway federates tools from multiple MCP servers into a unified interface. The `backends` array at route level is for **different protocol types** (MCP/A2A/OpenAPI), not for separating MCP targets.

2. **Stateful Mode Scope**: `statefulMode` applies to the entire backend group - session management must be consistent across all targets.

3. **Tool Namespace**: If you use multiple `- mcp:` blocks, only the last one's tools will be returned. The gateway merges multiple **targets** within a single MCP backend, not multiple MCP backend groups.

**Correct configuration:**

```yaml
backends:
  - mcp:
      statefulMode: stateless
      targets:
        - name: server-a
          sse:
            host: http://host.docker.internal:7001/sse
        - name: server-b
          sse:
            host: http://host.docker.internal:7002/sse
        - name: server-c
          mcp:
            host: http://host.docker.internal:7003/mcp
```

**Incorrect configuration (only server-c tools returned):**

```yaml
backends:
  - mcp:
      targets:
        - name: server-a
          sse:
            host: http://host.docker.internal:7001/sse
  - mcp: # ❌ Second mcp block overwrites first!
      targets:
        - name: server-c
          mcp:
            host: http://host.docker.internal:7003/mcp
```

See [MCP Multiplexing documentation](https://agentgateway.dev/docs/mcp/connect/multiplex/) for more details.

### SSE Endpoints Require Stateless Mode

⚠️ **Always use `statefulMode: stateless` when connecting to SSE-based MCP servers.**

**The Problem**: SSE (Server-Sent Events) connections have a lifecycle mismatch with MCP session semantics.

1. **SSE Connection Lifecycle**: An SSE connection is a long-lived HTTP GET request. When agentgateway closes the connection after receiving a response, the SSE session on the server is destroyed.

2. **MCP Session Semantics**: MCP expects sessions to persist across multiple requests. After `initialize`, subsequent calls like `tools/list` should reuse the same session.

3. **The Mismatch**:
   - agentgateway opens SSE connection, sends `initialize`, gets response
   - SSE connection closes (HTTP disconnect)
   - Server destroys the session
   - Later, `tools/list` arrives with the same session ID
   - Server rejects: "Received request before initialization was complete"

**The Solution**: `statefulMode: stateless` tells agentgateway to automatically wrap every request with a fresh `initialize` call, treating each request as an independent transaction.

```yaml
backends:
  - mcp:
      statefulMode: stateless  # Required for SSE targets
      targets:
        - name: sequential-thinking
          sse:
            host: http://host.docker.internal:7030/servers/sequential-thinking/sse
```

**Note**: This applies to SSE (`sse:`) transport. Streamable HTTP (`mcp:`) transport handles sessions differently and may work in stateful mode, but using stateless mode for mixed SSE/MCP backends is safe.

### DNS Notes

Use `host.docker.internal:PORT` for backend URLs. Container-to-container DNS doesn't work reliably with agentgateway's Go resolver.

## Features

agentgateway provides enterprise features not available in simpler gateways:

| Feature            | Description                  |
| ------------------ | ---------------------------- |
| **Authentication** | JWT, OAuth2 support          |
| **Authorization**  | CEL-based RBAC policies      |
| **Rate Limiting**  | Per-client rate limits       |
| **Native TLS**     | Built-in SSL/TLS             |
| **OpenAPI → MCP**  | Convert OpenAPI specs to MCP |
| **A2A Protocol**   | Agent-to-agent communication |
| **Hot Reload**     | Config updates via xDS       |

## Comparison to MCPX

| Feature            | MCPX | agentgateway |
| ------------------ | ---- | ------------ |
| MCP Gateway        | ✅   | ✅           |
| Authentication     | ❌   | ✅           |
| Authorization/RBAC | ❌   | ✅           |
| Native TLS         | ❌   | ✅           |
| Rate Limiting      | ❌   | ✅           |
| Hot Reload         | ❌   | ✅           |

## Docker Compose

This setup runs two containers:

| Container    | Image                               | Purpose                        |
| ------------ | ----------------------------------- | ------------------------------ |
| agentgateway | `ghcr.io/agentgateway/agentgateway` | MCP gateway (Linux Foundation) |
| nginx-proxy  | `nginx:alpine`                      | SSL termination, CDP proxy     |

### nginx-proxy

The nginx-proxy is our custom addition (not part of agentgateway) that provides:

| Port  | Purpose            | Direction                     |
| ----- | ------------------ | ----------------------------- |
| 3443  | HTTPS MCP endpoint | Clients → agentgateway        |
| 15443 | HTTPS Admin UI     | Browser → agentgateway        |
| 9223  | CDP proxy          | Containers → host Chrome:9222 |

**Why CDP proxy?** Playwright and browser-use MCPs run inside Docker containers but need to control Chrome running on the host. Containers can't reach `localhost:9222` directly, so nginx proxies `host.docker.internal:9223` → `host:9222`.

> **Note:** Kapture doesn't use this proxy. The Chrome extension (running on host) connects directly to stdio-proxy:61822. The connection direction is reversed - host→container instead of container→host.

## Troubleshooting

### DNS Resolution Failed

If you see "backends required DNS resolution which failed":

1. Use `host.docker.internal:PORT` for backend URLs
2. Ensure docker-compose.yml has `dns: - 127.0.0.11`

### prompts/list 500 Error

Expected - some MCP backends don't implement prompts. Doesn't affect tool discovery.

### resources/list 500 Error (Multiplexing Limitation)

When using **more than one MCP target** (multiplexing mode), `resources/list` and `resources/templates/list` return HTTP 500 errors. **This is expected behavior**, not a bug.

**What triggers multiplexing**: Having `backend.targets.len() > 1`. From the source (`handler.rs`):

```rust
let default_target_name = if backend.targets.len() != 1 {
    is_multiplexing = true;  // More than 1 target = multiplexing
    None
} else {
    Some(backend.targets[0].name.to_string())  // Single target = no multiplexing
};
```

With our current 8 targets (sequential-thinking, memory, kapture, etc.), we're in multiplexing mode.

**Why it happens**: agentgateway hasn't implemented URL mapping for resources in multiplexing mode. From `session.rs`:

```rust
ClientRequest::ListResourcesRequest(_) => {
    if !self.relay.is_multiplexing() {
        // Works with single target
    } else {
        // TODO(https://github.com/agentgateway/agentgateway/issues/404)
        Err(UpstreamError::InvalidMethodWithMultiplexing(...))
    }
}
```

**Why tools work but resources don't**:

- `tools/list` - Tool names get prefixed with target name (e.g., `context7_resolve-library-id`)
- `resources/list` - Would need URL rewriting/mapping which isn't implemented yet

**Resolution options**:

1. **Accept the limitation** - If you don't need MCP resources, ignore the 500s. Tool discovery works fine.
2. **Use single target** - Resources work with only one MCP target configured.
3. **Track upstream** - [agentgateway/agentgateway#404](https://github.com/agentgateway/agentgateway/issues/404)

## TODO

- [ ] Configure authentication (JWT/OAuth2)
- [ ] Set up RBAC policies
- [ ] Configure rate limiting
- [ ] Set up xDS for hot-reload
- [ ] Restrict sequential-thinking MCP to local models only (hosted models/agents like Cline and GitHub Copilot provide similar chain-of-thought functionality in the client)

## Related

- [Client Configuration](../../clients/) - Configure AI clients to connect
- [stdio-proxy](../../mcps/stdio-proxy/readme.md) - stdio→SSE bridge for MCPs
- [Langfuse](../../platform/langfuse/README.md) - LLM observability platform
