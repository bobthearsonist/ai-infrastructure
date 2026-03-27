# Code Intelligence for AI Agents

> Research into giving AI coding agents (Claude Code, OpenCode, GitHub Copilot) IDE-like code navigation across connected .NET/C# projects.
>
> Last updated: 2026-03-24

---

## Architecture Overview

```
                         ┌──────────────────────────┐
                         │      AI Coding Agent      │
                         │  (Claude Code, OpenCode,  │
                         │   Copilot, Cursor, etc.)  │
                         └────────────┬─────────────┘
                                      │ queries via MCP / LSP
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
   ┌─────────────────┐   ┌─────────────────────┐   ┌──────────────────┐
   │  Code Navigator  │   │  Code Graph Engine   │   │  Search Engine    │
   │                  │   │                      │   │                   │
   │  • Go to def     │   │  • Call hierarchy    │   │  • Vector/semantic│
   │  • Find refs     │   │  • Dependency graphs │   │  • Keyword (BM25) │
   │  • Hover/types   │   │  • Blast radius      │   │  • Structural     │
   │  • Implementations│  │  • Inheritance trees │   │    (AST-aware)    │
   │                  │   │  • Impact analysis   │   │                   │
   └────────┬─────────┘   └──────────┬───────────┘   └────────┬──────────┘
            │                        │                         │
            │  real-time             │  indexed / live         │  indexed
            │                        │                         │
   ┌────────▼─────────┐   ┌─────────▼───────────┐   ┌────────▼──────────┐
   │  Language Server  │   │  Compiler Semantic   │   │  Index Store      │
   │  (LSP)           │   │  Model               │   │                   │
   │                  │   │                      │   │  • Vector DB      │
   │  Roslyn LS,      │   │  Roslyn (C#),        │   │  • Graph DB       │
   │  csharp-ls       │   │  SCIP indexers,      │   │  • Search index   │
   │                  │   │  Tree-sitter (broad) │   │                   │
   └────────┬─────────┘   └──────────┬───────────┘   └────────┬──────────┘
            │                        │                         │
            └───────────────────┬────┴─────────────────────────┘
                                │
                                ▼
              ┌──────────────────────────────────┐
              │          Source Code              │
              │                                  │
              │  Solutions, projects, repos       │
              │  (single-solution or cross-repo)  │
              └──────────────────────────────────┘
```

### What each layer provides

| Layer | Purpose | Answers |
|-------|---------|---------|
| **Code Navigator** | Real-time point queries against live code | "Where is this defined?" "Who references this?" |
| **Code Graph Engine** | Structural relationship traversal | "Who calls this?" "What breaks if I change this?" "What implements this interface?" |
| **Search Engine** | Content discovery across large codebases | "Find code similar to X" "Find all files matching this pattern" |
| **Compiler Semantic Model** | Source of truth for symbol resolution | Resolves types, generics, overloads, cross-project references |
| **Index Store** | Persistent queryable data | Pre-computed graphs, embeddings, search indexes |

### The gap today

Most AI agents only have the **Search Engine** layer (vector RAG + grep). Some have basic **Code Navigation** via LSP (definitions, references). Almost none have the **Code Graph Engine** — the layer that enables call hierarchies, dependency graphs, blast radius, and inheritance traversal.

---

## Background

We have a Qdrant-based RAG index over our codebase. It works for semantic similarity search but is underutilized — vector search alone can't answer structural questions about code. AI agents working across our connected Profisee .NET projects need the same understanding an IDE provides.

