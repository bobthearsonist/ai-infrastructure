#!/bin/sh
# Loads KEY=VALUE lines from a mounted env file into the process environment,
# then execs the image's real entrypoint. Secrets loaded this way never appear
# in the container's Config.Env, so `docker inspect` and `docker compose
# config` do not show them; compose's env_file: would inline every value.
#
# Usage (compose):
#   entrypoint: ["/env-file-entrypoint.sh", "<image entrypoint>"]
#   command:    [<image cmd>]   # setting entrypoint clears the image CMD
#   environment: [ENV_SECRETS_FILE=/run/secrets/<name>.env]
#
# Parses the subset of compose env_file syntax these files use: blank lines,
# # comments, an optional "export " prefix, and one pair of surrounding single
# or double quotes. No variable expansion and no inline comments, so values
# are taken literally.
set -eu

file="${ENV_SECRETS_FILE:-}"
if [ -z "$file" ] || [ ! -r "$file" ]; then
  # Fail closed: starting without the secrets would mean an unauthenticated
  # gateway or MCPs that fail later with confusing errors.
  echo "env-file-entrypoint: ENV_SECRETS_FILE unset or unreadable" >&2
  exit 1
fi

while IFS= read -r line || [ -n "$line" ]; do
  line="${line%"$(printf '\r')"}"
  case "$line" in
    '' | '#'*) continue ;;
    'export '*) line="${line#export }" ;;
  esac
  key="${line%%=*}"
  [ "$key" = "$line" ] && continue
  case "$key" in
    '' | [0-9]* | *[!A-Za-z0-9_]*)
      echo "env-file-entrypoint: skipping invalid key in $file" >&2
      continue
      ;;
  esac
  value="${line#*=}"
  case "$value" in
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
    \'*\') value="${value#\'}"; value="${value%\'}" ;;
  esac
  export "$key=$value"
done < "$file"

unset ENV_SECRETS_FILE
exec "$@"
