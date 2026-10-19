# Production-optimized Dockerfile without editable install
# Uses Alpine Linux with clean dependency installation

# Pinned to 3.14 on purpose: the floating `python:3-alpine` tag moved to 3.15,
# which has no pydantic-core wheels yet, so uv fell back to a source build and
# died on the missing C toolchain (#162). 3.14 is the interpreter this project
# develops and tests on, and every locked dependency ships a cp314 musllinux
# wheel, so the build stage needs no compiler.
FROM python:3.14-alpine

# Install essential runtime dependencies
RUN apk add --no-cache curl

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
RUN mkdir -p src && touch src/__init__.py
COPY src/_version.py ./src/_version.py

# Install uv and sync dependencies from lock file into .venv
# --no-install-project: install deps only, project source comes from filesystem COPY later
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
RUN uv sync --frozen --no-dev --no-install-project && \
    rm -rf /root/.cache/uv

# Configure .venv as active Python environment
# uv sync creates .venv by default (no --system flag in current uv 0.11.x)
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user for security
RUN addgroup -g 1000 appuser && \
    adduser -D -s /bin/sh -u 1000 -G appuser appuser

# Create necessary directories and set permissions before switching user
RUN mkdir -p logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Copy real source code (this layer rebuilds when code changes)
COPY src/ ./src/

# Environment defaults for FastMCP HTTP
ENV SERVER_MODE=http-auth \
    HOST=0.0.0.0 \
    PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose the application's port
EXPOSE 8000

# Healthcheck: use the dedicated health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=2 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["python", "-m", "src.server"]
