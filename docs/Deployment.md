# 🐳 Deployment Guide

## Docker Deployment (Production)

### Prerequisites

- **Docker & Docker Compose** installed
- **Telegram API credentials** ([get them here](https://my.telegram.org/auth))
- **Domain name** (for Traefik reverse proxy setup)

### Environment Setup

Create a `.env` file in your project directory:

```bash
# Telegram API Credentials
API_ID=your_api_id
API_HASH=your_api_hash

# Domain Configuration (for remote docker deployment)
DOMAIN=your-domain.com

# Server Configuration
SERVER_MODE=http-auth       # stdio, http-no-auth, or http-auth
HOST=0.0.0.0                # Bind address (auto-adjusts based on server mode)
PORT=8000                   # Service port

# Optional: Session Management
MAX_ACTIVE_SESSIONS=10      # LRU cache limit for concurrent sessions

# Optional: Logging
LOG_LEVEL=INFO
```

**Note:** Phone numbers are specified during setup via CLI options rather than environment variables for better security and flexibility.

### Telegram Authentication & Token Generation

**Important:** The setup process creates an authenticated Telegram session file and generates a Bearer token for HTTP authentication.

```bash
# 1. Run authentication setup with your phone number
docker compose --profile setup run --rm setup --phone-number="+1234567890"

# Alternative: Use all CLI options (bypasses .env file reading)
docker compose --profile setup run --rm setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+1234567890"

# 2. Note the Bearer token output after successful setup
# 🔑 Bearer Token: AbCdEfGh123456789KLmnOpQr...

# 3. Start the main MCP server (if not already running)
docker compose --profile server up -d
```

**Setup Options:**
- **Default**: Use `--phone-number` with .env file for API credentials
- **Full CLI**: Specify all credentials via command line options
- **Additional options**: `--overwrite`, `--session-name` available

**🌐 Browser alternative:** After the server is reachable, open `https://<DOMAIN>/setup` to authenticate via web and download `mcp.json` (no CLI needed). For local testing, use `http://localhost:8000/setup`.

**Profile System:**
- `--profile setup`: Runs only the Telegram authentication setup
- `--profile server`: Runs only the MCP server (after authentication)
- No profile: No services start (prevents accidental startup)

**Authentication Output:**
- **Session file**: `~/.config/fast-mcp-telegram/{token}.session`
- **Bearer token**: Unique token for HTTP authentication
- **Multi-user support**: Each setup creates isolated session

### Domain Configuration (Optional)

The default domain is `your-domain.com`. To use your own domain:

1. **Set up DNS**: Point your domain to your server
2. **Configure environment**: Add `DOMAIN=your-domain.com` to your `.env` file
3. **Traefik network**: Ensure `traefik-public` network exists on your host

**Example:**
```bash
# In your .env file
DOMAIN=my-telegram-bot.example.com
```

### Local Docker Deployment

```bash
# After completing setup, start the MCP server (if not already running)
docker compose --profile server up --build -d

# Check logs
docker compose logs -f fast-mcp-telegram

# Check health
docker compose ps
```

**Note:** Run setup with `docker compose --profile setup run --rm setup --phone-number="+1234567890"` to authenticate and generate a Bearer token. No server shutdown or restart required.

The service will be available at `http://localhost:8000` (internal) and through Traefik if configured.

### Remote Server Deployment

For production deployment on a remote server:

```bash
# Set up environment variables for remote deployment
export VDS_USER=your_server_user
export VDS_HOST=your.server.com
export VDS_PROJECT_PATH=/path/to/deployment

# Run the deployment script
./scripts/deploy-mcp.sh
```

**Post-deployment setup:**
1. SSH to your server and run the Telegram authentication setup:
   ```bash
   ssh your_server_user@your.server.com
   cd /path/to/deployment
   docker compose --profile setup run --rm setup --phone-number="+1234567890"
   ```
2. After setup completes, start the MCP server (if not already running):
   ```bash
   docker compose --profile server up -d
   ```

The deployment script will:
- Transfer project files to your server
- Copy environment file
- Build the Docker containers (but won't start services automatically)

### Configure Your MCP Client

**For HTTP_AUTH mode (production with Bearer token):**

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-domain.com",
      "headers": {
        "Authorization": "Bearer AbCdEfGh123456789KLmnOpQr..."
      }
    }
  }
}
```

**For HTTP_NO_AUTH mode (development HTTP server):**

```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8000"
    }
  }
}
```

**⚠️ Important:** Replace `AbCdEfGh123456789KLmnOpQr...` with your actual Bearer token from the setup process.

### Verify Deployment

```bash
# Check container status
docker compose ps

