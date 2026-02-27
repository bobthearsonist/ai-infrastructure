#!/usr/bin/env python3
"""Index Obsidian vault into Qdrant collections (work/personal)."""

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# --- Configuration ---

VAULT_PATH = Path.home() / "SynologyDrive" / "Test"
QDRANT_URL = "http://localhost:6333"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384
VECTOR_NAME = "fast-all-minilm-l6-v2"  # Must match mcp-server-qdrant's naming
MAX_CHUNK_CHARS = 800
STATE_FILE = Path(__file__).parent / ".index_state.json"

# Folders that route to the "work" collection. Everything else goes to "personal".
WORK_PREFIXES = ["0 Profisee"]

# Folders/patterns to skip entirely.
SKIP_DIRS = {
    ".obsidian",
    ".trash",
    ".history",
    "attachments",
    "copilot-conversations",
    "copilot-custom-prompts",
    "Templates",
}


def should_skip(rel_path: Path) -> bool:
    """Return True if the file should be excluded from indexing."""
    parts = rel_path.parts
    return any(part in SKIP_DIRS for part in parts)


def route_collection(rel_path: Path) -> str:
    """Determine which collection a file belongs to based on its path."""
    top_folder = rel_path.parts[0] if rel_path.parts else ""
    for prefix in WORK_PREFIXES:
        if top_folder == prefix:
            return "work"
    return "personal"


def file_hash(path: Path) -> str:
    """Return MD5 hex digest of file contents."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def extract_title(content: str, filename: str) -> str:
    """Extract title from first H1 heading or fall back to filename."""
    m = re.match(r"^#\s+(.+)", content)
    if m:
        return m.group(1).strip()
    return filename.replace(".md", "")


def chunk_markdown(content: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split markdown into chunks, preferring header boundaries."""
    # Split on H1/H2/H3 headers
    sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue


        if len(section) <= max_chars:
            chunks.append(section)
        else:
            # Split long sections on double newlines (paragraphs)
            paragraphs = re.split(r"\n\n+", section)
            current = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if current and len(current) + len(para) + 2 > max_chars:
                    chunks.append(current)
                    current = para
                else:
                    current = f"{current}\n\n{para}" if current else para
            if current:
                chunks.append(current)

    return [c for c in chunks if len(c.strip()) > 30]


def load_state() -> dict:
    """Load previous indexing state (file hashes)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    """Persist indexing state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def make_point_id(file_path: str, chunk_index: int) -> str:
    """Generate a deterministic UUID for a chunk."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{file_path}::{chunk_index}"))


def ensure_collection(client: QdrantClient, name: str):
    """Create collection if it doesn't exist, using named vectors."""
    collections = [c.name for c in client.get_collections().collections]
    if name not in collections:
        client.create_collection(
            collection_name=name,
            vectors_config={
                VECTOR_NAME: VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            },
        )
        print(f"  Created collection: {name}")


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if not VAULT_PATH.exists():
        print(f"Vault not found at {VAULT_PATH}")
        sys.exit(1)

    print(f"Vault: {VAULT_PATH}")
    print(f"Qdrant: {QDRANT_URL}")
    print(f"Model: {EMBEDDING_MODEL}")
    if force:
        print("Mode: FULL RE-INDEX (--force)")
    if dry_run:
        print("Mode: DRY RUN (no writes)")
    print()

    # Initialize
    client = QdrantClient(url=QDRANT_URL)
    embedder = TextEmbedding(model_name=EMBEDDING_MODEL)

    ensure_collection(client, "work")
    ensure_collection(client, "personal")

    prev_state = {} if force else load_state()
    new_state = {}
    stats = {"skipped": 0, "indexed": 0, "unchanged": 0, "errors": 0, "chunks": 0}

    # Collect all markdown files
    md_files = sorted(VAULT_PATH.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")

    # Track which files still exist (for cleanup)
    current_files = set()

    for md_file in md_files:
        rel = md_file.relative_to(VAULT_PATH)

        if should_skip(rel):
            stats["skipped"] += 1
            continue

        rel_str = str(rel)
        current_files.add(rel_str)
        collection = route_collection(rel)

        # Check if file changed
        h = file_hash(md_file)
        if rel_str in prev_state and prev_state[rel_str]["hash"] == h:
            new_state[rel_str] = prev_state[rel_str]
            stats["unchanged"] += 1
            continue

        # Read and chunk
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  ERROR reading {rel}: {e}")
            stats["errors"] += 1
            continue

        title = extract_title(content, md_file.name)
        chunks = chunk_markdown(content)

        if not chunks:
            stats["skipped"] += 1
            continue

        # Generate embeddings (passage_embed for indexing, matches MCP server behavior)
        texts = [f"{title}\n\n{chunk}" for chunk in chunks]
        try:
            vectors = list(embedder.passage_embed(texts))
        except Exception as e:
            print(f"  ERROR embedding {rel}: {e}")
            stats["errors"] += 1
            continue

        # Build points
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            point_id = make_point_id(rel_str, i)
            points.append(
                PointStruct(
                    id=point_id,
                    vector={VECTOR_NAME: vector.tolist()},
                    payload={
                        "document": chunk,
                        "metadata": {
                            "file_path": rel_str,
                            "title": title,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "collection": collection,
                            "folder": str(rel.parent),
                            "last_modified": datetime.fromtimestamp(
                                md_file.stat().st_mtime, tz=timezone.utc
                            ).isoformat(),
                        },
                    },
                )
            )

        if not dry_run:
            # Delete old points for this file first (chunk count may have changed)
            old_chunk_count = prev_state.get(rel_str, {}).get("chunks", 0)
            if old_chunk_count > 0:
                old_ids = [make_point_id(rel_str, i) for i in range(old_chunk_count)]
                old_collection = prev_state[rel_str].get("collection", collection)
                client.delete(
                    collection_name=old_collection, points_selector=old_ids
                )

            client.upsert(collection_name=collection, points=points)

        new_state[rel_str] = {
            "hash": h,
            "chunks": len(chunks),
            "collection": collection,
        }
        stats["indexed"] += 1
        stats["chunks"] += len(chunks)
        print(f"  [{collection}] {rel} ({len(chunks)} chunks)")

    # Clean up deleted files
    deleted = set(prev_state.keys()) - current_files
    for del_file in deleted:
        old = prev_state[del_file]
        old_ids = [make_point_id(del_file, i) for i in range(old.get("chunks", 0))]
        if old_ids and not dry_run:
            client.delete(
                collection_name=old.get("collection", "personal"),
                points_selector=old_ids,
            )
        print(f"  DELETED {del_file}")

    if not dry_run:
        save_state(new_state)

    # Summary
    print()
    print("--- Summary ---")
    print(f"Indexed:   {stats['indexed']} files ({stats['chunks']} chunks)")
    print(f"Unchanged: {stats['unchanged']} files")
    print(f"Skipped:   {stats['skipped']} files")
    print(f"Errors:    {stats['errors']} files")
    print(f"Deleted:   {len(deleted)} files")

    # Collection stats
    for name in ("work", "personal"):
        info = client.get_collection(name)
        print(f"Collection '{name}': {info.points_count} points")


if __name__ == "__main__":
    main()
