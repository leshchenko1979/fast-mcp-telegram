# Production-optimized Dockerfile using uv for dependency management
# Uses Alpine Linux for minimal size and global installation for production efficiency
# No virtual environment needed - container provides isolation

# Stage 1: Builder
FROM python:3-alpine AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables for uv optimizations
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Set the working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in venv first, then copy to system
RUN uv sync --frozen --no-install-project

# Copy application source code
COPY . .

# Install the project
RUN uv sync --frozen

# Stage 2: Runtime
FROM python:3-alpine AS runtime

# Install only essential runtime dependencies
RUN apk add --no-cache curl

# Create non-root user for security
RUN addgroup -g 1000 appuser && \
    adduser -D -s /bin/sh -u 1000 -G appuser appuser

# Switch to non-root user
USER appuser

# Set the working directory
WORKDIR /app

# Copy venv from builder (single efficient copy operation)
COPY --from=builder /app/.venv /app/.venv

# Copy only necessary application source files
COPY src/ ./src/

# Set PATH to use venv binaries directly
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


