FROM python:3.12-slim

WORKDIR /app

# Install uv (fast resolver/installer)
RUN pip install --no-cache-dir uv

# Copy dependency metadata first for better caching
COPY pyproject.toml uv.lock ./

# Install locked dependencies into the system Python
RUN uv sync --frozen --no-dev --system

# Copy application code
COPY . ./

# This keeps the container alive so we can test connectivity
CMD ["tail", "-f", "/dev/null"]