# === Build stage ===
FROM ghcr.io/astral-sh/uv:0.7-python3.11-bookworm-slim AS builder

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install project
COPY src/ src/
RUN uv sync --frozen --no-dev

# === Runtime stage ===
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Ensure the venv's Python is used
ENV PATH="/app/.venv/bin:$PATH"

# Default port; override with PORT env var
ENV PORT=8080

EXPOSE ${PORT}

# Non-root user
RUN useradd --create-home appuser
USER appuser

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health', timeout=5)" || exit 1

ENTRYPOINT ["python", "-m", "pac"]
