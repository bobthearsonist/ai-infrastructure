# Qdrant Embedding Model Tuning Plan

> **Document Type**: Planning & Migration Runbook
> **Created**: 2026-06-16
> **Status**: Approved — not yet started · builds on the merged on-disk/durability work from session `0ff9a121`
> **Owner**: AI Infrastructure
> **Realizes**: "Larger Embedding Models" (Future Considerations) from [qdrant-rag-improvements.md](./qdrant-rag-improvements.md)

This document is the detailed execution plan for moving the Qdrant RAG indexes off a single, uniform embedding model onto **corpus-appropriate models** — a code-specialized model for source-code collections and a long-context prose model for Obsidian collections. It supersedes the one-line "Larger Embedding Models" entry in the roadmap with concrete model choices, a reversible migration pattern, code changes, an evaluation method, and a staged execution order.

---

## Motivation

Today every collection — code and prose alike — uses `sentence-transformers/all-MiniLM-L6-v2` (384d). One model, one dimension, one chunking philosophy, applied to two corpora with very different shapes. Three findings drive this plan:

### Finding 1 — The code index has a silent truncation defect

`all-MiniLM-L6-v2`'s maximum sequence length is **256 tokens**, enforced *silently* by sentence-transformers ([model card discussion](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/discussions/66)). The code indexer chunks at `max_chunk_chars: 1200` (~300–430 tokens) and prepends a `repo/path` context line. Every code chunk over ~256 tokens has its tail discarded by the model before embedding — large functions are effectively indexed on their opening lines only. This is a correctness gap, not merely a quality ceiling.

### Finding 2 — A purpose-built code model exists inside FastEmbed

