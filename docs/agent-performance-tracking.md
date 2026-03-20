# AI Agent Performance Tracking

Design doc for measuring and comparing AI coding agent performance across clients (Claude Code, OpenCode, GitHub Copilot, etc.) as configuration changes are made (adding MCPs, RAG, skills, etc.).

**Status:** Draft
**Created:** 2026-03-05

---

## Problem

We add MCPs, RAG indexes, skills, and other configuration to improve AI agent performance, but have no way to measure whether these changes actually help. We need a cross-agent measurement framework.

## Goals

1. Track token usage, cost, and tool usage across all AI coding clients
2. Measure the impact of configuration changes (before/after adding an MCP, skill, etc.)
3. Compare agent performance head-to-head on comparable tasks
4. Keep collection friction low enough to actually use daily

---

## Metrics Taxonomy

### Tier 1 - Quantitative (auto-collectible)

| Metric | Source | Why it matters |
|--------|--------|---------------|
| Token usage (input/output/cache) | ccusage family, session logs | Direct cost driver |
| Cost (USD) | ccusage family | Bottom line |
| MCP tool calls (count, per-tool) | agentgateway Prometheus | Cross-agent; measures how actively agent uses infrastructure |
| MCP tool latency | agentgateway OTel spans | Are tools fast enough or slowing the agent down? |
| Session duration | Session logs / manual | Time efficiency |

### Tier 2 - Efficiency (semi-automated)

| Metric | Source | Why it matters |
|--------|--------|---------------|
| Tokens per task | Derived (tokens / task count) | Normalizes across task sizes |
| Tool calls per task | Derived | Is the agent precise or flailing? |
| Error/retry rate | Session logs, build output | Failed tool calls, build failures |
| Context compactions | Session logs | Hit the limit = task too large or agent wasteful |
| Files touched | Git diff | Scope of changes |
| User corrections/turns | Manual / session review | Proxy for autonomy |

### Tier 3 - Quality (requires judgment)

| Metric | Source | Why it matters |
|--------|--------|---------------|
| Task completion | Manual (success/partial/fail) | Did it actually work? |
| Correctness | Manual / code review | Did it do the RIGHT thing? |
| Code quality | Manual / lint results | Did it introduce tech debt? |

---

## Data Sources

### Automatic: ccusage family (token & cost tracking)

