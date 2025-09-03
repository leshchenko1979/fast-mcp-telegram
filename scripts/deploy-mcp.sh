#!/bin/bash

set -e

RED="$(tput setaf 1)"
GREEN="$(tput setaf 2)"
BLUE="$(tput setaf 4)"
BOLD="$(tput bold)"
RESET="$(tput sgr0)"

start_time=$(date +%s)

log() {
  local color="$1"; shift
  local ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo -e "${color}${BOLD}[${ts}] $*${RESET}"
}

require_env() {
  local var="$1"
  if [ -z "${!var}" ]; then
    log "$RED" "Missing required env: $var"
    exit 1
  fi
}

validate() {
  if [ ! -f docker-compose.yml ]; then
    log "$RED" "docker-compose.yml not found"
    exit 1
  fi
  if [ ! -f .env ]; then
    log "$RED" ".env not found"
    exit 1
  fi
  # Load .env safely
  export $(grep -v '^#' .env | grep -v '^$' | xargs)
  require_env VDS_USER
  require_env VDS_HOST
  require_env VDS_PROJECT_PATH
}

deploy() {
  log "$BLUE" "Preparing remote directory..."

  ssh "$VDS_USER@$VDS_HOST" "rm -rf $VDS_PROJECT_PATH && mkdir -p $VDS_PROJECT_PATH"

  log "$BLUE" "Transferring project files..."
  # Create a temporary file list excluding deleted files
  git ls-files | xargs ls -d 2>/dev/null | tar -czf - --files-from=- | ssh "$VDS_USER@$VDS_HOST" "tar -xzf - -C $VDS_PROJECT_PATH"
  scp -C .env "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/.env"

  # Clean up macOS resource fork files
  ssh "$VDS_USER@$VDS_HOST" "find $VDS_PROJECT_PATH -name '._*' -delete 2>/dev/null || true"

  log "$BLUE" "Note: Session files are managed per-environment and should be set up separately on the remote server"

  log "$BLUE" "Starting containers..."
  if ! ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose --env-file .env up --build -d"; then
    log "$RED" "Failed to start containers"
    exit 1
  fi

  log "$BLUE" "Checking health..."
  ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose ps && echo '=== Recent logs ===' && docker compose logs --since=1m fast-mcp-telegram | tail -n 20 | cat"
}

validate
deploy

elapsed=$(( $(date +%s) - start_time ))
log "$GREEN" "Deployment finished in ${elapsed}s"