`jinaai/jina-embeddings-v2-base-code` is in the [FastEmbed supported-models catalog](https://qdrant.github.io/fastembed/examples/Supported_Models/): 768d, **8192-token context** (via ALiBi), ~0.64 GB, trained on the `github-code` dataset plus 150M code-QA/docstring pairs, covering 30 programming languages including C#, TypeScript, and Python ([model card](https://huggingface.co/jinaai/jina-embeddings-v2-base-code)). Adopting it for the code collections both **eliminates the truncation** (8192 ≫ our chunk sizes) and adds code-aware semantics.

### Finding 3 — FastEmbed + vector-name coupling is the binding constraint

Both the index side and the query side embed through **FastEmbed** (`mcp-server-qdrant` only supports `EMBEDDING_PROVIDER=fastembed`). The Qdrant client derives the vector field name deterministically as `f"fast-{model_name.split('/')[-1].lower()}"` ([source](https://python-client.qdrant.tech/_modules/qdrant_client/qdrant_fastembed)). Consequences:

- Any model swap must update **three things in lockstep**: `EMBEDDING_MODEL` in `servers.json`, `VECTOR_NAME`/`VECTOR_SIZE` in the indexer, and the `vector_name`/`vector_size` in config. A mismatch makes queries target a non-existent vector field and return **nothing, silently**.
- Models **not** in the FastEmbed catalog are out of scope without replacing the query embedder. Notably, `Alibaba-NLP/gte-base-en-v1.5` is *not* in the catalog and is therefore excluded despite strong benchmarks.

---

## Foundation already in place (session `0ff9a121`, merged to `main`)

A prior session hardened this stack; those fixes are **merged** (commits `a857138` on-disk, `5cd6523` durable watchers, `8707a3f` mem caps) and this plan builds on them rather than re-litigating them:

- **`on_disk: true`** for vectors + HNSW is baked into both indexers' `ensure_collection` (`VectorParams(on_disk=True)`, `HnswConfigDiff(on_disk=True)`, `memmap_threshold=20000`). Result: qdrant holds 678k+ points at ~257 MiB RSS. The dimension increase to 768d therefore costs **disk**, not RAM.
- **`mem_limit` set on every service**: `qdrant` 3g, `qdrant-mcp` 2g (≈1 GB idle with 4×MiniLM), **repo-watchers already 4g** (sized for the cold full-embed), obsidian-watcher/`-watcher` 1–2g.
- **Durable, observable watcher**: `watcher.py` is a stat-poll loop honoring the indexer's `skip_dirs` (no more choking on 88 `.git` stores), reconcile-first, streaming indexer output to docker logs. Configs are mounted under their **real names** so `index_repos.py`'s config-stem→state-filename derivation lands on the bind-mounted state file (`.index_repos_state_work.json`), which now persists across recreates.
- **Known accepted tax**: the slow part of any cold build is the **Windows→WSL2 9p bind-mount walk + md5 hash** (~571s just to walk 110k files; ~79 min for a full 94-repo cold embed), *not* GPU embedding. This is Windows-host-only — do **not** redesign the data path around it; prefer progress logging. (See memories `qdrant-repo-watcher-durability…`, `qdrant-mcp-memory-on-disk…`, `wsl-bindmount-slow-is-windows-only`.)

## Current State (accurate as of 2026-06-16)

> Note: the "Current State" section of [qdrant-rag-improvements.md](./qdrant-rag-improvements.md) predates the 2026-06-09 collection split and still lists the old `code`/`work` names. The table below reflects the live four-collection layout.

| Collection | Content | Points | Model | Dim | Ctx limit | Chunk cap |
|---|---|---|---|---|---|---|
| `code-work` | 23 Profisee canonical repos | ~678k | all-MiniLM-L6-v2 | 384 | **256 tok** | 1200 chars |
| `code-public` | 9 personal/public repos | ~8.7k | all-MiniLM-L6-v2 | 384 | **256 tok** | 1200 chars |
| `notes-work` | Obsidian Profisee notes | ~2.8k | all-MiniLM-L6-v2 | 384 | **256 tok** | 800 chars |
| `personal` | Personal Obsidian (empty) | 0 | all-MiniLM-L6-v2 | 384 | **256 tok** | 800 chars |

Embedding stack: FastEmbed (`fastembed` CPU / `fastembed-gpu` GPU), ONNX Runtime. Code re-index is GPU-accelerated (`CUDAExecutionProvider`, batch 256); Obsidian and query-side run CPU. Vectors and the HNSW graph are `on_disk`. Code chunking is language-aware (splits on class/function boundaries); prose chunking splits on Markdown headers.

---

## Candidate Models (all FastEmbed-resident)

| Use | Model | Dim | Ctx | Size | Notes |
|---|---|---|---|---|---|
| **Code (chosen)** | `jinaai/jina-embeddings-v2-base-code` | 768 | 8192 | 0.64 GB | Purpose-built for code; fixes truncation; speaks the Profisee stack |
| **Prose (chosen)** | `nomic-ai/nomic-embed-text-v1.5` | 768 | 8192 | 0.52 GB | MTEB ~62.4; Matryoshka (truncatable to 512/256d later); needs `search_query:`/`search_document:` prefixes (FastEmbed applies) |
| Prose (alt) | `BAAI/bge-base-en-v1.5` | 768 | 512 | 0.21 GB | Symmetric, no prefix gotchas, smallest footprint |
| Prose (alt) | `mixedbread-ai/mxbai-embed-large-v1` | 1024 | 512 | 0.64 GB | Top MTEB but 1024d = most storage |

**Decisions (approved):** code → `jina-embeddings-v2-base-code`; prose → `nomic-embed-text-v1.5`.

---

## Target End-State

| Collection | Model | Vector field | Dim | Chunk cap |
|---|---|---|---|---|
| `code-work` | `jinaai/jina-embeddings-v2-base-code` | `fast-jina-embeddings-v2-base-code` | 768 | 2000 |
| `code-public` | `jinaai/jina-embeddings-v2-base-code` | `fast-jina-embeddings-v2-base-code` | 768 | 2000 |
| `notes-work` | `nomic-ai/nomic-embed-text-v1.5` | `fast-nomic-embed-text-v1.5` | 768 | 800 → 1000 (eval-tuned) |
| `personal` | `nomic-ai/nomic-embed-text-v1.5` | `fast-nomic-embed-text-v1.5` | 768 | 1000 |

---

## Migration Pattern (parallel collection + alias cutover)

Applied identically to each collection. Chosen over in-place drop/recreate because a 669k-point re-index cannot be undone, and this pattern keeps search live throughout and makes cutover/rollback atomic.

```
1. Build new physical collection   <name>__<model>   (old collection stays live & serving)
2. Index into it (--force)
3. Smoke test: embed a doc, query it back -> assert non-zero score   (catches prefix mismatch)
4. A/B eval: recall@5 + MRR, old vs new, on the curated query set
5. Cutover: point alias <name> -> <name>__<model>   (atomic)   OR flip servers.json COLLECTION_NAME
6. Restart qdrant-mcp; verify from a client
7. After sign-off -> drop the old MiniLM collection; reclaim disk
```

**Why aliases:** Qdrant collection aliases let `servers.json` keep pointing at a stable name while the physical collection underneath changes. Cutover and rollback become single atomic alias swaps — no broken-search window, no per-iteration `servers.json` churn, and a one-call revert if the new index underperforms. Cost: the indexer writes to a physical name (e.g. `code-work__jina`) rather than the alias.

**Critical: the state file is model-blind.** `index_repos.py`/`index_obsidian.py` key their state on file hash + chunk count, **not** the embedding model. Changing the model in an existing config and letting the watcher run incrementally will mark every file "unchanged" and **skip it** → the new collection comes up empty. The migration must trigger a full re-embed. Two safe ways, both used here:

- **New config file per migration** (preferred): `repos-work-jina.yaml` has a different *stem*, so the indexer derives a *fresh, empty* state file (`.index_repos_state_work-jina.json`) and naturally does a full build into the new collection — while the existing watcher keeps serving the old collection from its own untouched state. The config-stem→state-filename design (the same one behind the earlier ephemeral-state bug) is what makes this clean.
- **`--force`** on a one-shot `repo-indexer` run as belt-and-suspenders, since the one-shot shares the generic `.index_repos_state.json`.

---

## Code Changes Required

| # | File | Change |
|---|---|---|
| 1 | `mcps/qdrant-mcp/indexer/index_repos.py` (lines ~50–52) | Lift hardcoded `EMBEDDING_MODEL`/`VECTOR_SIZE`/`VECTOR_NAME` into the YAML `embedding:` block (parity with `index_obsidian.py`); default to MiniLM values for back-compat |
| 2 | `mcps/qdrant-mcp/indexer/repos-work.yaml`, `repos-public.yaml` | Add `embedding:` block (jina / 768 / `fast-jina-embeddings-v2-base-code`); bump `max_chunk_chars: 1200 → 2000` |
| 3 | `mcps/qdrant-mcp/indexer/indexer.yaml` | Swap `embedding:` block to nomic / 768 / `fast-nomic-embed-text-v1.5` |
| 4 | `mcps/qdrant-mcp/servers.json` | Update `EMBEDDING_MODEL` per server to match its collection's model |
| 5 | `mcps/qdrant-mcp/docker-compose.yml` | `qdrant-mcp` `mem_limit: 2g → 4g` (4 servers loading 768d models — jina/nomic ONNX are ~2–3× MiniLM's resident footprint; measure post-cutover). **Repo-watchers are already 4g.** Watch `qdrant` (3g) during the code-work cold build for optimizer segment-rewrite spikes on the bigger vectors |
| 5b | `mcps/qdrant-mcp/indexer/repos-work-jina.yaml`, `repos-public-jina.yaml`, watcher configs | New per-migration config files (distinct stems → fresh state) pointing `qdrant_collection` at the `__jina` physical names; or run the one-shot `repo-indexer` with `--force` |
| 6 | `mcps/qdrant-mcp/indexer/eval/` (new) | `queries.yaml` + `eval_retrieval.py` — see Evaluation |

---

## Evaluation Harness

A small, reusable A/B harness produces real before/after evidence rather than eyeballed relevance.

- **`eval/queries.yaml`** — per collection, a list of `{ query, expected_path_substrings }`. Ground truth is **user-curated** (5–10 realistic queries per corpus) — the people who run the searches know what "correct" looks like.
- **`eval/eval_retrieval.py`** — for a given collection + model, embeds each query via FastEmbed `query_embed`, runs Qdrant top-k search, and computes **recall@5** and **MRR** by matching expected path substrings against result metadata. Prints an old-vs-new comparison table.
- **Gate 0 — prefix-consistency smoke test (runs first):** embed a known document, query for it, assert non-zero similarity. This catches the silent failure mode where index-side and query-side disagree on the `search_document:`/`search_query:` prefix convention (relevant for both nomic and jina). No A/B numbers are trusted until this passes.

---

## Execution Order (one collection at a time)

Staged smallest-to-largest so migration mechanics are proven before the heavy re-index, and so the multi-model RAM load never lands all at once on a half-migrated stack.

```
Groundwork (shared, do once)
├── Bump qdrant-mcp mem_limit (RAM headroom for multi-model)
├── Make index_repos.py embedding config-driven
└── Build eval harness + curate query set

Iteration 0: personal      (empty)   -> config only, no compute       [warm-up]
Iteration 1: notes-work    (~2.8k)   -> nomic; proves prefixes+alias  [lowest stakes]
Iteration 2: code-public   (~8.7k)   -> jina;  proves code model
Iteration 3: code-work     (~669k)   -> jina;  the heavy GPU re-index [last]
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Silent prefix mismatch** (nomic/jina are asymmetric; wrong prefix convention degrades retrieval with no error) | Gate 0 smoke test before trusting any eval; verify from a real client after each cutover |
| **Model-blind state file** → incremental run skips all files, new collection comes up empty | Migrate via a new config file (distinct stem = fresh state) or `--force`; never just edit the model in an existing watcher config |
| **RAM ceiling on the query side** (`qdrant-mcp` 2g runs 4 servers; 768d ONNX models are ~2–3× MiniLM resident) | Bump `qdrant-mcp` to 4g and measure actual RSS after jina/nomic load; repo-watchers already 4g; on_disk keeps the DB tiny |
| **Irreversible re-index** of ~678k points | Parallel-collection + alias cutover keeps old index intact until sign-off; rollback = one alias swap |
| **Disk growth** (384→768d roughly doubles vector storage; code-work ≈ 2 GB raw) | `on_disk` vectors (disk, not RAM, already live); drop old collections post-cutover to reclaim |
| **Long cold-build wall-clock** for code-work (~75–90 min) | Bottleneck is the WSL2 9p bind-mount walk+hash, **not** GPU embedding — an accepted Windows-only tax; run as the final isolated step, lean on the watcher's progress logging, don't redesign the data path |

---

## Cost Notes

- Re-index is **mandatory and full** per collection: changing model/dim changes the vector field name, so existing 384d vectors are unusable for the new field. Force it via a fresh-stem config or `--force` (the state file won't trigger it on its own — see Migration Pattern).
- Wall-clock is dominated by the **WSL2 bind-mount walk + md5 hash**, not GPU embedding (~571s just to crawl 110k files; ~75–90 min for a full code-work cold build). Windows-host-only tax.
- First run downloads the jina (~0.64 GB) and nomic (~0.52 GB) models into the `fastembed-cache` volume (one-time, shared across CPU + GPU services).
- `fastembed-gpu` supports the same model catalog as CPU FastEmbed, so the GPU code path covers jina.

---

## Open Decisions — Resolved

| Decision | Choice |
|---|---|
| Scope | Plan all four collections; execute one at a time to protect the machine |
| Code model | `jinaai/jina-embeddings-v2-base-code` |
| Prose model | `nomic-ai/nomic-embed-text-v1.5` |
| Evaluation | Build a small A/B harness (recall@5 / MRR) with a curated query set |

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-06-16 | AI Infrastructure | Initial plan — executes the "Larger Embedding Models" roadmap item with per-corpus models, alias-based migration, eval harness, and staged rollout |
| 2026-06-16 | AI Infrastructure | Reconciled with merged session `0ff9a121` work: added "Foundation already in place" (on_disk/mem_limits/durable watcher already live); corrected code-work to ~678k pts; flagged the model-blind state-file migration trap; reframed RAM risk to query-side only (repo-watchers already 4g); corrected re-index bottleneck to WSL2 bind-mount crawl, not GPU |
