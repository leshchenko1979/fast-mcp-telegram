#!/bin/bash

set -e

# Color codes and timing functions
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# SSH multiplexing setup for faster connections
SSH_OPTS="-o ControlMaster=auto -o ControlPath=~/.ssh/master-%r@%h:%p -o ControlPersist=10m"

start_time=$(date +%s)
section_start_time=0

start_section() {
    section_start_time=$(date +%s)
    echo -e "${BLUE}┌─────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${WHITE}$1${NC}"
    echo -e "${BLUE}└─────────────────────────────────────────────────────────────────┘${NC}"
}

end_section() {
    local end_time=$(date +%s)
    local duration=$((end_time - section_start_time))
    echo -e "${GREEN}✓ Completed in ${duration}s${NC}"
    echo ""
}

log() {
  local color="$1"; shift
  local ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo -e "${color}[${ts}] $*${NC}"
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
    if [ -f .env.example ]; then
      log "$RED" ".env not found. Please copy .env.example to .env and configure it:"
      log "$RED" "  cp .env.example .env"
      log "$RED" "  # Then edit .env with your values"
    else
      log "$RED" ".env not found and .env.example not available"
    fi
    exit 1
  fi
  # Load .env safely
  export $(grep -v '^#' .env | grep -v '^$' | xargs)
  require_env VDS_USER
  require_env VDS_HOST
  require_env VDS_PROJECT_PATH
}

deploy() {
  start_section "📁 Preparing Remote Directory"
  log "$BLUE" "Creating project directory on remote server..."
  ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "mkdir -p $VDS_PROJECT_PATH"
  end_section

  start_section "💅 Code Formatting"
  log "$BLUE" "Running ruff autofix on local source code..."
  if ! command -v ruff &> /dev/null; then
    log "$RED" "ruff not found. Please install it with: pip install ruff"
    exit 1
  fi
  ruff check --fix --unsafe-fixes .
  ruff format .
  log "$GREEN" "Code formatting completed successfully"
  end_section

  start_section "📦 File Transfer"
  log "$BLUE" "Transferring project files using optimized tarball transfer..."
  # Create a temporary file list including tracked and untracked files (excluding deleted and ignored files)
  (git ls-files && git ls-files --others --exclude-standard) | sort | uniq | xargs ls -d 2>/dev/null | tar -czf - --no-xattrs --files-from=- | ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "tar -xzf - -C $VDS_PROJECT_PATH"
  scp $SSH_OPTS -C .env "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/.env"
  # Copy .env.example if it exists
  if [ -f .env.example ]; then
    scp $SSH_OPTS -C .env.example "$VDS_USER@$VDS_HOST:$VDS_PROJECT_PATH/.env.example"
  fi

  # Clean up macOS resource fork files
  ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "find $VDS_PROJECT_PATH -name '._*' -delete 2>/dev/null || true"
  end_section

  start_section "🐳 Container Deployment"
  log "$BLUE" "Building and starting MCP server containers..."
  if ! ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose --profile server --env-file .env up --build -d"; then
    log "$RED" "Failed to start containers"
    exit 1
  fi
  end_section

  start_section "🏥 Health Verification"
  log "$BLUE" "Waiting for container to be healthy..."
  ATTEMPTS=0
  MAX_ATTEMPTS=30
  until ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose ps --format json | grep -q '\"Health\":\"healthy\"'" || [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; do
      ATTEMPTS=$((ATTEMPTS + 1))
      log "$YELLOW" "Waiting for container to be healthy (attempt ${ATTEMPTS}/${MAX_ATTEMPTS})..."
      sleep 5
  done

  if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
      log "$RED" "Container failed to become healthy after ${MAX_ATTEMPTS} attempts"
      exit 1
  fi

  log "$BLUE" "Checking container status and recent logs..."
  ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && docker compose ps && echo '=== Recent logs ===' && docker compose logs --since=1m fast-mcp-telegram | tail -n 20 | cat"
  end_section

  start_section "🧹 Post-Deployment Cleanup"
  log "$BLUE" "Removing source files as per VDS deployment rules..."
  ssh $SSH_OPTS "$VDS_USER@$VDS_HOST" "cd $VDS_PROJECT_PATH && find . -type f ! -name 'docker-compose.yml' ! -name '.env' ! -name '.env.example' -delete && find . -type d -empty -delete"
  end_section
}

validate
deploy

end_time=$(date +%s)
total_duration=$((end_time - start_time))
current_time=$(date '+%Y-%m-%d %H:%M:%S')

echo -e "${CYAN}┌─────────────────────────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}│${NC} ${WHITE}🎉 Deployment completed successfully!${NC}"
echo -e "${CYAN}│${NC} ${GREEN}Total deployment time: ${total_duration}s${NC}"
echo -e "${CYAN}│${NC} ${YELLOW}Finished at: ${current_time}${NC}"
echo -e "${CYAN}└─────────────────────────────────────────────────────────────────┘${NC}"