The [ccusage](https://github.com/ryoppippi/ccusage) project (11k+ stars) parses local JSONL session files to extract token usage and cost data. It supports multiple agents through separate packages:

| Package | Agent | Data Location |
|---------|-------|---------------|
| `ccusage` | Claude Code | `~/.claude/projects/**/*.jsonl` |
| `@ccusage/opencode` | OpenCode | OpenCode session files |
| `@ccusage/codex` | OpenAI Codex CLI | Codex session files |
| `@ccusage/amp` | Amp | Amp session files |
| `@ccusage/pi` | Pi-agent | Pi-agent session files |

**Key features:**
- Daily, weekly, monthly, session-level reports
- Per-model breakdown (Opus, Sonnet, etc.)
- JSON output (`--json`) for programmatic consumption
- 5-hour billing block tracking (Claude-specific)
- Project/instance grouping (`--instances`)
- MCP server (`@ccusage/mcp`) for querying from within agents

**Example commands:**
```bash
# Daily report with JSON output
npx ccusage@latest daily --json

# Session-level with project breakdown
npx ccusage@latest session --instances --since 20260301

# OpenCode equivalent
npx @ccusage/opencode@latest daily --json

# Per-model cost breakdown
npx ccusage@latest daily --breakdown
```

### Automatic: agentgateway metrics (MCP tool usage)

Already running in our infrastructure. Tracks MCP tool usage across ALL clients since they all route through agentgateway.

**Prometheus metrics available:**
- `agentgateway_requests_total` - HTTP requests by client, method, status
- `agentgateway_mcp_requests` - MCP tool calls
- `tool_calls_total` - Tool calls by server and tool name
- `list_calls_total` - List operations
- Span-derived latency histograms from OTel Collector

**Access:** Grafana at `:3000`, Prometheus at `:9090`, Jaeger at `:16686`

### Automatic: Langfuse (LLM observability)

Already deployed at `:3100`. Provides:
- LLM tracing (calls, chains, agent actions)
- Cost tracking and latency metrics
- Evaluations and scoring
- Datasets for benchmarking

**Gap:** AI coding clients don't natively send traces to Langfuse. Would need integration work or a proxy approach.

### Manual: Session log

For metrics that can't be auto-collected, a lightweight manual log.

---

## Implementation Plan

### Phase 1: Automated collection (low effort)

1. **Set up ccusage scheduled reports**
   - Run `ccusage daily --json` and `@ccusage/opencode daily --json` on a schedule (or manually)
   - Append results to a JSONL file in this repo: `data/token-usage.jsonl`
   - Script: PowerShell/bash wrapper that runs both and merges output

2. **Build Grafana dashboards for agentgateway**
   - Already have "MCP Infrastructure" dashboard
   - Add panels for: tool calls over time, tool call breakdown by tool, latency trends
   - Add labels/annotations for config changes ("added Qdrant RAG", "added skill X")

3. **Install @ccusage/mcp**
   - Add to agentgateway config so agents can self-report their own usage mid-session
   - Useful for agents to be cost-aware

### Phase 2: Unified session log (medium effort)

Create a lightweight session logging mechanism. Each entry captures one "task session" across any agent.

**Schema:**
```jsonc
{
  // Auto-populated
  "id": "uuid",
  "timestamp": "2026-03-05T10:30:00Z",
  
  // Agent context
  "agent": "claude-code",        // claude-code | opencode | copilot | cline
  "model": "claude-sonnet-4",  // primary model used
  
  // Task context
  "task_type": "bug-fix",        // bug-fix | feature | refactor | debug | research | config
  "task_description": "Fix null ref in user lookup",
  "work_item_id": "156553",      // optional ADO work item
  "project": "matching",         // which repo/project
  
  // Quantitative metrics
  "tokens_input": 125000,
  "tokens_output": 15000,
  "tokens_cache_read": 80000,
  "tokens_cache_write": 20000,
  "cost_usd": 1.25,
  "duration_minutes": 45,
  "tool_calls": 87,
  "files_changed": 5,
  "context_compactions": 0,
  
  // Quality metrics (manual)
  "outcome": "success",          // success | partial | fail
  "user_corrections": 2,         // times you had to redirect the agent
  "notes": "Added qdrant RAG, agent found the right files faster",
  
  // Configuration snapshot
  "config": {
    "mcps": ["memory", "sequential-thinking", "qdrant", "context7"],
    "skills_active": ["profisee-api-architecture", "dotnet"],
    "rag_sources": ["qdrant-code", "qdrant-work"],
    "custom_instructions": true
  }
}
```

**Collection options (pick one):**
- **PowerShell script** - prompted form after sessions, appends to JSONL
- **CLI tool** - `node scripts/log-session.js --agent claude-code --outcome success ...`
- **Obsidian template** - structured frontmatter in session summaries (already doing summaries, just add fields)

### Phase 3: Benchmarking (higher effort)

Define repeatable tasks to test configuration changes against:

1. **Create a benchmark task suite** - 5-10 coding tasks of varying complexity stored in `benchmarks/`
2. **Run each task** with a specific agent + config combo
3. **Log results** using the Phase 2 schema
4. **Compare** before/after metrics in Grafana or a simple analysis script

**Example benchmark tasks:**
- Fix a known bug in a test repo (measures: accuracy, tokens, time)
- Add a feature with a spec (measures: completeness, code quality)
- Navigate unfamiliar codebase to answer questions (measures: RAG effectiveness)
- Refactor a module (measures: correctness, scope)

---

## Analysis & Visualization

| Question | Data Source | Tool |
|----------|------------|------|
| How much am I spending per day/week? | ccusage JSON | Grafana or ccusage CLI |
| Which MCP tools are used most? | agentgateway Prometheus | Grafana |
| Did adding RAG reduce token usage? | Session log + ccusage | Compare before/after periods |
| Which agent is best for bug fixes? | Session log | Query by agent + task_type |
| Are tool calls getting faster/slower? | agentgateway OTel spans | Jaeger / Grafana |

---

## Other Tools to Evaluate

| Tool | What it does | Status |
|------|-------------|--------|
| [ccusage](https://github.com/ryoppippi/ccusage) | Parse Claude Code/OpenCode/Codex session files for token usage & cost | Ready to use |
| [@ccusage/mcp](https://www.npmjs.com/package/@ccusage/mcp) | MCP server exposing ccusage data to agents | Ready to use |
| [Langfuse](https://langfuse.com) | LLM observability, evals, datasets, cost tracking | Already deployed, needs client integration |
| agentgateway metrics | MCP tool call tracking via Prometheus | Already running |
| OpenTelemetry | Distributed tracing standard | Already collecting via OTel Collector |

---

## Open Questions

- [ ] Does GitHub Copilot expose any session/token data locally? (ccusage doesn't support it)
- [ ] Can we hook into OpenCode's session storage format for richer data than @ccusage/opencode provides?
- [ ] Should session logs live in this repo, Obsidian, or a SQLite DB?
- [ ] Is Langfuse worth integrating if ccusage + agentgateway covers most metrics?
- [ ] Should we build the session logger as a PowerShell script, Node CLI, or Obsidian template?
- [ ] Can we use Grafana annotations API to mark config changes automatically?

---

## Next Steps

1. Run `npx ccusage@latest daily --json` and `npx @ccusage/opencode@latest daily --json` to see what data we get today
2. Decide on session log format and collection method
3. Build Grafana dashboard for agentgateway tool usage trends
4. Add `@ccusage/mcp` to agentgateway config
