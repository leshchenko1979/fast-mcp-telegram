# Remote Server Setup

Deploy your own MCP server on a VDS with Docker Compose and Traefik reverse proxy. Traefik handles SSL — no per-service TLS configuration needed.

## Prerequisites

- Docker and Docker Compose installed on your VDS
- Traefik already running on the server with the `traefik-public` network
- Domain pointed to your server's IP
- Telegram API credentials (`API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org/auth))

## Step 1 — Get the Docker Compose File

**Option A — Clone the repository:**
```bash
git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
cd fast-mcp-telegram
```

**Option B — Download compose file only:**
```bash
curl -O https://raw.githubusercontent.com/leshchenko1979/fast-mcp-telegram/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/leshchenko1979/fast-mcp-telegram/main/.env.example
mv .env.example .env
```

## Step 2 — Configure Environment

Edit the `.env` file:

```bash
# Required
API_ID=your_api_id
API_HASH=your_api_hash
DOMAIN=your-domain.com

# Optional — defaults work for the pre-built image
SERVER_MODE=http-auth
HOST=0.0.0.0
PORT=8000
```

## Step 3 — Add Traefik Labels

The Docker Compose file does not include Traefik labels. Add them to the `fast-mcp-telegram` service in your docker-compose.yml:

```yaml
services:
  fast-mcp-telegram:
    # ... existing config ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.fast-mcp-telegram.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.fast-mcp-telegram.entrypoints=websecure"
      - "traefik.http.routers.fast-mcp-telegram.tls.certresolver=le"
```

The service must be on the `traefik-public` network (already configured). Traefik handles SSL via certResolver: le — no per-service TLS config needed.

## Step 4 — Start the Server

```bash
# Pull the image and start the container
docker compose up -d --pull

# Check logs
docker compose logs -f
```

## Step 5 — Authenticate via Web Interface

Open `https://your-domain.com/setup` in your browser. Three options are available:

- **Create New Session** — add a new Telegram account
- **Reauthorize Existing Session** — refresh an expired session using its bearer token
- **Delete Session** — remove a session by bearer token

**To create a new session:**
1. Click **Create New Session**
2. Enter your phone number (with country code, e.g. `+1234567890`)
3. Enter the verification code from Telegram
4. If 2FA is enabled, enter your password when asked
5. Download the `mcp.json` file — this contains your server URL and bearer token

**To reauthorize an existing session:**
1. Click **Reauthorize Existing Session**
2. Enter your bearer token (from your existing `mcp.json`)
3. Enter your phone number
4. Enter the verification code from Telegram
5. If 2FA is enabled, enter your password when asked

## Step 6 — Connect Your MCP Client

Configure your MCP client to use the remote server. Two authentication methods are supported:

**Header auth (standard):**
```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-domain.com/v1/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

**URL path auth (for clients that cannot set custom headers):**
```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-domain.com/v1/url_auth/YOUR_TOKEN/mcp"
    }
  }
}
```

Replace `YOUR_TOKEN` with the token from your `mcp.json` file.

## Health Check

```bash
curl https://your-domain.com/health
```

Example response (new server with one session):
```json
{
  "status": "healthy",
  "active_sessions": 1,
  "max_sessions": 10,
  "session_files": 1,
  "setup_sessions": 0
}
```

## Troubleshooting

**Container won't start:**
- `.env` must have `API_ID` and `API_HASH`
- Run `docker compose config` to validate the compose file
- Check logs: `docker compose logs fast-mcp-telegram`

**502 Bad Gateway:**
- Traefik is not routing to the container — verify labels and that container is on `traefik-public` network (`docker network inspect traefik-public`)
- Check Traefik logs

**Session auth fails:**
- Use token from `mcp.json` (not your Telegram password)
- For URL path auth, token goes between `/v1/url_auth/` and `/mcp`
- Go to `/setup` → **Manage Sessions** to reauthenticate if token expired