#!/bin/sh
# Load the API token from a file secret so it never appears in `docker inspect`
# or the compose environment, then hand over to mcp-proxy.
set -eu

secret=/run/secrets/paperless_api_key
if [ ! -s "$secret" ]; then
  echo "paperless-mcp: $secret is missing or empty" >&2
  exit 1
fi

PAPERLESS_API_KEY="$(tr -d '\r\n' < "$secret")"
export PAPERLESS_API_KEY

# --pass-environment forwards the key to the single child defined in servers.json.
# --allowed-host: mcp-proxy rejects any Host header but localhost (421 Invalid Host
# header), so the name other containers use to reach this one must be listed.
exec mcp-proxy \
  --pass-environment \
  --host 0.0.0.0 \
  --port 7015 \
  --allowed-host paperless-mcp \
  --allowed-host paperless-mcp:7015 \
  --named-server-config /opt/paperless-mcp/servers.json
