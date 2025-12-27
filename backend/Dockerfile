FROM python:3.12-slim

WORKDIR /app

# Install uv from official image (faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency metadata first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies system-wide (no venv needed in container)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml --group dev

# Copy application code
COPY . ./

# Run database initialization and start the FastAPI server
CMD ["sh", "-c", "python init_db.py && uvicorn main:app --host 0.0.0.0 --port 8000"]