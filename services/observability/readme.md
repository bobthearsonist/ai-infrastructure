# Observability Stack

OpenTelemetry Collector, Jaeger, Prometheus, and Grafana for monitoring the AI infrastructure.

## Architecture

```text
agentgateway ──OTLP──► OTel Collector ──► Jaeger (traces)
                              │
                              └──► Prometheus (span metrics :8889)
                                        │
agentgateway ──metrics──► Prometheus ◄──┘
                              │
                              └──► Grafana (dashboards)
                                        │
                              Jaeger ◄──┘ (trace queries)
```

## Components

| Service | Port | Purpose |
| ------- | ---- | ------- |
| OpenTelemetry Collector | 4317/4318 (internal) | Receives OTLP traces, generates span metrics |
| Jaeger | 16686 | Distributed tracing UI |
| Prometheus | 9090 | Metrics collection & storage |
| Grafana | 3000 | Dashboards & visualization |

## Quick Start

```bash
docker-compose up -d
```

## Access

- **Grafana**: <http://localhost:3000> (admin/admin)
- **Prometheus**: <http://localhost:9090>
- **Jaeger**: <http://localhost:16686>

## Dashboards

Pre-configured dashboards in Grafana:

- **MCP Infrastructure**: Dynamic dashboard showing connections, tool calls, latency, and errors

## Data Sources

Grafana is pre-configured with:

- **Prometheus** - for metrics queries
- **Jaeger** - for trace queries

## OpenTelemetry Collector

The OTel Collector serves as the central telemetry hub:

1. **Receives** OTLP traces from agentgateway on ports 4317 (gRPC) / 4318 (HTTP)
2. **Exports** traces to Jaeger on port 14317
3. **Generates** span-derived metrics via the `spanmetrics` connector
4. **Exposes** metrics for Prometheus scraping on port 8889

Configuration: `otel-collector-config.yml`

## Prometheus Scrape Targets

| Target | Endpoint | Metrics |
| ------ | -------- | ------- |
| agentgateway | host.docker.internal:15020 | Gateway metrics (requests, MCP calls) |
| otel-collector-spanmetrics | otel-collector:8889 | Span-derived metrics (latency, counts) |

## Jaeger Features

- **Search**: Find traces by service, operation, tags, duration
- **Monitor**: Service performance metrics (requires OTel span metrics)
- **Compare**: Compare traces across time periods
