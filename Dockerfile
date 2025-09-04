# Simplified single-stage Dockerfile for reliable builds
# Uses Alpine Linux with direct pip installation

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

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir -e .

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