# Paperless-ngx MCP behind mcp-proxy, in its OWN container.
#
# Deliberately not hosted in the shared stdio-proxy: that proxy starts with
# --pass-environment (every child would inherit this API token) and initialises
# all of its servers fatally (one failing child takes the rest down).
#
# Base is pinned by digest. Bump with:
#   docker pull ghcr.io/sparfenyuk/mcp-proxy:latest
#   docker image inspect ghcr.io/sparfenyuk/mcp-proxy:latest --format '{{index .RepoDigests 0}}'
FROM ghcr.io/sparfenyuk/mcp-proxy@sha256:ecbe838e41b3bbfaccc009b234d34bc285b8bf4479d143454e5a35cf41f646b2

# nodejs comes from the Alpine release the pinned base ships, so it only moves
# when the base digest is bumped. npm is needed at build time only.
RUN apk add --no-cache nodejs

WORKDIR /opt/paperless-mcp

# Exact version + lockfile with integrity hashes. Lifecycle scripts are disabled:
# the package needs none to run, and a dependency's install script must not
# execute in the same container that holds the token.
COPY package.json package-lock.json ./
RUN apk add --no-cache --virtual .build npm \
 && npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
 && npm cache clean --force \
 && apk del .build

COPY servers.json entrypoint.sh ./
RUN chmod 0555 entrypoint.sh \
 && addgroup -S mcp && adduser -S -G mcp -H -s /sbin/nologin mcp

USER mcp
EXPOSE 7015
ENTRYPOINT ["/opt/paperless-mcp/entrypoint.sh"]
