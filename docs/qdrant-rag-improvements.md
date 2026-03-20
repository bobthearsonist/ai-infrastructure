# Qdrant RAG & Obsidian CLI Improvement Plan

> **Document Type**: Planning & Roadmap  
> **Created**: 2026-03-05  
> **Status**: Draft  
> **Owner**: AI Infrastructure Team

This document outlines planned improvements to the Qdrant RAG indexing system and Obsidian CLI tooling. Each improvement is prioritized based on user impact and implementation complexity.

---

## Current State

The existing infrastructure provides semantic search capabilities across multiple knowledge domains:

### Components

| Component | Description |
|-----------|-------------|
| **Obsidian CLI** | Command-line tool for managing Obsidian vault operations |
| **Qdrant Vector DB** | Self-hosted vector database running in Docker |
| **MCP Integration** | Model Context Protocol servers exposing search to AI agents |

### Collections

| Collection | Content | MCP Tool |
|------------|---------|----------|
| `code` | Indexed Git repository source code | `qdrant-code_qdrant-find` |
| `work` | Obsidian Profisee work notes | `qdrant-work_qdrant-find` |
| `personal` | Personal Obsidian vault content | `qdrant-personal_qdrant-find` |

### Features

- **Incremental indexing** - Only new/modified files are re-indexed
- **Chunk-based storage** - Documents split into semantic chunks with overlap
- **Embedding generation** - Text converted to vectors via embedding model
- **Metadata preservation** - File paths, timestamps, and source info retained

---

## Improvement 1: Automated Index Freshness

| Attribute | Value |
|-----------|-------|
| **Priority** | High |
| **Effort** | Low |
| **Status** | Not Started |

### Problem

Indexes become stale when files are modified but not re-indexed. Users must manually remember to run indexing commands, leading to outdated search results and missed context.

### Proposed Solutions

- [ ] **Task Scheduler Integration**
  - Create Windows Task Scheduler job for nightly full reindex
  - Configure incremental index runs every 4 hours during work hours
  - Add logging to track index operations and failures

- [ ] **Git Hook Automation**
  - Implement `post-commit` hook to trigger incremental index of changed files
  - Add `post-merge` hook for branch switches and pulls
  - Create `post-checkout` hook for worktree changes

- [ ] **Stale Index Warnings**
  - Track last index timestamp per collection
  - Emit warning in MCP server startup if index older than 24 hours
  - Add `--check-freshness` flag to CLI for manual verification

### Acceptance Criteria

- [ ] Indexes are automatically updated within 4 hours of file changes during work hours
- [ ] Git operations trigger relevant incremental indexing
- [ ] Users receive clear warnings when searching stale indexes
- [ ] No manual intervention required for routine index maintenance

---

## Improvement 2: Obsidian Metadata Extraction

| Attribute | Value |
|-----------|-------|
| **Priority** | High |
| **Effort** | Medium |
| **Status** | Not Started |

### Problem

Current indexing treats Obsidian notes as plain markdown, ignoring rich metadata that could dramatically improve search relevance. Tags, wikilinks, and frontmatter properties are not searchable or filterable.

### Proposed Solutions

- [ ] **Tag Extraction and Indexing**
  - Parse inline tags (`#tag`) and nested tags (`#parent/child`)
  - Store tags as filterable payload field in Qdrant
  - Enable tag-based filtering in search queries
  - Index tag co-occurrence for related content discovery

- [ ] **Wikilink Graph Building**
  - Extract `[[wikilinks]]` and `[[link|aliases]]` from content
  - Build adjacency list of note connections
  - Store backlink counts as relevance signal
  - Enable "find related notes" via link traversal

- [ ] **Frontmatter Property Parsing**
  - Parse YAML frontmatter from note headers
  - Index common properties: `date`, `type`, `project`, `status`
  - Support custom property schemas per vault
  - Enable property-based filtering in queries

### Acceptance Criteria

- [ ] Tags are extractable and filterable in search queries
- [ ] Wikilink relationships are queryable (forward and backlinks)
- [ ] Frontmatter properties appear in search result metadata
- [ ] Search can filter by any indexed metadata field

---

## Improvement 3: Hybrid Search with Sparse+Dense Vectors

| Attribute | Value |
|-----------|-------|
| **Priority** | Medium |
| **Effort** | Medium |
| **Status** | Not Started |

### Problem

Pure semantic search sometimes misses exact keyword matches that users expect. Technical terms, function names, and specific identifiers may not have strong semantic similarity but are critical for code search accuracy.

### Proposed Solutions

- [ ] **BM25 Sparse Vector Generation**
  - Implement BM25 tokenization and term frequency calculation
  - Generate sparse vectors alongside dense embeddings
  - Store both vector types in Qdrant named vectors

