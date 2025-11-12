# Chrome DevTools MCP Setup (Unsuccessful)

This documents an attempted setup of the Chrome DevTools MCP server in Docker that ultimately did not work due to Chrome's security restrictions.

## Attempted Architecture

```
Cline (VS Code)
    ↓ mcp-remote via localhost:9000/mcp
MCPX Gateway (Docker container)
    ↓ --browser-url flag
Chrome DevTools MCP Server (inside mcpx container)
    ↓ HTTP request to host.docker.internal:9222
localhost:9222 (nginx-ssl container proxy)
    ↓ HTTP proxy
Chrome browser on host (--remote-debugging-port=9222)
```

## Why It Didn't Work

**Chrome's localhost-only restriction on macOS:**

Chrome/Chromium on macOS have hardcoded security that **only allows HTTP debugging endpoint connections from 127.0.0.1** (localhost). This restriction cannot be bypassed with command-line flags.

### What We Tried

1. **`--remote-allow-origins="*"` flag**

   - Only affects WebSocket CORS, not HTTP endpoint access
   - Chrome still rejected HTTP connections from non-localhost IPs

2. **`--remote-debugging-address=0.0.0.0` flag**

   - Intended to bind to all interfaces
   - Doesn't work on macOS - Chrome still binds only to 127.0.0.1
   - Verified with `lsof -i :9222` showing only 127.0.0.1:9222

3. **Nginx proxy on port 9222**

   - Successfully proxied connections
   - Chrome rejected them because source IP was 192.168.65.254 (Docker)
   - Returns 500 Internal Server Error

4. **TCP forwarding with socat**

   - Attempted to proxy connections through localhost
   - Chrome still saw the original source IP and rejected

5. **Chromium as alternative**
   - Has identical security restrictions to Chrome
   - Same localhost-only limitation

### Test Results

```bash
# From host (works)
curl http://localhost:9222/json
# Returns 200 OK with target list

# From Docker (fails)
curl http://host.docker.internal:9222/json
# Returns 500 Internal Server Error
```

## Configuration Attempted

### docker-compose.yml

```yaml
nginx-ssl:
  ports:
    - '9222:9222' # Chrome DevTools Protocol proxy port
```

### nginx.conf

```nginx
server {
    listen 9222;
    server_name localhost;

    location / {
        set $chrome_host host.docker.internal;
        proxy_pass http://$chrome_host:9222;
        proxy_http_version 1.1;

        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_connect_timeout 3600s;
    }
}
```

### mcp.json

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "chrome-devtools-mcp@latest",
        "--browser-url=http://host.docker.internal:9222"
      ]
    }
  }
}
```

## Conclusion

The Chrome DevTools MCP server **cannot run in Docker and connect to a Chrome instance on the host** due to Chrome's security architecture on macOS. The HTTP debugging endpoint only accepts connections from 127.0.0.1, which excludes Docker containers.

## Alternative Solution: Kapture

We successfully implemented [Kapture](./kapture.md) instead, which:

- Uses a Chrome extension (runs inside the browser)
- Connects OUT to the server via WebSocket (reverse direction)
- No localhost restriction since extension initiates the connection
- Works perfectly with Docker infrastructure
