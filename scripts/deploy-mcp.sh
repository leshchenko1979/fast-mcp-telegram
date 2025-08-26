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
  git ls-files | tar -czf - --files-from=- | ssh "$VDS_USER@$VDS_HOST" "tar -xzf - -C $VDS_PROJECT_PATH"
  scp -C .env "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/.env"
  
  log "$BLUE" "Copying session files..."
  scp -C *.session* "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/" 2>/dev/null || log "$BLUE" "No session files to copy"

  log "$BLUE" "Starting containers..."
  ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose --env-file .env up --build -d"

  log "$BLUE" "Checking health..."
  ssh "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose ps && docker compose logs --since=1m tg-mcp | tail -n 100 | cat"
}

validate
deploy

elapsed=$(( $(date +%s) - start_time ))
log "$GREEN" "Deployment finished in ${elapsed}s"


