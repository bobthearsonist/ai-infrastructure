#!/usr/bin/env python3
"""Index Obsidian vault into Qdrant collections (work/personal).

Usage:
    python index_obsidian.py --config path/to/indexer.yaml [--force] [--dry-run]

The --config argument is required. See indexer.yaml.example for template.
All configuration must be explicit - no defaults are applied.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Required top-level keys
REQUIRED_KEYS = [
    "qdrant_url",
    "collections",
    "routing",
    "skip_dirs",
    "skip_unrouted",
    "embedding",
]

# Required embedding keys
REQUIRED_EMBEDDING_KEYS = [
    "model",
    "vector_size",
    "vector_name",
    "max_chunk_chars",
]


def load_config(config_path: str | None) -> dict[str, Any]:
    """Load configuration from YAML file. All keys must be explicitly configured."""
    if config_path is None:
        print("Error: --config is required. See indexer.yaml.example for template.")
        sys.exit(1)

    config_file = Path(config_path)
    if not config_file.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Validate all required top-level keys
    missing = [k for k in REQUIRED_KEYS if k not in config]
    if missing:
        print(f"Error: Missing required config keys: {', '.join(missing)}")
        sys.exit(1)

    # Validate embedding section
    emb = config.get("embedding", {})
    missing_emb = [k for k in REQUIRED_EMBEDDING_KEYS if k not in emb]
    if missing_emb:
        print(f"Error: Missing required embedding keys: {', '.join(missing_emb)}")
        sys.exit(1)

    # If skip_unrouted is false, default_collection is required
    if not config["skip_unrouted"] and "default_collection" not in config:
        print("Error: 'default_collection' is required when 'skip_unrouted' is false")
        sys.exit(1)

    return config


def get_vault_path() -> Path:
    """Get vault path from VAULT_PATH env var.

    In Docker, vault is mounted at /vault regardless of env var value.
    Check for /vault first (Docker), then use VAULT_PATH env var.
    Error if neither is available.
    """
    vault_mount = Path("/vault")
    if vault_mount.is_dir() and any(vault_mount.iterdir()):
        return vault_mount

    vault_path = os.environ.get("VAULT_PATH")
    if not vault_path:
        print("Error: VAULT_PATH environment variable is required")
        print("Set it in ~/ai/local.yaml and run via run.sh, or set it directly")
        sys.exit(1)

    return Path(os.path.expandvars(os.path.expanduser(vault_path)))


class Indexer:
    """Obsidian vault indexer with configurable routing."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.vault_path = get_vault_path()
        self.qdrant_url = config["qdrant_url"]
        self.collections = config["collections"]
        self.routing = config["routing"]
        self.skip_dirs = set(config["skip_dirs"])
        self.skip_unrouted = config["skip_unrouted"]
        self.default_collection = config.get(
            "default_collection"
        )  # None if skip_unrouted=true

        emb = config["embedding"]
        self.embedding_model = emb["model"]
        self.vector_size = emb["vector_size"]
        self.vector_name = emb["vector_name"]
        self.max_chunk_chars = emb["max_chunk_chars"]

        self.state_file = Path(__file__).parent / ".index_state.json"

    def should_skip(self, rel_path: Path) -> bool:
        """Return True if the file should be excluded from indexing."""
        parts = rel_path.parts
        return any(part in self.skip_dirs for part in parts)

    def route_collection(self, rel_path: Path) -> str | None:
        """Determine which collection a file belongs to based on its path."""
        top_folder = rel_path.parts[0] if rel_path.parts else ""

        for collection, prefixes in self.routing.items():
            for prefix in prefixes:
                if top_folder == prefix:
                    return collection

        if self.skip_unrouted:
            return None
        return self.default_collection

    @staticmethod
    def file_hash(path: Path) -> str:
        """Return MD5 hex digest of file contents."""
        return hashlib.md5(path.read_bytes()).hexdigest()

    @staticmethod
    def extract_title(content: str, filename: str) -> str:
        """Extract title from first H1 heading or fall back to filename."""
        m = re.match(r"^#\s+(.+)", content)
        if m:
            return m.group(1).strip()
        return filename.replace(".md", "")

    def chunk_markdown(self, content: str) -> list[str]:
        """Split markdown into chunks, preferring header boundaries."""
        max_chars = self.max_chunk_chars
        sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
        chunks = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            if len(section) <= max_chars:
                chunks.append(section)
            else:
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

    def load_state(self) -> dict:
        """Load previous indexing state (file hashes)."""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}

    def save_state(self, state: dict):
        """Persist indexing state."""
        self.state_file.write_text(json.dumps(state, indent=2))

    @staticmethod
    def make_point_id(file_path: str, chunk_index: int) -> str:
        """Generate a deterministic UUID for a chunk."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{file_path}::{chunk_index}"))

    def ensure_collection(self, client: QdrantClient, name: str):
        """Create collection if it doesn't exist, using named vectors."""
        collections = [c.name for c in client.get_collections().collections]
        if name not in collections:
            client.create_collection(
                collection_name=name,
                vectors_config={
                    self.vector_name: VectorParams(
                        size=self.vector_size, distance=Distance.COSINE
                    ),
                },
            )
            print(f"  Created collection: {name}")

    def run(self, force: bool = False, dry_run: bool = False):
        """Run the indexing process."""
        if not self.vault_path.exists():
            print(f"Vault not found at {self.vault_path}")
            sys.exit(1)

        print(f"Vault: {self.vault_path}")
        print(f"Qdrant: {self.qdrant_url}")
        print(f"Collections: {', '.join(self.collections)}")
        print(f"Model: {self.embedding_model}")
        print(f"Skip unrouted: {self.skip_unrouted}")
        if force:
            print("Mode: FULL RE-INDEX (--force)")
        if dry_run:
            print("Mode: DRY RUN (no writes)")
        print()

        # Initialize
        client = QdrantClient(url=self.qdrant_url)
        embedder = TextEmbedding(model_name=self.embedding_model)

        for collection in self.collections:
            self.ensure_collection(client, collection)

        prev_state = {} if force else self.load_state()
        new_state = {}
        stats = {
            "skipped": 0,
            "indexed": 0,
            "unchanged": 0,
            "errors": 0,
            "chunks": 0,
            "unrouted": 0,
        }

        # Collect all markdown files
        md_files = sorted(self.vault_path.rglob("*.md"))
        print(f"Found {len(md_files)} markdown files")

        # Track which files still exist (for cleanup)
        current_files = set()

        for md_file in md_files:
            rel = md_file.relative_to(self.vault_path)

            if self.should_skip(rel):
                stats["skipped"] += 1
                continue

            rel_str = str(rel)
            collection = self.route_collection(rel)

            if collection is None:
                stats["unrouted"] += 1
                continue

            current_files.add(rel_str)

            # Check if file changed
            h = self.file_hash(md_file)
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

            title = self.extract_title(content, md_file.name)
            chunks = self.chunk_markdown(content)

            if not chunks:
                stats["skipped"] += 1
                continue

            # Generate embeddings
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
                point_id = self.make_point_id(rel_str, i)
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={self.vector_name: vector.tolist()},
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
                # Delete old points for this file first
                old_chunk_count = prev_state.get(rel_str, {}).get("chunks", 0)
                if old_chunk_count > 0:
                    old_ids = [
                        self.make_point_id(rel_str, i) for i in range(old_chunk_count)
                    ]
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
            old_collection = old.get("collection")
            if not old_collection:
                print(
                    f"  WARNING: No collection stored for {del_file}, skipping cleanup"
                )
                continue
            old_ids = [
                self.make_point_id(del_file, i) for i in range(old.get("chunks", 0))
            ]
            if old_ids and not dry_run:
                client.delete(
                    collection_name=old_collection,
                    points_selector=old_ids,
                )
            print(f"  DELETED {del_file}")

        if not dry_run:
            self.save_state(new_state)

        # Summary
        print()
        print("--- Summary ---")
        print(f"Indexed:   {stats['indexed']} files ({stats['chunks']} chunks)")
        print(f"Unchanged: {stats['unchanged']} files")
        print(f"Skipped:   {stats['skipped']} files")
        print(f"Unrouted:  {stats['unrouted']} files")
        print(f"Errors:    {stats['errors']} files")
        print(f"Deleted:   {len(deleted)} files")

        # Collection stats
        for name in self.collections:
            info = client.get_collection(name)
            print(f"Collection '{name}': {info.points_count} points")


def main():
    parser = argparse.ArgumentParser(description="Index Obsidian vault into Qdrant")
    parser.add_argument("--config", "-c", help="Path to indexer.yaml config file")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force full re-index"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Preview without writing"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    indexer = Indexer(config)
    indexer.run(force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
