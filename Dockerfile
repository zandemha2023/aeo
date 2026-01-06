# Multi-stage Dockerfile for AEO Orchestrator
# Supports both API server and background worker

FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 aeo && \
    useradd --uid 1000 --gid aeo --shell /bin/bash --create-home aeo

WORKDIR /app

# Install Python dependencies
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final image
FROM dependencies AS final

# Copy application code
COPY --chown=aeo:aeo . .

# Switch to non-root user
USER aeo

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8000}/health || exit 1

# Default environment
ENV APP_ENV=production \
    LOG_LEVEL=INFO \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Expose API port
EXPOSE 8000

# Default command: run API server
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Worker target for background jobs
FROM final AS worker

# Override health check for worker (check Redis connection)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import redis; redis.from_url('${REDIS_URL:-redis://localhost:6379}').ping()" || exit 1

# Worker command
CMD ["python", "-m", "arq", "jobs.worker.WorkerSettings"]
