# Multi-stage Dockerfile using uv for dependency management
# Based on best practices from uv optimization examples

# Stage 1: Builder
FROM python:3-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables for uv optimizations
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Set the working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in a virtual environment
RUN uv sync --frozen --no-install-project

# Copy application source code
COPY . .

# Install the project itself
RUN uv sync --frozen

# Stage 2: Runtime
FROM python:3-slim AS runtime

# Install curl for healthchecks in runtime stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home appuser

# Switch to non-root user for security
USER appuser

# Set the working directory
WORKDIR /app

# Copy the virtual environment and application from the builder stage
COPY --from=builder /app /app

# Add the virtual environment's binary directory to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Environment for FastMCP HTTP
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default: store Telethon session in a mounted volume under /data
# settings.py computes SESSION_PATH = PROJECT_DIR / SESSION_NAME
# By setting SESSION_NAME absolute, it will not join with PROJECT_DIR
ENV SESSION_NAME=/data/mcp_telegram

# Expose the application's port
EXPOSE 8000

# Healthcheck: succeed if HTTP server accepts connections (status code agnostic)
HEALTHCHECK --interval=5s --timeout=5s --retries=3 \
    CMD curl -sS -o /dev/null http://localhost:8000 || exit 1

# Command to run the application
CMD ["python", "-m", "src.server"]


