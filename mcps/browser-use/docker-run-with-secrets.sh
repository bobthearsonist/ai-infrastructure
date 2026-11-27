#!/bin/sh
# Wraps `docker run`, adding a read-only mount of this container's secrets
# directory. Usage: docker-run-with-secrets.sh <docker run args...>
#
# docker run resolves -v sources on the Docker host, not inside this
# container, so the host path is read from this container's own mount.
set -eu

SECRETS_MOUNT=${SECRETS_MOUNT:-/run/secrets/browser-use}

src=$(docker inspect \
  --format "{{range .Mounts}}{{if eq .Destination \"$SECRETS_MOUNT\"}}{{.Source}}{{end}}{{end}}" \
  "$(hostname)")

if [ -z "$src" ]; then
  echo "docker-run-with-secrets: no mount at $SECRETS_MOUNT" >&2
  exit 1
fi

exec docker run -v "$src:$SECRETS_MOUNT:ro" "$@"
