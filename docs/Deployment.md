# Deployment Guide

## Automatic Deployment via GitHub Actions

This project uses GitHub Actions for automatic builds and deployments. When you push to `main`, the pipeline:

1. Runs tests
2. Builds a Docker image and pushes it to GitHub Container Registry (GHCR)
3. Deploys to your VDS server automatically

### Prerequisites

- GitHub repository forked from this project
- VDS server with SSH access
- Telegram API credentials

### Setup

**1. Configure GitHub Secrets:**

In your GitHub repository, go to Settings > Secrets and add:

| Secret | Description |
|--------|-------------|
| `SSH_HOST` | Your VDS server IP or hostname |
| `SSH_USER` | SSH username (e.g., `root`) |
| `SSH_PORT` | SSH port (default: 22) |
| `SSH_PRIVATE_KEY` | Private key for SSH authentication |
| `GHCR_PULL_TOKEN` | GitHub PAT with `packages:read` scope (optional, for private repos) |
| `GHCR_PULL_USER` | GitHub username for GHCR login (optional) |

**2. Configure your `.env` file:**

```bash
# Telegram API Credentials
API_ID=your_api_id
API_HASH=your_api_hash

# Domain Configuration
DOMAIN=your-domain.com

# Server Configuration
SERVER_MODE=http-auth
HOST=0.0.0.0
PORT=8000
```

**3. Push to `main`:**

```bash
git push origin main
```

The deployment will start automatically. Watch the Actions tab in your GitHub repository for progress.

### Manual Deployment

For manual deployment (without GitHub Actions), use the sync script:

```bash
# Configure .env with SSH connection details
export SSH_HOST=your.server.com
export SSH_USER=root

# Sync compose file and run deployment
./scripts/sync-remote-config.sh
```

## Local Docker Deployment

For local testing or development:

```bash
# Configure .env
cp .env.example .env
# Edit .env with your API credentials

# Build and start
docker compose up --build -d

# Check logs
docker compose logs -f
```

## Telegram Authentication

After the server is running, authenticate via the web interface:

1. Open `http://localhost:8000/setup` (local) or `https://your-domain.com/setup`
2. Enter your phone number
3. Enter the verification code from Telegram
4. Download your `mcp.json` configuration

## Session Management

Sessions are stored in a Docker named volume (`telegram-sessions`) and persist across deployments.

```bash
# Backup sessions
docker compose exec fast-mcp-telegram tar czf - -C /home/appuser/.config/fast-mcp-telegram . > sessions-backup.tar.gz

# Restore sessions
cat sessions-backup.tar.gz | docker compose exec -T fast-mcp-telegram tar xzf - -C /home/appuser/.config/fast-mcp-telegram
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_ID` | Telegram API ID | Required |
| `API_HASH` | Telegram API hash | Required |
| `DOMAIN` | Public host for web setup and attachment URLs | `your-domain.com` |
| `SERVER_MODE` | Server mode (`stdio`, `http-no-auth`, `http-auth`) | `http-auth` |
| `PORT` | Service port | `8000` |
| `GHCR_IMAGE` | Docker image to use | `ghcr.io/{owner}/fast-mcp-telegram` |
| `IMAGE_TAG` | Docker image tag | `main` |

## Verify Deployment

```bash
# Check container status
docker compose ps

# Test health endpoint
curl http://localhost:8000/health

# View logs
docker compose logs fast-mcp-telegram
```

## Troubleshooting

**Deployment fails:**
- Verify GitHub secrets are configured correctly
- Check Actions tab for error details
- Ensure SSH key is authorized on VDS server

**Container won't start:**
- Verify `.env` has required variables
- Check logs: `docker compose logs fast-mcp-telegram`
- Ensure `traefik-public` network exists: `docker network ls`

**Authentication issues:**
- Clear browser cache and try again
- Use the `/setup` endpoint to re-authenticate
- Check server logs for verification code issues