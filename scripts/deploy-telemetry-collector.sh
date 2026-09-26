#!/usr/bin/env bash
# Deploy telemetry collector to remote server.
# Usage:
#   ./scripts/deploy-telemetry-collector.sh            # uses default SSH_HOST from .env
#   ./scripts/deploy-telemetry-collector.sh apps        # explicit host
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

SSH_HOST="${1:-${SSH_HOST:?Set SSH_HOST in .env or pass as first argument}}"
: "${SSH_USER:?Set SSH_USER in .env}"
: "${TELEMETRY_DB_PASSWORD:?Set TELEMETRY_DB_PASSWORD in .env}"

REMOTE_DIR="${REMOTE_DIR:-/root/services/telemetry-collector}"

ssh_opts=(-o ServerAliveInterval=15 -o ServerAliveCountMax=3)
if [[ -n "${SSH_KEY:-}" ]]; then
  ssh_opts+=(-i "$SSH_KEY")
fi
if [[ -n "${SSH_PORT:-}" ]]; then
  ssh_opts+=(-p "$SSH_PORT")
fi

target="${SSH_USER}@${SSH_HOST}"

echo "[deploy] mkdir ${REMOTE_DIR}"
ssh "${ssh_opts[@]}" "$target" "mkdir -p '${REMOTE_DIR}'"

echo "[deploy] scp docker-compose.yml"
scp "${ssh_opts[@]}" collector/docker-compose.yml "${target}:${REMOTE_DIR}/"

echo "[deploy] set up .env on remote"
ssh "${ssh_opts[@]}" "$target" "
cat > '${REMOTE_DIR}/.env' <<'ENVEOF'
GHCR_IMAGE=ghcr.io/leshchenko1979/telemetry-collector
IMAGE_TAG=main
TELEMETRY_DB_PASSWORD=${TELEMETRY_DB_PASSWORD}
ENVEOF
"

echo "[deploy] ensure telemetry database and user exist"
ssh "${ssh_opts[@]}" "$target" '
set -euo pipefail
docker exec postgres psql -U postgres -tc \
  "SELECT 1 FROM pg_roles WHERE rolname='\''telemetry'\''" \
  | grep -q 1 || \
  docker exec postgres psql -U postgres -c \
    "CREATE ROLE telemetry WITH LOGIN PASSWORD '\''${TELEMETRY_DB_PASSWORD}'\'';"
docker exec postgres psql -U postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname='\''telemetry'\''" \
  | grep -q 1 || \
  docker exec postgres psql -U postgres -c \
    "CREATE DATABASE telemetry OWNER telemetry;"
'

echo "[deploy] docker compose pull && up -d"
ssh "${ssh_opts[@]}" "$target" bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_DIR}"

# Login to GHCR if token is available
if [[ -n "\${GHCR_PULL_TOKEN:-}" ]] && [[ -n "\${GHCR_PULL_USER:-}" ]]; then
  echo "\${GHCR_PULL_TOKEN:-}" | docker login ghcr.io -u "\${GHCR_PULL_USER:-}" --password-stdin
fi

docker compose pull && docker compose up -d --wait
REMOTE

echo "[deploy] verifying health..."
sleep 3
if ssh "${ssh_opts[@]}" "$target" "docker exec telemetry-collector sh -c 'wget -qO- http://localhost:8000/health' 2>/dev/null"; then
  echo "[deploy] telemetry collector is healthy."
else
  echo "[deploy] WARNING: health check failed. Check logs with: docker logs telemetry-collector"
fi

echo "[deploy] done."
