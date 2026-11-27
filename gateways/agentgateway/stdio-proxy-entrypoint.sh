#!/bin/sh
# Export every file in /run/secrets as an environment variable named after the
# file, then hand off to mcp-proxy. Values reach the proxy process (and, via
# --pass-environment, its stdio children such as hass-mcp) without appearing in
# the container's Config.Env, so `docker inspect` and `docker compose config`
# show only the file mounts.
set -eu

if [ -d /run/secrets ]; then
  for f in /run/secrets/*; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    case "$name" in
      *[!A-Za-z0-9_]* | [0-9]*)
        echo "stdio-proxy-entrypoint: skipping $name (not a valid env var name)" >&2
        continue
        ;;
    esac
    # $(...) strips trailing newlines, so files written with or without one work.
    value=$(cat "$f")
    export "$name=$value"
  done
fi

exec mcp-proxy "$@"
