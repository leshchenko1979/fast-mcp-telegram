#!/usr/bin/env bash
# Deploy fast-mcp-telegram to production.
# Usage: ./scripts/deploy.sh [version]
#   version defaults to `git describe --tags` (or "dev" if not in a git repo)
#
# Prerequisites:
#   - SSH access to the apps host configured in ~/.ssh/config
#   - Docker on the remote host
#   - Source committed (the script copies the working tree via rsync)
#
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-apps}"
REMOTE_DIR="${REMOTE_DIR:-/root/fast-mcp-telegram}"
VERSION="${1:-$(git describe --tags --dirty --always 2>/dev/null || echo "dev")}"
GHCR_IMAGE="ghcr.io/leshchenko1979/fast-mcp-telegram"
COMPOSE_FILE="docker-compose.yml"
SERVICE="fast-mcp-telegram"
CONTAINER_NAME="fast-mcp-telegram"

echo "=== Deploy ${VERSION} → ${REMOTE_HOST} ==="

# ------- 1. Sync source to remote -------
echo "--- Syncing source ---"
# Ensure remote dir exists (macOS rsync lacks --mkpath)
ssh "${REMOTE_HOST}" "mkdir -p ${REMOTE_DIR}"
rsync -avz --delete \
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    --exclude '*.pyc' --exclude '*.pyo' \
    --exclude '.env' --exclude '.env.local' --exclude '.env.remote' \
    --exclude '.cursor' --exclude 'memory-bank' --exclude 'dist' --exclude 'build' \
    --exclude '*.egg-info' --exclude '.mypy_cache' --exclude '.ruff_cache' \
    --exclude '.pytest_cache' --exclude 'htmlcov' --exclude '.coverage*' \
    --exclude 'logs' --exclude '*.session' --exclude 'sessions' \
    --exclude '.mcpregistry_*' --exclude '.DS_Store' \
    ./ "${REMOTE_HOST}:${REMOTE_DIR}/"

# ------- 2. Save current tag for rollback -------
CURRENT_TAG=""
if ssh "${REMOTE_HOST}" "docker container inspect ${CONTAINER_NAME} >/dev/null 2>&1"; then
    CURRENT_TAG=$(ssh "${REMOTE_HOST}" \
        "docker inspect --format '{{.Config.Image}}' ${CONTAINER_NAME} 2>/dev/null" \
        | awk -F: '{print $NF}')
fi
echo "   Current: ${CURRENT_TAG:-none}  Target: ${VERSION}"

# ------- 3. Build image ----
echo "--- Building ${GHCR_IMAGE}:${VERSION} ---"
ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && docker build -t ${GHCR_IMAGE}:${VERSION} ."

# ------- 4. Replace any orphan container using the fixed name -------
# Previous deploys may have started the container outside this compose project.
echo "--- Replacing container ${CONTAINER_NAME} ---"
ssh "${REMOTE_HOST}" "docker stop ${CONTAINER_NAME} >/dev/null 2>&1 || true; docker rm ${CONTAINER_NAME} >/dev/null 2>&1 || true"

# ------- 5. Deploy via compose & wait for healthy ----
echo "--- Deploying via compose ---"
if ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && IMAGE_TAG=${VERSION} docker compose up --wait --wait-timeout 90 ${SERVICE}"; then
    echo "✅ ${VERSION} deployed — healthy."
    # Clean up dangling layers only; keep version-tagged images for rollback
    ssh "${REMOTE_HOST}" "docker image prune -f --filter 'dangling=true'"
    exit 0
fi

echo "❌ Healthcheck failed within 90s timeout."
if [ -n "${CURRENT_TAG}" ]; then
    echo "   Rolling back to ${CURRENT_TAG}..."
    ssh "${REMOTE_HOST}" "docker stop ${CONTAINER_NAME} >/dev/null 2>&1 || true; docker rm ${CONTAINER_NAME} >/dev/null 2>&1 || true"
    # Prefer local image (may not exist on GHCR); compose pull is not required.
    if ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && IMAGE_TAG=${CURRENT_TAG} docker compose up --pull never --wait --wait-timeout 60 ${SERVICE}"; then
        echo "   Rolled back to ${CURRENT_TAG}."
    else
        echo "   Rollback also failed — check container logs."
    fi
else
    echo "   No previous tag — manual intervention required."
fi
exit 1
