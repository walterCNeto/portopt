# Dockerfile for the portopt FastAPI service.
# Multi-stage build: separate dependency install from app code for cache efficiency.

FROM python:3.11-slim AS base

# System deps: build tools for some Python packages (scipy/numpy use precompiled wheels,
# but xlrd and pyarrow can need them). Keep minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- Stage 1: install dependencies ----------
# Copy only pyproject.toml first to leverage Docker layer caching
COPY portopt/pyproject.toml /app/portopt/pyproject.toml
COPY portopt/README.md /app/portopt/README.md

# Pre-install just the lockable deps. We use editable mode to enable hot-reload
# during development, but in production we install normally.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        "fastapi>=0.110" \
        "uvicorn[standard]>=0.27" \
        "pydantic>=2.6" \
        "numpy>=1.26" \
        "scipy>=1.11" \
        "pandas>=2.1" \
        "pyarrow>=14" \
        "scikit-learn>=1.3" \
        "matplotlib>=3.8" \
        "seaborn>=0.13" \
        "tqdm>=4.66" \
        "yfinance>=0.2.40" \
        "xlrd>=2.0" \
        "openpyxl>=3.1"

# ---------- Stage 2: app code ----------
COPY portopt /app/portopt

# Install portopt itself (no deps — already installed above)
RUN pip install --no-cache-dir --no-deps -e /app/portopt

# Production env
ENV PORTOPT_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Bind to 0.0.0.0 for Fly.io
CMD ["uvicorn", "portopt.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
