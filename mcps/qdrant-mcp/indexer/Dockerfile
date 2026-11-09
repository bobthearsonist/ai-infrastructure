# Qdrant indexers for Obsidian vaults and code repositories
# Multi-stage: 'cpu' target for obsidian-indexer, 'gpu' target for repo-indexer
#
# Build targets:
#   cpu   - python:3.12-slim + fastembed (small image, CPU embedding)
#   gpu   - nvidia/cuda + fastembed-gpu (large image, GPU-accelerated embedding)
#   intel - ubuntu + onnxruntime-openvino (Intel iGPU under WSL2)

# ---- CPU target (default) ----
FROM python:3.12-slim AS cpu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY index_obsidian.py .
COPY index_repos.py .
COPY chunking.py .
COPY filters.py .
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
COPY filters.py .
COPY watcher.py .

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# ---- Intel target ----
# OpenVINO execution provider for Intel iGPUs under WSL2. The GPU is reached
# through /dev/dxg plus the host's /usr/lib/wsl libraries, so the container
# needs those mapped in (see docker-compose.intel-gpu.yml). The kobuk-team
# PPA carries a compute runtime new enough for recent Intel graphics
# (the Ubuntu archive build predates Xe3). The NPU is not exposed to WSL2.
FROM ubuntu:24.04 AS intel

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common gpg-agent python3.12 python3-pip python3.12-venv \
    && add-apt-repository -y ppa:kobuk-team/intel-graphics \
    && apt-get update && apt-get install -y --no-install-recommends \
    libze-intel-gpu1 libze1 intel-opencl-icd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-intel.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements-intel.txt \
    && pip uninstall -y --break-system-packages onnxruntime \
    && pip install --no-cache-dir --break-system-packages onnxruntime-openvino==1.24.1

COPY index_obsidian.py .
COPY index_repos.py .
COPY chunking.py .
COPY filters.py .
COPY watcher.py .

ENV LD_LIBRARY_PATH=/usr/lib/wsl/lib
