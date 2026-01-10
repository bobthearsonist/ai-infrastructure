# Kilo Code Configuration for Ollama

This document describes the recommended configuration for using Kilo Code with Ollama.

## Configuration Location

Kilo Code stores its settings at:

```
~/Library/Application Support/Code/User/globalStorage/kilocode.kilo-code/settings/
```

Key files:

- `kilo_mcp_settings.json` - MCP server configurations
- Model and API settings are stored in VSCode's extension settings

## Prerequisites

- **Ollama** installed and running on `localhost:11434`
- **Model**: `qwen2.5-coder:32b` (or other compatible models)

## API Provider Settings

Configure these in VSCode: `Settings → Extensions → Kilo Code`

| Setting         | Value                    |
| --------------- | ------------------------ |
| API Provider    | `Ollama`                 |
| Ollama Base URL | `http://localhost:11434` |
| Model ID        | `qwen2.5-coder:32b`      |

## Model Parameters

### Recommended Settings for Code Generation

| Parameter      | Value       | Description                                           |
| -------------- | ----------- | ----------------------------------------------------- |
| Temperature    | `0.1 - 0.3` | Lower values produce more deterministic, focused code |
| Max Tokens     | `8192`      | Maximum response length                               |
| Context Window | `32768`     | qwen2.5-coder:32b supports 32K context                |

### Temperature Guidelines

| Use Case              | Temperature |
| --------------------- | ----------- |
| Code generation       | `0.1`       |
| Code refactoring      | `0.15`      |
| Documentation         | `0.2`       |
| Architecture planning | `0.3`       |
| Creative solutions    | `0.5`       |

## Mode-Specific Configuration

Kilo Code supports different modes, each optimized for specific tasks:

### Code Mode

- **Model**: `qwen2.5-coder:32b`
- **Temperature**: `0.1`
- **Best for**: Writing, modifying, and refactoring code

### Architect Mode

- **Model**: `qwen2.5-coder:32b`
- **Temperature**: `0.3`
- **Best for**: Planning, design, and system architecture

### Ask Mode

- **Model**: `qwen2.5-coder:32b`
- **Temperature**: `0.2`
- **Best for**: Explanations, documentation, and Q&A

### Debug Mode

- **Model**: `qwen2.5-coder:32b`
- **Temperature**: `0.1`
- **Best for**: Troubleshooting, error analysis, and fixes

## Ollama Performance Tuning

Add these environment variables to your `~/.zshrc` for optimal performance with large models:

```bash
# Ollama performance settings for large models (32B+)
export OLLAMA_NUM_PARALLEL=1        # Limit parallel requests
export OLLAMA_MAX_LOADED_MODELS=1   # Keep only one model in memory
export OLLAMA_KEEP_ALIVE="30m"      # Keep model loaded for 30 minutes
export OLLAMA_FLASH_ATTENTION=1     # Enable flash attention if supported
```

After adding, reload your shell:

```bash
source ~/.zshrc
```

## Memory Considerations

For `qwen2.5-coder:32b`:

- **VRAM Required**: ~20-24GB for full precision, ~12-16GB for Q4 quantization
- **RAM Fallback**: Model will use system RAM if VRAM is insufficient (slower)

### Check Model Status

```bash
# List running models
ollama ps

# Check model details
ollama show qwen2.5-coder:32b

# Pull/update model
ollama pull qwen2.5-coder:32b
```

## MCP Server Configuration

Kilo Code uses its own MCP settings file, separate from Cline.

### Setting Up Symlink (Optional)

To share MCP configurations between this repo and Kilo Code:

```bash
# Create symlink from Kilo Code settings to this repo
ln -sf ~/Repositories/ai-infrastructure/clients/kilocode/kilo_mcp_settings.json \
    ~/Library/Application\ Support/Code/User/globalStorage/kilocode.kilo-code/settings/kilo_mcp_settings.json
```

Or to sync from existing Kilo Code settings to this repo:

```bash
# Copy existing settings first (if any)
cp ~/Library/Application\ Support/Code/User/globalStorage/kilocode.kilo-code/settings/kilo_mcp_settings.json \
   ~/Repositories/ai-infrastructure/clients/kilocode/kilo_mcp_settings.json

# Then create symlink
ln -sf ~/Repositories/ai-infrastructure/clients/kilocode/kilo_mcp_settings.json \
    ~/Library/Application\ Support/Code/User/globalStorage/kilocode.kilo-code/settings/kilo_mcp_settings.json
```

## Troubleshooting

### Model Not Responding

1. Check Ollama is running: `ollama ps`
2. Verify model is loaded: `curl http://localhost:11434/api/tags`
3. Restart Ollama: `ollama serve`

### Slow Performance

1. Ensure `OLLAMA_NUM_PARALLEL=1` is set
2. Close other GPU-intensive applications
3. Consider using a quantized model variant

### Context Length Errors

1. Reduce input size or break into smaller chunks
2. Increase `Context Window` setting if supported
3. Use `Max Tokens` to limit response length

## Alternative Models

Other Ollama models compatible with Kilo Code:

| Model                | Size | Context | Best For                |
| -------------------- | ---- | ------- | ----------------------- |
| `qwen2.5-coder:32b`  | 32B  | 32K     | Full-featured coding    |
| `qwen2.5-coder:14b`  | 14B  | 32K     | Balanced performance    |
| `qwen2.5-coder:7b`   | 7B   | 32K     | Fast responses          |
| `codellama:34b`      | 34B  | 16K     | Legacy codebase support |
| `deepseek-coder:33b` | 33B  | 16K     | Algorithm-focused tasks |

## Version Info

- **Kilo Code Extension**: Latest from VS Code Marketplace
- **Ollama**: v0.1.x or later
- **Model**: qwen2.5-coder:32b
