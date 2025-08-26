FROM python:3.12-slim

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Environment for FastMCP HTTP
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    PYTHONUNBUFFERED=1

# Default: store Telethon session in a mounted volume under /data
# settings.py computes SESSION_PATH = PROJECT_DIR / SESSION_NAME
# By setting SESSION_NAME absolute, it will not join with PROJECT_DIR
ENV SESSION_NAME=/data/mcp_telegram

EXPOSE 8000

# Healthcheck: succeed if HTTP server accepts connections (status code agnostic)
HEALTHCHECK --interval=5s --timeout=5s --retries=3 CMD curl -sS -o /dev/null http://localhost:8000 || exit 1

CMD ["python", "-m", "src.server"]


