FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libgtk-4-1 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Install browsers (both Chrome and Firefox for ARM64)
# Install Chromium (ARM64 compatible alternative to Chrome)
RUN apt-get update \
    && apt-get install -y chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Firefox ESR
RUN apt-get update \
    && apt-get install -y firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir uv

# Install browser-use with MCP support
RUN uv pip install --system "browser-use[cli]" mcp playwright

# Install playwright browsers
RUN playwright install chromium --with-deps

# Create directories for data persistence
RUN mkdir -p /app/.browser-cache /app/profiles /app/resume-data

# Create a non-root user
RUN useradd -m -u 1001 browseruse && \
    chown -R browseruse:browseruse /app

USER browseruse

# Copy entrypoint script and health server, set permissions
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh
COPY health_server.py /app/health_server.py

# Expose port for health checks
EXPOSE 7009

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
