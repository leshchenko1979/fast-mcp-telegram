#!/usr/bin/env bash
# Push docker-compose.yml and runtime .env to the VDS, then docker compose pull && up -d.
# Optional GHCR_PULL_* in local .env for private registry login on the server.
# Primary deploy path is GitHub Actions; use this to bootstrap or refresh the server directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${SSH_HOST:?Set SSH_HOST in .env}"
: "${SSH_USER:?Set SSH_USER in .env}"

REMOTE_DOCKER_DIR="${REMOTE_DOCKER_DIR:-/root/services/fast-mcp-telegram}"

if [[ ! -f .env ]]; then
  echo ".env not found. Copy from .env.example." >&2
  exit 1
fi

ssh_opts=(-o ServerAliveInterval=15 -o ServerAliveCountMax=3)
if [[ -n "${SSH_KEY:-}" ]]; then
  ssh_opts+=(-i "$SSH_KEY")
fi
if [[ -n "${SSH_PORT:-}" ]]; then
  ssh_opts+=(-p "$SSH_PORT")
fi

RUNTIME_ENV=$(mktemp)
trap 'rm -f "$RUNTIME_ENV"' EXIT
grep -vE '^(SSH_HOST|SSH_USER|SSH_KEY|SSH_PORT|GHCR_PULL_USER|GHCR_PULL_TOKEN)=' .env > "$RUNTIME_ENV"

target="${SSH_USER}@${SSH_HOST}"

echo "[sync] mkdir ${REMOTE_DOCKER_DIR}"
ssh "${ssh_opts[@]}" "$target" "mkdir -p '${REMOTE_DOCKER_DIR}'"

echo "[sync] scp docker-compose.yml"
scp "${ssh_opts[@]}" docker-compose.yml "${target}:${REMOTE_DOCKER_DIR}/docker-compose.yml"

echo "[sync] scp .env (runtime only, SSH and GHCR pull vars excluded)"
scp "${ssh_opts[@]}" "$RUNTIME_ENV" "${target}:${REMOTE_DOCKER_DIR}/.env"

echo "[sync] remote: optional docker login + compose pull && up -d"
ssh "${ssh_opts[@]}" "$target" bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_DOCKER_DIR}"
if [[ -n "${GHCR_PULL_TOKEN:-}" ]] && [[ -n "${GHCR_PULL_USER:-}" ]]; then
  echo "${GHCR_PULL_TOKEN:-}" | docker login ghcr.io -u "${GHCR_PULL_USER:-}" --password-stdin
fi
docker compose pull && docker compose up -d --wait
REMOTE

echo "[sync] done."