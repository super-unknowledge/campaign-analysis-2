FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy dependency files first for better layer caching —
# rebuilds only reinstall deps if pyproject.toml/uv.lock don't change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy application code
COPY main.py detection.py ./

EXPOSE 8000

CMD ["uv", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]