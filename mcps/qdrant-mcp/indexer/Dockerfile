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
COPY chunking.py .
COPY watcher.py .

# ---- GPU target ----
# CUDA 13 base to match onnxruntime-gpu 1.27 (ships libcudart.so.13). Host
# driver 581.95 supports CUDA 13.0. Bumped from 12.6.3 after an unpinned
# rebuild pulled the CUDA-13 onnxruntime onto the old CUDA-12 base.
FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04 AS gpu

# Install Python 3.12 (ships with Ubuntu 24.04)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3-pip python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-gpu.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements-gpu.txt

COPY index_obsidian.py .
COPY index_repos.py .
COPY chunking.py .
COPY watcher.py .

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
