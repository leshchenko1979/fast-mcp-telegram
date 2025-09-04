# Production-optimized Dockerfile without editable install
# Uses Alpine Linux with clean dependency installation

FROM python:3-alpine

# Install essential runtime dependencies
RUN apk add --no-cache curl

# Create non-root user for security
RUN addgroup -g 1000 appuser && \
    adduser -D -s /bin/sh -u 1000 -G appuser appuser

# Switch to non-root user
USER appuser

# Set the working directory
WORKDIR /app

# Copy dependency files and minimal package structure for caching
COPY pyproject.toml ./
RUN mkdir -p src && touch src/__init__.py

# Install package with dependencies (minimal src structure satisfies pip)
# This layer will be cached and not rebuilt unless pyproject.toml changes
RUN pip install --no-cache-dir .

# Copy real source code (this layer rebuilds when code changes)
COPY src/ ./src/

# Environment for FastMCP HTTP
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Session files stored in user config directory (~/.config/fast-mcp-telegram/)
# as determined by settings.py logic for cross-platform compatibility

# Expose the application's port
EXPOSE 8000

# Healthcheck: use the dedicated health endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["python", "-m", "src.server"]