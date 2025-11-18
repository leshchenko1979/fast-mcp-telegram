# Production-optimized Dockerfile without editable install
# Uses Alpine Linux with clean dependency installation

FROM python:3-alpine

# Install essential runtime dependencies
RUN apk add --no-cache curl

WORKDIR /app

COPY pyproject.toml ./
RUN mkdir -p src && touch src/__init__.py
COPY src/_version.py ./src/_version.py

RUN pip install --no-cache-dir uv; \
    uv pip install --system --no-cache -r pyproject.toml; \
    pip uninstall -y uv; \
    rm -rf /root/.cache/uv

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

# Add local bin to PATH to fix script warnings
ENV PATH="/home/appuser/.local/bin:$PATH"

# Environment for FastMCP HTTP
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose the application's port
EXPOSE 8000

# Healthcheck: use the dedicated health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --start-interval=1s --retries=1 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["python", "-m", "src.server"]