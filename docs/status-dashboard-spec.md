# MCP Status Dashboard

## Overview

A lightweight web-based status dashboard that provides real-time visibility into the health, status, and logs of all MCP servers running across the ai-infrastructure Docker Compose stacks.

## Motivation

The mcpx UI shows connected servers but provides limited diagnostics when things go wrong. During the network architecture redesign, debugging required manually running `docker logs`, `docker exec`, and `docker inspect` across multiple containers. A dedicated status dashboard would surface this information in one place.

## Requirements

### Must Have
- **Container health status**: Show health state (healthy/unhealthy/starting) for all MCP-related containers
- **Scrolling log viewer**: Live-tail logs from any selected container, similar to `docker logs -f`
- **Network topology**: Which containers are on which Docker networks
- **Auto-refresh**: Status updates without manual page refresh

### Should Have
- **MCP tool discovery status**: Show which MCP servers have successfully completed tool discovery (tools count) vs pending/failed
- **Startup timing**: Show how long each container took to become healthy (helps diagnose race conditions like the stdio-proxy startup delay)
- **Container resource usage**: Basic CPU/memory metrics per container
- **Log filtering**: Filter logs by level (ERROR, WARN, INFO, DEBUG)

### Nice to Have
- **Dependency graph**: Visual representation of container dependencies (depends_on chains)
- **Quick actions**: Restart individual containers, force recreate a stack
- **Historical uptime**: Track container restart counts and uptime over time
- **Alert on unhealthy**: Visual/audio alert when a container goes unhealthy

## Technical Considerations

### Architecture
- Should run as a container in the ai-infrastructure stack (on `ai-shared` network)
- Needs access to the Docker socket (`/var/run/docker.sock`) for container inspection
- Frontend: Simple single-page app (consider lightweight options — no heavy frameworks)
- Backend: Minimal API that wraps Docker Engine API calls

### Existing Options to Evaluate
- **Portainer** — full Docker management UI (may be overkill)
- **Dozzle** — lightweight log viewer with Docker socket access
- **Uptime Kuma** — health monitoring with alerting
- **Custom build** — Tailored exactly to MCP infrastructure needs

### Container Labels
Consider using Docker labels to identify MCP containers for the dashboard:
- `ai-infra.type=mcp-server` / `gateway` / `platform`
- `ai-infra.stack=mcpx` / `agentgateway` / `memory` / etc.

### Network Access
- Dashboard should be accessible via the mcpx SSL proxy (add an nginx location block) or its own port
- Should NOT be exposed to the internet — local dev tool only

## Non-Goals
- This is NOT a replacement for the mcpx UI — it's a complement for infrastructure debugging
- No authentication needed (local dev only)
- No persistent storage required (ephemeral metrics are fine)

## Open Questions
1. Build custom vs adopt existing tool (Dozzle looks promising for the log viewer piece)?
2. Should it integrate with the existing observability stack (Langfuse/Grafana)?
3. Single dashboard or compose it from multiple lightweight tools?
