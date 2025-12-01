# Observability Stack

Prometheus, Grafana, and Jaeger for monitoring the AI infrastructure.

## Components

| Service | Port | Purpose |
| ------- | ---- | ------- |
| Prometheus | 9090 | Metrics collection & storage |
| Grafana | 3000 | Dashboards & visualization |
| Jaeger | 16686 | Distributed tracing |

## Quick Start

```bash
docker-compose up -d
```

## Access

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686

## Dashboards

Pre-configured dashboards:
- **AgentGateway - MCP Clients**: Shows connected clients, tool calls, and request metrics

## Data Sources

Grafana is pre-configured with:
- Prometheus (for metrics)
- Jaeger (for traces)

## Metrics Scraped

Prometheus scrapes:
- `agentgateway` at `host.docker.internal:15020`
