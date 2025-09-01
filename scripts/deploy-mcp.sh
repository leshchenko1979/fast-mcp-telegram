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

  # Ensure sessions directory exists locally
  mkdir -p sessions

  # Backup all session files and directories if they exist
  SESSION_BACKUP_DIR="/tmp/mcp_session_backup_$(date +%s)"
  ssh "$VDS_USER@$VDS_HOST" "mkdir -p $SESSION_BACKUP_DIR"

  # Find and backup all session-related files and directories
  SESSION_ITEMS=$(ssh "$VDS_USER@$VDS_HOST" "find $VDS_PROJECT_PATH/sessions -name '*.session*' -o -name '*session*' 2>/dev/null || true")
  if [ -n "$SESSION_ITEMS" ]; then
    log "$BLUE" "Backing up existing session files and directories..."
    ssh "$VDS_USER@$VDS_HOST" "echo '$SESSION_ITEMS' | while read -r item; do if [ -e \"\$item\" ]; then cp -r \"\$item\" $SESSION_BACKUP_DIR/ 2>/dev/null || true; fi; done"
    SESSION_COUNT=$(ssh "$VDS_USER@$VDS_HOST" "ls -1 $SESSION_BACKUP_DIR 2>/dev/null | wc -l")
    log "$GREEN" "Backed up $SESSION_COUNT session file(s)"
  else
    log "$BLUE" "No existing session files found to backup"
  fi

  ssh "$VDS_USER@$VDS_HOST" "rm -rf $VDS_PROJECT_PATH && mkdir -p $VDS_PROJECT_PATH"

  log "$BLUE" "Transferring project files..."
  # Create a temporary file list excluding deleted files (excluding sessions directory)
  git ls-files | grep -v '^sessions/' | xargs ls -d 2>/dev/null | tar -czf - --files-from=- | ssh "$VDS_USER@$VDS_HOST" "tar -xzf - -C $VDS_PROJECT_PATH"
  scp -C .env "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/.env"

  # Create sessions directory on remote
  ssh "$VDS_USER@$VDS_HOST" "mkdir -p $VDS_PROJECT_PATH/sessions"

  # Clean up macOS resource fork files
  ssh "$VDS_USER@$VDS_HOST" "find $VDS_PROJECT_PATH -name '._*' -delete 2>/dev/null || true"

  # Fix session file permissions for container access
  ssh "$VDS_USER@$VDS_HOST" "chown -R 1000:1000 $VDS_PROJECT_PATH/sessions 2>/dev/null || true && chmod 775 $VDS_PROJECT_PATH/sessions 2>/dev/null || true && chmod 664 $VDS_PROJECT_PATH/sessions/*.session 2>/dev/null || true"

  # Copy local session files to remote if any exist
  if [ "$(ls -A sessions/ 2>/dev/null)" ]; then
    log "$BLUE" "Copying local session files to remote..."
    scp -C sessions/* "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/sessions/" 2>/dev/null || true
    LOCAL_COUNT=$(ls -1 sessions/ | wc -l)
    log "$GREEN" "Copied $LOCAL_COUNT local session file(s)"
  fi

  # Restore backed up session files if any exist
  if ssh "$VDS_USER@$VDS_HOST" "[ -d $SESSION_BACKUP_DIR ] && [ \"\$(ls -A $SESSION_BACKUP_DIR 2>/dev/null)\" ]"; then
    log "$BLUE" "Restoring backed up session files..."
    ssh "$VDS_USER@$VDS_HOST" "cp -r $SESSION_BACKUP_DIR/* $VDS_PROJECT_PATH/sessions/ 2>/dev/null || true && chown -R 1000:1000 $VDS_PROJECT_PATH/sessions"
    ssh "$VDS_USER@$VDS_HOST" "rm -rf $SESSION_BACKUP_DIR"
    RESTORED_COUNT=$(ssh "$VDS_USER@$VDS_HOST" "ls -1 $VDS_PROJECT_PATH/sessions/ 2>/dev/null | wc -l")
    log "$GREEN" "Restored $RESTORED_COUNT session file(s) total"
  fi

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


