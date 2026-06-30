# Qdrant Embedding Model Comparison — Results

> **Document Type**: Evaluation results
> **Date**: 2026-06-19
> **Companion to**: [qdrant-embedding-model-tuning-plan.md](./qdrant-embedding-model-tuning-plan.md) (the plan/approach)
> **Harness**: `mcps/qdrant-mcp/indexer/eval/eval_retrieval.py` + `eval/queries.yaml`

A/B comparison of embedding models per corpus, measured with a small retrieval
eval harness. Metrics: **recall@5** (fraction of queries where an expected file
appears in the top 5) and **MRR@5** (mean reciprocal rank of the first hit).
Queries are matched (case-insensitive) against result file paths + document text.

## Method

- **Harness** runs each query through the candidate model's FastEmbed
  `query_embed`, searches the target collection's named vector, scores recall@5
  / MRR@5 against expected path/symbol substrings.
- **Gate 0 (prefix sanity)** runs first: embed an indexed chunk as a query,
  confirm it self-retrieves. Catches silent query/passage prefix mismatches
  (nomic/jina are asymmetric).
- Queries are **derived from real usage**: the code set comes from grep history
  across 127 past sessions (how we actually search the code); the prose set from
  real note lookups.
- Comparison is **full-index vs full-index** (both collections fully built).

## Code (Profisee repos) — MiniLM vs jina

| model | collection | dim | points | recall@5 | MRR@5 |
|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | code-work | 384 | 688,842 | 0.833 | 0.736 |
| **jina-embeddings-v2-base-code** | code-work__jina | 768 | **188,390** | **0.917** | **0.833** |

**Verdict: adopt jina.** Higher recall and MRR at ~¼ the index size. jina wins
on the discriminating "answer lives deep in a large file" queries that MiniLM's
256-token truncation mangled:

| query | MiniLM | jina |
|---|---|---|
| certificate thumbprint validation | miss | **rank 1** |
| entity lock service for concurrent editing | rank 3 | **rank 1** |
| user account types (admin/regular/windows) | rank 2 | rank 2 |
| (9 of 12 queries) | rank 1 tie | rank 1 tie |

> Gate 0 reads "RED" for code on both models — a **false alarm**: code is full of
> near-duplicate chunks, so embedding one chunk returns a *different but
> near-identical* chunk at rank 1 (jina self-score 0.90 is high). The strong
> real-query ranks confirm prefixes are fine; the exact-self-id gate is just too
> strict for duplicate-heavy code. (Follow-up: relax the code gate to a score
> threshold.)

## Prose (Obsidian work notes) — MiniLM vs nomic

| model | collection | dim | points | recall@5 | MRR@5 |
|---|---|---|---|---|---|
| **all-MiniLM-L6-v2** | notes-work | 384 | 3,129 | **0.857** | **0.671** |
| nomic-embed-text-v1.5 | notes-work__nomic | 768 | 3,185 | 0.714 | 0.643 |

**Verdict: do NOT adopt nomic for prose.** No win — MiniLM slightly ahead on a
7-query set. Consistent with the thesis: notes chunk to ~200 tokens and were
never truncated by MiniLM, so nomic's long-context advantage has nothing to bite
on. (Caveat: small query set + brittle path-substring ground truth — enough to
say "no clear win," not "nomic is worse." Gate 0 PASSED for both prose models.)

## Why the gap differs by corpus

The headline finding: **the embedding upgrade pays off only where the old model
was actually losing information.** MiniLM silently truncates at 256 tokens —
which hurt *code* (large functions, dense files) but not *prose* (short note
chunks). So a code-specialized, long-context model is a clear win for code and a
wash for prose. The bigger structural lever turned out to be **chunking**
(token-bounded AST chunking, see the plan doc), which improved the code index
quality independent of the model swap.

## Decisions

| Corpus | Model | Adopted? |
|---|---|---|
| code-work | jina-embeddings-v2-base-code | ✅ live (2026-06-19) |
| code-public | jina-embeddings-v2-base-code | ✅ migrating (same rationale) |
| notes-work / personal | all-MiniLM-L6-v2 (unchanged) | nomic evaluated, deferred |

## Reproduce

```bash
# inside an indexer container (same FastEmbed version as the index side)
docker exec obsidian-watcher python /app/eval/eval_retrieval.py \
  --queries /app/eval/queries.yaml --k 5 --corpus code   # or --corpus notes
```
