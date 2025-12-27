FROM python:3.12-slim

WORKDIR /app

# Install uv from official image (faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files from worker subdirectory
COPY worker/pyproject.toml worker/uv.lock ./

# Install dependencies system-wide (no venv needed in container)
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_HTTP_TIMEOUT=600 uv pip install --system -r pyproject.toml --group dev

# Copy shared backend code (sentiment analyzer and models)
COPY backend/services/ ./backend/services/
COPY backend/models/ ./backend/models/
COPY backend/__init__.py ./backend/__init__.py


# Copy worker application code
COPY worker/*.py ./

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

# Disable Python output buffering so we see prints/progress bars immediately
ENV PYTHONUNBUFFERED=1

# Set HuggingFace cache directory (will be mounted as volume)
ENV HF_HOME=/root/.cache/huggingface
ENV HF_HUB_DISABLE_TELEMETRY=1

# Pre-download ML models during build to bake them into the image
# This makes the image larger but ensures models are always available
# Note: NOT using cache mount here so models persist in the image
RUN UV_HTTP_TIMEOUT=600 python -c "\
import os; \
print('Downloading models to:', os.getenv('HF_HOME', 'default')); \
from transformers import pipeline; \
print('Downloading sentiment model...'); \
pipeline('text-classification', model='distilbert-base-uncased-finetuned-sst-2-english'); \
print('Downloading emotion model...'); \
pipeline('text-classification', model='j-hartmann/emotion-english-distilroberta-base'); \
print('Models downloaded successfully')"

# Run the worker script directly (system-wide install)
# Clean stale lock files before starting to prevent deadlocks
CMD ["sh", "-c", "rm -rf /root/.cache/huggingface/**/.locks && python worker.py"]