# View logs
docker compose logs fast-mcp-telegram

# Test health endpoint (includes session statistics)
curl -s https://your-domain.com/health
```

## Environment Variables Reference

| Variable | Description | Default | Mode |
|----------|-------------|---------|------|
| `SERVER_MODE` | Server mode (stdio, http-no-auth, http-auth) | `stdio` | All |
| `HOST` | Bind address | Auto-adjusts based on mode | HTTP modes |
| `PORT` | Service port | `8000` | HTTP modes |
| `DOMAIN` | Domain for Traefik routing and web setup | `your-domain.com` | HTTP modes |
| `API_ID` | Telegram API ID | Required | Setup |
| `API_HASH` | Telegram API hash | Required | Setup |
| `MAX_ACTIVE_SESSIONS` | LRU cache limit for concurrent sessions | `10` | All |
| `LOG_LEVEL` | Logging level | `INFO` | All |

## Docker Compose Configuration

The `docker-compose.yml` automatically sets the server to `http-auth` mode for production deployment with Bearer token authentication.

## Session Management

### Session Persistence
- **Zero-Downtime Deployment**: Session files preserved across deployments
- **Automatic Permission Management**: Container user access automatically configured
- **Cross-Platform Compatibility**: Handles macOS, Linux, and Windows deployment scenarios
- **Health Monitoring**: Comprehensive container health checks and logging
- **Security Hardened**: Session files excluded from version control, proper file permissions

### Session Files
- **Location**: `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Format**: `{token}.session` for multi-user isolation
- **Backup/Restore**: Automatic backup/restore across deployments
- **Permission Management**: Automatic chown/chmod for container user access (1000:1000)

## Monitoring and Health Checks

### Health Endpoint
```bash
# Check server health and session statistics
curl -s https://your-domain.com/health
```

**Response includes:**
- Server status
- Active session count and max limit
- Count of session files on disk
- Setup session count (web setup flow)
- Per-session statistics (token prefix, hours since access, connection status, last access)

### Container Health Checks
```bash
# Check container status
docker compose ps

# View real-time logs
docker compose logs -f fast-mcp-telegram

# Check container health
docker inspect $(docker compose ps -q fast-mcp-telegram) | jq '.[0].State.Health'
```

## Troubleshooting

### Common Deployment Issues

**Container won't start:**
- Check environment variables are set correctly
- Verify Docker and Docker Compose are installed
- Check logs: `docker compose logs fast-mcp-telegram`

**Authentication failures:**
- Verify API credentials in `.env` file
- Check phone number format (include country code)
- Try running setup again with `--overwrite` flag

**Session permission errors:**
- Deployment script automatically fixes permissions
- Manual fix: `chown -R 1000:1000 ~/.config/fast-mcp-telegram/`

**Domain/Traefik issues:**
- Verify DNS points to your server
- Check Traefik network exists: `docker network ls | grep traefik`
- Verify SSL certificates: `docker compose logs traefik`

### Getting Help

- Check the [Operations Guide](Operations.md) for detailed monitoring
- Review [SECURITY.md](../SECURITY.md) for security considerations
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup
- Open an [issue](https://github.com/leshchenko1979/fast-mcp-telegram/issues) for bugs
