# adb-mcp (Photoshop MCP)

AI-controlled Adobe Photoshop via Model Context Protocol. Enables natural language photo editing without learning Photoshop.

## Status

🚧 **Setup in progress**

## TODO

- [ ] Push fixes to forked repo (`bobthearsonist/adb-mcp`) once verified
- [ ] Update `docker-compose.yml` `additional_contexts` to use fork URL instead of local path
- [ ] Submit PR to upstream `mikechambers/adb-mcp` with Linux + env config fixes

## Architecture

```text
Host (macOS)
  └─ Photoshop + UXP Plugin → ws://localhost:3927

Containers
  ├─ adb-proxy (Node.js WebSocket bridge, port 3927→3001)
  └─ photoshop-mcp (Python MCP server, stdio)

agentgateway → docker exec photoshop-mcp (stdio)
```

## Build Context

The MCP container uses Docker Compose `additional_contexts` to reference the local adb-mcp source repo:

```yaml
# docker-compose.yml
build:
  context: .
  dockerfile: Dockerfile.mcp
  additional_contexts:
    - adb-mcp-source=/Users/dislexicmofo/Repositories/adb-mcp
```

```dockerfile
# Dockerfile.mcp
COPY --from=adb-mcp-source /mcp/*.py /app/
```

This keeps source code in the `adb-mcp` repo while deployment config lives here.

## Setup

### 1. Start the containers

```bash
cd mcps/adb-mcp
docker-compose up -d
```

### 2. Install Photoshop plugin (host)

#### Option A: Use prebuilt plugin (port 3001)

```bash
# Download plugin
curl -L -o ~/Downloads/Photoshop.MCP.Agent_PS.ccx \
  https://github.com/mikechambers/adb-mcp/releases/download/v0.85.4/Photoshop.MCP.Agent_PS.ccx

# Double-click the .ccx file to install via Creative Cloud Desktop
open ~/Downloads/Photoshop.MCP.Agent_PS.ccx
```

> ⚠️ The prebuilt plugin connects to `localhost:3001`. Update `docker-compose.yml` ports to `3001:3001` if using this option.

#### Option B: Build custom plugin (adds settings UI)

The modified plugin source in the cloned `adb-mcp` repo at `uxp/ps/` includes a **Proxy URL settings field** that persists across restarts. No code changes needed - configure the port directly in Photoshop.

1. **Install UXP Developer Tool** from Adobe Creative Cloud:
   - Open Creative Cloud Desktop → All Apps → Install "UXP Developer Tools"
   - Or direct: <https://creativecloud.adobe.com/apps/download/uxp-developer-tools>

2. **Launch UXP Developer Tool** and enable Developer Mode when prompted (requires admin privileges)

3. **Add the plugin**:
   - Click "Add Plugin" → select `uxp/ps/manifest.json`
   - The plugin appears in your workspace

4. **Package the plugin**:
   - Click the ⋯ menu next to your plugin → "Package"
   - Choose output directory → generates `.ccx` file

5. **Install the packaged plugin**:
   - Double-click the `.ccx` file
   - Click "Install locally" when prompted
   - Confirm trust warning (you built it)

6. **Configure proxy URL in Photoshop**:
   - Open the plugin panel: **Plugins → Photoshop MCP Agent**
   - Enter your proxy URL (e.g., `http://localhost:3927`)
   - Click **Save** - the setting persists across restarts

> 💡 For development, you can skip packaging and use "Load" to hot-reload the plugin directly into Photoshop.

### 3. Enable Photoshop developer mode

1. Launch Photoshop (2025/26.0+)
2. Go to **Settings → Plugins**
3. Check **"Enable Developer Mode"**
4. Restart Photoshop

### 4. Connect the plugin

1. In Photoshop: **Plugins → Photoshop MCP Agent**
2. Click **"Connect to Bridge"**
3. Status should show **green** (connected to ws://localhost:3927)

### 5. Fonts (user fonts recommended)

- This MCP typically does not require fonts unless using text-related tools.
- Default setup mounts only user fonts: `/Users/<you>/Library/Fonts` (no Docker Desktop sharing required).
- System fonts are optional and commented in `docker-compose.yml`. If you need them, share the paths in Docker Desktop and uncomment:
  - `/System/Library/Fonts`
  - `/Library/Fonts`

Verify inside the container:

```bash
docker exec photoshop-mcp python -c "import os; print(os.environ.get('FONT_DIRS'))"
docker exec photoshop-mcp python - <<'PY'
from fonts import list_all_fonts_postscript
names = list_all_fonts_postscript()
print(f"Fonts enumerated: {len(names)}")
print(names[:10])
PY
```

### 6. Configure agentgateway

Add to `gateways/agentgateway/config.yaml`:

```yaml
- name: photoshop
  stdio:
    command: docker
    args:
      - exec
      - -i
      - photoshop-mcp
      - python
      - -u
      - ps-mcp.py
```

Then restart agentgateway:

```bash
cd ../../gateways/agentgateway
docker-compose restart agentgateway
```

## Capabilities

### Photo Editing

- Remove objects (Generative Fill)
- Remove background (AI selection)
- Select subject/sky
- Color adjustments (brightness, contrast, vibrance, B&W)
- Layer effects (shadows, strokes, gradients)
- Cropping, resizing, rotating
- Export (JPG, PNG, PSD)

### Example Commands

Via AI assistant:

- "Remove the person in the background"
- "Make this look like a vintage Polaroid"
- "Create a double exposure with a forest"
- "Extract subject and remove background"
- "Apply vignette and increase saturation"
- "Export each layer as PNG for a GIF"

## Ports

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| 3927 | adb-proxy | WebSocket | Photoshop plugin connection (host → container 3001) |
| 3928 | adb-proxy | HTTP | Health/status endpoint (host → container 3000) |

## Troubleshooting

| Issue                            | Solution                                                |
| -------------------------------- | ------------------------------------------------------- |
| Plugin won't connect             | Verify adb-proxy running: `docker ps \| grep adb-proxy` |
| WebSocket errors                 | Check logs: `docker logs adb-proxy`                     |
| MCP not responding               | Check: `docker logs photoshop-mcp`                      |
| MCP keeps restarting             | Check PROXY_URL env: should be `ws://adb-proxy:3001`    |
| "Unsupported platform: linux"    | Ensure using patched fonts.py with Linux support        |
| Can't find tools in agentgateway | Verify config and restart gateway                       |

## References

- [mikechambers/adb-mcp](https://github.com/mikechambers/adb-mcp) - Official repo
- [Discord](https://discord.gg/fgxw9t37D7) - Community support
