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
  
  log "$BLUE" "Copying session files..."
  # Copy session files if they exist
  if ls *.session* 1>/dev/null 2>&1; then
    scp -C *.session* "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/" || log "$RED" "Failed to copy session files"
    # Fix permissions for session files to prevent readonly database errors
    ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && chmod 666 *.session* 2>/dev/null || true"
    # Also ensure the project directory has proper permissions
    ssh "$VDS_USER@$VDS_HOST" "chmod 755 $VDS_PROJECT_PATH 2>/dev/null || true"
  else
    log "$BLUE" "No session files to copy"
  fi

  log "$BLUE" "Starting containers..."
  if ! ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose --env-file .env up --build -d"; then
    log "$RED" "Failed to start containers"
    exit 1
  fi

  log "$BLUE" "Checking health..."
  ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose ps && echo '=== Recent logs ===' && docker compose logs --since=1m tg-mcp | tail -n 20 | cat"
}

validate
deploy

elapsed=$(( $(date +%s) - start_time ))
log "$GREEN" "Deployment finished in ${elapsed}s"


