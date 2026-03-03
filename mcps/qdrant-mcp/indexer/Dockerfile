# Qdrant indexers for Obsidian vaults and code repositories
# Multi-stage: 'cpu' target for obsidian-indexer, 'gpu' target for repo-indexer
#
# Build targets:
#   cpu  - python:3.12-slim + fastembed (small image, CPU embedding)
#   gpu  - nvidia/cuda + fastembed-gpu (large image, GPU-accelerated embedding)

# ---- CPU target (default) ----
FROM python:3.12-slim AS cpu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY index_obsidian.py .
COPY index_repos.py .

# ---- GPU target ----
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 AS gpu

# Install Python 3.12 (ships with Ubuntu 24.04)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3-pip python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-gpu.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements-gpu.txt

COPY index_obsidian.py .
COPY index_repos.py .

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