- [ ] **Hybrid Query Execution**
  - Configure Qdrant to search both sparse and dense vectors
  - Implement Reciprocal Rank Fusion (RRF) for result merging
  - Tune alpha parameter for sparse/dense balance per collection

- [ ] **Query Analysis and Routing**
  - Detect query type (keyword-heavy vs semantic)
  - Adjust sparse/dense weights based on query characteristics
  - Add query expansion for acronyms and abbreviations

### Acceptance Criteria

- [ ] Exact keyword matches rank highly even without semantic similarity
- [ ] Technical identifiers (function names, variables) are findable
- [ ] Semantic queries still return conceptually related results
- [ ] Search latency remains under 200ms for typical queries

---

## Improvement 4: Cross-Collection Search

| Attribute | Value |
|-----------|-------|
| **Priority** | Medium |
| **Effort** | Low |
| **Status** | Not Started |

### Problem

Users must know which collection contains relevant information and query them separately. Context that spans code and documentation requires multiple searches and manual correlation.

### Proposed Solutions

- [ ] **Unified MCP Server**
  - Create `qdrant-all_qdrant-find` tool searching all collections
  - Return results with collection source clearly labeled
  - Maintain individual collection servers for targeted searches

- [ ] **Cross-Collection Ranking**
  - Normalize scores across collections with different content types
  - Apply collection-specific boost factors based on query context
  - Deduplicate results that appear in multiple collections

- [ ] **Smart Collection Routing**
  - Analyze query intent to suggest primary collection
  - Show collection distribution in result summary
  - Allow collection filtering in unified search

### Acceptance Criteria

- [ ] Single query can find relevant results across all indexed content
- [ ] Results clearly indicate source collection
- [ ] Cross-collection search latency is acceptable (< 500ms)
- [ ] Individual collection searches remain available for precision

---

## Improvement 5: Parent Context Retrieval

| Attribute | Value |
|-----------|-------|
| **Priority** | Low |
| **Effort** | Medium |
| **Status** | Not Started |

### Problem

Retrieved chunks often lack surrounding context needed for full comprehension. A matched function signature may not include the docstring above it or the implementation below.

### Proposed Solutions

- [ ] **Adjacent Chunk Linking**
  - Store previous/next chunk IDs in payload metadata
  - Enable retrieval of N adjacent chunks on demand
  - Preserve chunk boundaries at logical break points

- [ ] **Parent Document Reference**
  - Store full document ID with each chunk
  - Enable "expand to full document" operation
  - Cache frequently accessed parent documents

- [ ] **Hierarchical Chunking**
  - Implement multi-level chunking (paragraph, section, document)
  - Store hierarchy relationships in payload
  - Allow retrieval at different granularity levels

### Acceptance Criteria

- [ ] Retrieved chunks include option to fetch surrounding context
- [ ] Context expansion does not require re-searching
- [ ] Logical document structure is preserved in chunk relationships
- [ ] Memory usage remains reasonable with additional metadata

---

## Future Considerations

The following improvements are not yet scheduled but may be valuable as the system matures:

| Improvement | Description | Complexity |
|-------------|-------------|------------|
| **Larger Embedding Models** | Upgrade from current model to larger/newer embeddings for improved accuracy | High |
| **File System Watching** | Real-time index updates via filesystem event monitoring | Medium |
| **Reranking Pipeline** | Add cross-encoder reranking stage for top-K results | Medium |
| **OCR for Images** | Extract and index text from screenshots and diagrams | High |
| **Canvas Support** | Index Obsidian canvas files with spatial relationships | Medium |
| **Relevance Feedback** | Learn from user clicks/selections to improve ranking | High |
| **Usage Analytics** | Track query patterns to identify gaps and optimize | Low |

---

## Implementation Order

Based on priority and dependency analysis, the recommended implementation sequence is:

```
Phase 1 (Immediate)
├── 1. Automated Index Freshness
│   └── Foundation for reliable search results
└── 2. Obsidian Metadata Extraction
    └── High-value improvement to search quality

Phase 2 (Near-term)
├── 3. Cross-Collection Search
│   └── Low effort, enables unified workflows
└── 4. Hybrid Search
    └── Addresses keyword search gaps

Phase 3 (Future)
└── 5. Parent Context Retrieval
    └── Polish improvement after core is solid
```

### Dependencies

- Metadata Extraction should precede Hybrid Search (tags can inform sparse vectors)
- Cross-Collection Search can proceed independently
- Parent Context Retrieval requires stable chunking strategy

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-03-05 | AI Infrastructure | Initial draft |