The initial investigation started with [n2-arachne](https://github.com/choihyunsus/n2-arachne), a code context assembly tool that uses tiered retrieval (BM25 + optional semantic vectors + dependency graph traversal) with caching layers. While immature (43 stars), it surfaced an important insight: the gap isn't "better RAG" — it's **structural code intelligence**.

---

## The Problem

### What vector RAG gives us

- "Find me code that looks similar to this query"
- Semantic similarity across documents and code chunks
- Good for: finding related code, documentation lookup, pattern matching

### What vector RAG cannot do

- **Call hierarchy** — who calls this method? What does it call? Trace the full call chain.
- **Dependency graphs** — how do projects depend on each other? What's the coupling between services?
- **Blast radius / impact analysis** — if I change this interface, what breaks? How far do the ripples go?
- **Inheritance trees** — what's the type hierarchy? What extends this base class?
- **Implementation discovery** — show me every class that implements this interface across all projects.

IDEs know all of this through the compiler's semantic model. AI agents are blind to it — they grep, they vector-search, but they don't understand the structure.

### Why this matters for our workflow

We work across multiple connected .NET projects. Changes in one project ripple through others via shared interfaces, NuGet packages, and service contracts. Today, an AI agent trying to understand the impact of a change has to:

1. Grep for the symbol name (finds string matches, not semantic references)
2. Hope the vector index returns relevant chunks (misses structural relationships)
3. Manually be told which files to look at

An IDE developer would instead: right-click → Find All References → peek at the call hierarchy → check implementations. We need AI agents to have that same capability.

### Key requirements

1. **Compiler-grade accuracy** — for C# specifically, we need Roslyn-level understanding. Tree-sitter (AST parsing) can't resolve overloads, generics, extension methods, implicit usings, or DI-resolved implementations.
2. **Cross-project awareness** — must work across all projects within a solution, ideally across repos.
3. **Agent-friendly interface** — tools should accept symbol names, not file:line:column positions. MCP is the natural protocol.
4. **Works with our AI tools** — Claude Code, OpenCode, GitHub Copilot. Not locked to one vendor's AI client.
5. **Open source preferred** — MIT/Apache licensed, no proprietary lock-in.
6. **Older .NET compatibility** — must run on .NET 8 or earlier (we're not on .NET 10).

### The accuracy problem with tree-sitter

Several tools in this space use tree-sitter for broad language coverage. For C# specifically, tree-sitter provides syntactic parsing only — it **cannot**:

- Resolve method overloads (which `ProcessMatch()` is this calling?)
- Infer generic type arguments (`List<T>` vs `List<MatchResult>`)
- Follow extension methods (no type system to resolve the `this` parameter)
- Understand implicit usings or global usings
- Resolve DI container registrations to concrete implementations
- Follow cross-assembly references

For architectural overview this is acceptable. For precise "what breaks if I change this?" analysis, only Roslyn (the actual C# compiler) provides reliable answers.

### Stateless vs stateful retrieval

Another gap n2-arachne highlighted: most RAG pipelines treat every query independently. There's no memory of what was recently relevant. A tiered approach — warm cache of recently relevant files, persistent project structure, dynamically computed search results — reduces redundant retrieval and provides better context continuity across an agent session.

---

## Approaches

There are four distinct approaches to solving this, each with different tradeoffs.

### 1. LSP (Language Server Protocol)

AI agent sends requests to a running language server for real-time code intelligence.

**C# language servers:**

| Server | Status | Notes |
|--------|--------|-------|
| Roslyn Language Server | Active | Bundled with C# Dev Kit. The modern choice. |
| OmniSharp | Maintenance mode | Legacy — do not invest. |
| csharp-ls | Active (868 stars) | Lighter alternative, MIT |

**What LSP can and can't do for C#:**

| Capability | LSP Method | C# Server Support |
|------------|-----------|-------------------|
| Go to definition | `textDocument/definition` | Yes |
| Find all references | `textDocument/references` | Yes |
| Find implementations | `textDocument/implementation` | Yes |
| Call hierarchy | `callHierarchy/*` | **Not implemented** (OmniSharp #2612) |
| Inheritance tree | `typeHierarchy/*` | **Not implemented** |
| Dependency graphs | No LSP method exists | N/A |
| Blast radius | No LSP method exists | N/A |

**Agent integration:** Claude Code and OpenCode both support LSP plugins and have the protocol plumbing for call hierarchy. The blocker is the C# language servers, not the AI tools.

**Verdict:** Useful for definitions, references, and implementations. Dead end for call hierarchy, inheritance, dependencies, and blast radius — the protocol either doesn't support it or the C# servers don't implement it.

**Links:**
- [LSAP](https://github.com/lsp-client/LSAP) — wraps LSP into agent-friendly tools (symbol names instead of file:line:column)
- [Piebald-AI/claude-code-lsps](https://github.com/Piebald-AI/claude-code-lsps) — LSP marketplace for Claude Code
- [Claude Code C# LSP setup](https://medium.com/@tomas.tilllmann/getting-c-lsp-working-in-claude-code-3076a3b2eb11)

---

### 2. Roslyn MCP Servers

Purpose-built MCP servers that load a `.sln` via Roslyn and expose semantic analysis as agent tools.

| Server | License | .NET Req | Stars | Tools | Capability Coverage |
|--------|---------|----------|-------|-------|-------------------|
| [Glider MCP](https://glidermcp.com/) | **Proprietary** | .NET 10 | 11 | 35 | All 5 capabilities |
| [SharpToolsMCP](https://github.com/kooshi/SharpToolsMCP) | MIT | .NET 8 | 170 | 20 | Implementations only (call hierarchy + inheritance exist in code but disabled) |
| [roslyn-codelens-mcp](https://github.com/MarcelRoozekrans/roslyn-codelens-mcp) | MIT | .NET 10 | 0 | 30 | All 5 + DI analysis, data flow |
| [RoslynMCP](https://github.com/carquiza/RoslynMCP) | MIT | .NET 8 | 37 | 5 | Partial dependencies only |
| [roslyn-mcp](https://github.com/egorpavlikhin/roslyn-mcp) | Unspecified | — | 28 | 2 | Minimal |
| [RoslynMcpExtension](https://github.com/sailro/RoslynMcpExtension) | MIT | VS 2022+ | 18 | 6 | VS-only (VSIX) |

**Note:** Roslyn can analyze code targeting any .NET version (Framework 4.x through .NET 8+) regardless of what SDK the MCP server itself runs on.

**Verdict:** The most direct path to all 5 capabilities. Glider MCP is the most complete but proprietary + .NET 10. The MIT-licensed alternatives either lack features or require .NET 10. This space is young and moving fast.

---

### 3. Sourcegraph Stack (SCIP + Code Search + Code Navigation)

SCIP indexers produce compiler-accurate symbol graphs. The Sourcegraph server stitches them into a cross-repo code graph. You don't have to use their AI client (Cody/Amp).

```
┌─────────────────────────────────────────────┐
│         Cody / Amp (AI — optional)          │
├─────────────────────────────────────────────┤
│          Code Search (Comby syntax)          │  Cross-repo structural + text search
├─────────────────────────────────────────────┤
│    Code Navigation (BFG graph engine)        │  Cross-repo go-to-def, find-refs
├─────────────────────────────────────────────┤
│       SCIP Indexes (per language, per repo)  │  Compiler-accurate symbol data
├─────────────────────────────────────────────┤
│  Code Hosts (GitHub, Azure DevOps, GitLab)   │  Your repos
└─────────────────────────────────────────────┘
```

**Open source vs proprietary:**

| Component | License | Open? |
|-----------|---------|-------|
| SCIP protocol + all indexers (including scip-dotnet) | Apache 2.0 | Yes |
| Sourcegraph server (search, navigation, BFG graph) | Proprietary | **No** |
| Cody / Amp | Proprietary | No |

**What SCIP captures:** Every symbol occurrence with exact positions, definitions and references with roles (read, write, import), relationships (`is_implementation`, `is_type_definition`), enclosing ranges for call hierarchies, C#-specific symbol kinds.

**scip-dotnet:** Built on Roslyn, compiler-grade accuracy. Known issues: incomplete namespace emission (#85), NullRef crash on some patterns (#102). Low activity (~quarterly commits), 25 stars.

**Pricing:** $59/user/month for enterprise (includes Cody). Code Search standalone available — contact sales. Self-hosted: Docker Compose minimum 8 vCPU / 32 GB RAM.

**Azure DevOps:** First-class support. PAT with Code Read + Project/Team + User Profile scopes.

**Code Search vs alternatives:**

| Feature | grep/rg | GitHub Code Search | Sourcegraph |
|---------|---------|-------------------|-------------|
| Cross-repo | No | GitHub repos only | Any code host (GitHub, ADO, GitLab, Bitbucket, Perforce) |
| Structural search (AST-aware) | No | No | Yes (Comby syntax) |
| Precise go-to-definition | No | Python only | 8+ languages, cross-repo via SCIP |
| Cross-repo find-references | No | No | Yes, via SCIP symbol IDs |

**The "Normsky" architecture** (Norvig + Chomsky): Sourcegraph combines the compiler-accurate SCIP graph (symbolic/Chomsky) with dense embeddings + BM25 search (statistical/Norvig) to optimally fill LLM context. They matched Copilot's 30% acceptance rate using the open-source StarCoder model — purely through better context.

**Verdict:** The most complete solution for cross-repo code intelligence. The AI client is optional — you can use Code Search + SCIP navigation with your own AI tools. The cost is the server license and infrastructure.

**Links:**
- [SCIP protocol](https://github.com/sourcegraph/scip)
- [scip-dotnet](https://github.com/sourcegraph/scip-dotnet)
- [Sourcegraph Azure DevOps docs](https://sourcegraph.com/docs/admin/code_hosts/azuredevops)
- [Sourcegraph self-hosted](https://sourcegraph.com/docs/self-hosted)
- [Normsky architecture — Latent Space](https://www.latent.space/p/sourcegraph)

---

### 4. Code Knowledge Graph Tools

Parse codebase into a graph database, let agents query relationships via MCP.

| Project | Backend | C# Support | License | Stars |
|---------|---------|-----------|---------|-------|
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | LadybugDB | Tree-sitter (heuristic) | **PolyForm Noncommercial** | 19k |
| [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) | KuzuDB / Neo4j / FalkorDB | Tree-sitter | MIT | 2.6k |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Embedded graph | Tree-sitter | MIT | 883 |

**GitNexus:** 7 MCP tools — query, 360-degree symbol view, impact analysis, change detection, rename, Cypher queries. Most capable graph tool but noncommercial license and tree-sitter accuracy limitations.

**CodeGraphContext:** MIT, 14 languages, easy setup (`pip install codegraphcontext && cgc mcp setup`). Call graphs, class hierarchies, call chain tracing.

**codebase-memory-mcp:** Zero-dependency single binary. Call path tracing (BFS depth 1-5), architectural mapping, git diff impact analysis. 64 languages.

**Verdict:** Good for architectural overview and broad multi-language support. Not reliable for precise C# analysis due to tree-sitter limitations (see accuracy section above). Best used as a complement to a Roslyn-based tool.

---

### 5. NDepend MCP Server

- **Repo:** https://github.com/ndepend/NDepend.MCP.Server
- **License:** MIT (server), **requires paid NDepend license** (~$500-2000)
- 14 tools including dependency graphs (SVG), CQLinq queries, complexity metrics
- CQLinq can answer arbitrary structural questions — the most powerful query language for .NET code analysis
- 15+ year track record as the gold standard for .NET dependency analysis

---

## Capability Coverage Summary

| Capability | LSP | Roslyn MCP (Glider) | Sourcegraph | Tree-sitter Graph | NDepend |
|------------|-----|---------------------|-------------|--------------------|---------|
| Call hierarchy | Protocol yes, C# servers no | Yes | Reconstructable from SCIP | Heuristic | Yes |
| Dependency graphs | No LSP method | Yes (type-level) | Cross-repo via BFG | Heuristic | Yes (SVG) |
| Blast radius | No LSP method | Yes | Via Code Insights | Partial | Yes |
| Inheritance trees | Protocol yes, C# servers no | Yes | Yes (SCIP relationships) | Heuristic | Yes |
| Find implementations | Yes (works today) | Yes | Yes (cross-repo) | Heuristic | Yes |

---

## Decision Matrix

| If you need... | Best option |
|----------------|------------|
| All 5 capabilities, single solution | Roslyn MCP server (Glider or roslyn-codelens-mcp) |
| Cross-repo code intelligence | Sourcegraph (Code Search + SCIP, skip their AI) |
| Free architectural overview | CodeGraphContext or codebase-memory-mcp |
| Deep .NET dependency analysis | NDepend MCP Server |
| Real-time diagnostics after edits | LSP (Roslyn Language Server) |
| Best overall (budget available) | Sourcegraph for cross-repo + Roslyn MCP for deep single-solution |

---

## Emerging Standards

| Standard | Status | Purpose |
|----------|--------|---------|
| SCIP | Active, Sourcegraph-backed | Cross-language code intelligence indexing |
| LSIF | Deprecated | Predecessor to SCIP |
| LSP | Mature | Real-time IDE code intelligence |
| LSAP | New (2025) | Wraps LSP for agent-friendly consumption |
| ACP | Emerging (Zed, Kiro) | Universal agent-to-editor protocol |
| MCP | Widely adopted | General AI tool protocol |

---

## Open Questions

- Can we get Sourcegraph Code Search standalone (without Cody) at a reasonable price point?
- Will the Roslyn MCP space mature around a single MIT-licensed tool that covers all 5 capabilities on .NET 8?
- Could we combine Sourcegraph (cross-repo graph) with a Roslyn MCP server (deep single-solution analysis)?
- Is there a path to getting call hierarchy implemented in the Roslyn Language Server for LSP clients?

---

## References

- [Sourcegraph SCIP Protocol](https://github.com/sourcegraph/scip)
- [scip-dotnet](https://github.com/sourcegraph/scip-dotnet)
- [LSAP — Language Server Agent Protocol](https://github.com/lsp-client/LSAP)
- [Glider MCP](https://glidermcp.com/)
- [SharpToolsMCP](https://github.com/kooshi/SharpToolsMCP)
- [roslyn-codelens-mcp](https://github.com/MarcelRoozekrans/roslyn-codelens-mcp)
- [NDepend MCP Server](https://github.com/ndepend/NDepend.MCP.Server)
- [GitNexus](https://github.com/abhigyanpatwari/GitNexus)
- [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext)
- [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)
- [n2-arachne](https://github.com/choihyunsus/n2-arachne) — initial inspiration
- [Sourcegraph Azure DevOps Integration](https://sourcegraph.com/docs/admin/code_hosts/azuredevops)
- [Sourcegraph Self-Hosted Deployment](https://sourcegraph.com/docs/self-hosted)
- [Normsky Architecture — Latent Space Podcast](https://www.latent.space/p/sourcegraph)
- [Claude Code C# LSP Setup](https://medium.com/@tomas.tilllmann/getting-c-lsp-working-in-claude-code-3076a3b2eb11)
- [OmniSharp Call Hierarchy Issue #2612](https://github.com/OmniSharp/omnisharp-roslyn/issues/2612)
