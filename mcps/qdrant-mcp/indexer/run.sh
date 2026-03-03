#!/usr/bin/env bash
# Run indexers for Qdrant
# Usage: ./run.sh obsidian [args...]
#        ./run.sh repos [args...]

set -e

INDEXER="${1:?Usage: $0 <obsidian|repos> [args...]}"
shift

# Read paths from local config (yq needs Windows path conversion, before MSYS_NO_PATHCONV)
case "$INDEXER" in
    obsidian) export VAULT_PATH=$(yq '.obsidian.vault_path' ~/ai/local.yaml) ;;
    repos)    export REPOS_BASE=$(yq '.repos.base_path' ~/ai/local.yaml) ;;
    *)        echo "Unknown indexer: $INDEXER (use 'obsidian' or 'repos')"; exit 1 ;;
esac

# Disable MSYS path mangling for docker (must be AFTER yq calls)
export MSYS_NO_PATHCONV=1

SERVICE="${INDEXER/#obsidian/obsidian-indexer}"
SERVICE="${SERVICE/#repos/repo-indexer}"

# Build the full command - docker compose run replaces the default command
# when args are given, so we must always include the script name
case "$INDEXER" in
    obsidian) CMD=(python index_obsidian.py --config /app/indexer.yaml) ;;
    repos)    CMD=(python3 index_repos.py --config /app/repos.yaml) ;;
esac

# Run from parent dir where the main docker-compose.yml lives
docker compose -f ../docker-compose.yml --profile "$INDEXER" run --rm "$SERVICE" "${CMD[@]}" "$@"
