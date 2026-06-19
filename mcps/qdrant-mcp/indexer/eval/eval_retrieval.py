#!/usr/bin/env python3
"""A/B retrieval eval — compare embedding models on the same query set.

Run this INSIDE an indexer container (docker exec) so it uses the exact same
FastEmbed version and cached model files as the index side, and reaches Qdrant
over the docker network. Embedding-version drift between index and query is a
silent source of bad scores, so co-locating index + eval matters.

For each corpus the YAML names one or more TARGETS (a model + the collection it
populated). For each query we embed it with that target's model via FastEmbed
`query_embed`, search the target collection's NAMED vector, and score:

  recall@k : 1.0 if any expected substring matches a result in the top k
  MRR      : 1 / (rank of first matching result), else 0

Expected matches are substrings tested against each result's file_path / title /
repo metadata AND the document text (case-insensitive). A query lists one or
more acceptable substrings; ANY match counts as a hit.

GATE 0 (prefix sanity) runs first and must pass before any A/B numbers are
trusted: for each target we pull one of its own indexed chunks, embed that text
as a QUERY, and confirm the same chunk comes back at/near the top. nomic and
jina are asymmetric (search_query:/search_document: prefixes); if the index and
query sides disagree on the prefix convention, self-retrieval collapses and
this gate goes RED — catching a failure mode that otherwise returns plausible
garbage with no error.

Usage:
  python eval_retrieval.py --queries eval/queries.yaml [--k 5] [--corpus notes]
"""

import argparse
import os
import sys

import yaml
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client import models

_MODEL_CACHE: dict[str, TextEmbedding] = {}


def _embedder(model_name: str) -> TextEmbedding:
    emb = _MODEL_CACHE.get(model_name)
    if emb is None:
        print(f"    loading model {model_name} ...", flush=True)
        emb = TextEmbedding(model_name=model_name)
        _MODEL_CACHE[model_name] = emb
    return emb


def embed_query(model_name: str, text: str) -> list[float]:
    return list(_embedder(model_name).query_embed([text]))[0].tolist()


def embed_passage(model_name: str, text: str) -> list[float]:
    return list(_embedder(model_name).passage_embed([text]))[0].tolist()


def search(client: QdrantClient, collection: str, vector_name: str,
           vector: list[float], k: int):
    # query_points (search was removed in newer qdrant-client). `using` selects
    # the named vector; .points are ScoredPoints with id/score/payload.
    resp = client.query_points(
        collection_name=collection,
        query=vector,
        using=vector_name,
        limit=k,
        with_payload=True,
    )
    return resp.points


def result_haystack(point) -> str:
    payload = point.payload or {}
    md = payload.get("metadata", {}) or {}
    parts = [str(md.get(key, "")) for key in ("file_path", "title", "repo")]
    parts.append(str(payload.get("document", "")))
    return " ".join(parts).lower()


def first_hit_rank(results, expects: list[str]) -> int | None:
    """1-based rank of the first result matching ANY expected substring."""
    needles = [e.lower() for e in expects]
    for i, point in enumerate(results, start=1):
        hay = result_haystack(point)
        if any(n in hay for n in needles):
            return i
    return None


def gate0_self_retrieval(client: QdrantClient, target: dict, k: int = 3) -> bool:
    """Embed one indexed chunk as a query; confirm it returns at/near top."""
    collection = target["collection"]
    vname = target["vector_name"]
    model = target["model"]
    points, _ = client.scroll(
        collection_name=collection, limit=1,
        with_payload=True, with_vectors=False,
    )
    if not points:
        print(f"    [{target['label']}] GATE0 SKIP — collection empty")
        return False
    src = points[0]
    doc = (src.payload or {}).get("document", "")
    if not doc:
        print(f"    [{target['label']}] GATE0 SKIP — no document text")
        return False
    vec = embed_query(model, doc)
    hits = search(client, collection, vname, vec, k)
    top_id = hits[0].id if hits else None
    top_score = hits[0].score if hits else 0.0
    self_rank = next((i for i, h in enumerate(hits, 1) if h.id == src.id), None)
    ok = self_rank is not None and top_score >= 0.40
    flag = "PASS" if ok else "**RED**"
    print(f"    [{target['label']}] GATE0 {flag} — self-rank={self_rank} "
          f"top_score={top_score:.3f} (query/passage prefixes "
          f"{'consistent' if ok else 'SUSPECT'})")
    return ok


def run_corpus(client: QdrantClient, name: str, corpus: dict, k: int):
    targets = corpus["targets"]
    queries = corpus["queries"]
    print(f"\n=== Corpus: {name}  ({len(queries)} queries, k={k}) ===")

    print("  Gate 0 — prefix self-retrieval sanity:")
    gate_ok = {t["label"]: gate0_self_retrieval(client, t) for t in targets}

    # Aggregates
    agg = {t["label"]: {"recall": 0.0, "mrr": 0.0, "n": 0} for t in targets}
    # Per-query grid
    print("\n  Per-query first-hit rank (lower is better, '-' = miss in top k):")
    header = "    {:<52} ".format("query") + "  ".join(
        f"{t['label']:>8}" for t in targets)
    print(header)
    for query in queries:
        q = query["q"]
        expects = query["expect"]
        row = "    {:<52} ".format(q[:52])
        for t in targets:
            vec = embed_query(t["model"], q)
            hits = search(client, t["collection"], t["vector_name"], vec, k)
            rank = first_hit_rank(hits, expects)
            agg[t["label"]]["n"] += 1
            if rank is not None:
                agg[t["label"]]["recall"] += 1.0
                agg[t["label"]]["mrr"] += 1.0 / rank
            row += f"{(str(rank) if rank else '-'):>8}  "
        print(row)

    print(f"\n  Aggregate (recall@{k} / MRR@{k}):")
    print("    {:<10} {:>10} {:>10}".format("target", f"recall@{k}", f"MRR@{k}"))
    for t in targets:
        a = agg[t["label"]]
        n = max(a["n"], 1)
        gate = "" if gate_ok.get(t["label"]) else "  (GATE0 RED!)"
        print("    {:<10} {:>10.3f} {:>10.3f}{}".format(
            t["label"], a["recall"] / n, a["mrr"] / n, gate))


def main():
    ap = argparse.ArgumentParser(description="A/B retrieval eval across models")
    ap.add_argument("--queries", required=True, help="Path to queries.yaml")
    ap.add_argument("--k", type=int, default=5, help="top-k (default 5)")
    ap.add_argument("--corpus", help="Only run this corpus (default: all)")
    args = ap.parse_args()

    qdrant_url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    client = QdrantClient(url=qdrant_url)

    with open(args.queries) as f:
        spec = yaml.safe_load(f)

    corpora = spec["corpora"]
    if args.corpus:
        corpora = {args.corpus: corpora[args.corpus]}

    print(f"Qdrant: {qdrant_url}")
    existing = {c.name for c in client.get_collections().collections}
    for name, corpus in corpora.items():
        missing = [t["collection"] for t in corpus["targets"]
                   if t["collection"] not in existing]
        if missing:
            print(f"\n=== Corpus: {name} — SKIP, missing collections: {missing}")
            continue
        run_corpus(client, name, corpus, args.k)


if __name__ == "__main__":
    main()
