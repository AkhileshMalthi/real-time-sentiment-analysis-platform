FROM python:3.12-slim

WORKDIR /app

# Install uv from official image (faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency metadata first for better caching
COPY pyproject.toml uv.lock ./

# Install locked dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Pre-download HuggingFace models during build (not at runtime)
RUN uv run python -c "from transformers import pipeline; \
    pipeline('text-classification', model='distilbert-base-uncased-finetuned-sst-2-english'); \
    pipeline('text-classification', model='j-hartmann/emotion-english-distilroberta-base')"

# Copy application code
COPY . ./

# This keeps the container alive so we can test connectivity
CMD ["tail", "-f", "/dev/null"]