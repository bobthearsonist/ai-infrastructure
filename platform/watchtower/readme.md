# Watchtower - Automatic Docker Image Updates

[Watchtower](https://containrrr.dev/watchtower/) monitors running containers and automatically pulls + restarts them when a new image is available.

## Configuration

- **Opt-in only**: `WATCHTOWER_LABEL_ENABLE=true` — only containers with the label `com.centurylinklabs.watchtower.enable=true` get updated
- **Poll interval**: Every 24 hours (`86400` seconds)
- **Cleanup**: Old images are removed after updates (`WATCHTOWER_CLEANUP=true`)
- **Notifications**: Logs only (`logger://`)

## Monitored Containers

| Container | Compose Location | Image |
|---|---|---|
| mcpx | `mcps/mcpx/` | `us-central1-docker.pkg.dev/.../mcpx:latest` |
| agentgateway | `gateways/agentgateway/` | `ghcr.io/agentgateway/agentgateway:latest` |
| mcp_playwright | `mcps/playwright/` | `mcr.microsoft.com/playwright/mcp:latest` |
| qdrant | `mcps/qdrant-mcp/` | `qdrant/qdrant:latest` |
| otel-collector | `platform/observability/` | `otel/opentelemetry-collector-contrib:latest` |
| jaeger | `platform/observability/` | `jaegertracing/all-in-one:latest` |
| prometheus | `platform/observability/` | `prom/prometheus:latest` |
| grafana | `platform/observability/` | `grafana/grafana:latest` |

### Not monitored (by design)

- **Locally-built services** (qdrant-mcp, indexers, stdio-proxy, nginx proxies) — no remote image to pull
- **Docker-in-Docker spawned containers** (hass-mcp, browser-use) — ephemeral, managed by their proxy
- **Databases** (postgres, redis, clickhouse in langfuse) — schema migrations need manual control

## Usage

```bash
# Start
docker compose up -d

# Check update logs
docker logs watchtower

# Force an update check now
docker exec watchtower /watchtower --run-once

# Stop
docker compose down
```

## Adding a new container

Add this label to any service in any compose file:

```yaml
labels:
  - "com.centurylinklabs.watchtower.enable=true"
```

Watchtower watches all labeled containers across the Docker daemon — they don't need to be in the same compose file.
