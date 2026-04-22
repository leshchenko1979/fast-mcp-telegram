# Remote Server Setup

Deploy your own MCP server on a VDS with Docker Compose and Traefik reverse proxy. Traefik handles SSL — no per-service TLS configuration needed.

## Prerequisites

- Docker and Docker Compose installed on your VDS
- Traefik already running on the server with the `traefik-public` network
- Domain pointed to your server's IP
- Telegram API credentials (`API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org/auth))

## Step 1 — Configure Environment

Create a `.env` file in the project directory with at minimum:

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

## Step 2 — Add Traefik Labels

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

## Step 3 — Start the Server

```bash
# Pull the image and start the container
docker compose up -d --pull

# Check logs
docker compose logs -f
```

## Step 4 — Authenticate via Web Interface

Open `https://your-domain.com/setup` in your browser.

1. Click **Create New Session**
2. Enter your phone number (with country code, e.g. `+1234567890`)
3. Enter the verification code from Telegram
4. Download the `mcp.json` file — this contains your server URL and Bearer token

## Step 5 — Connect Your MCP Client

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

Expected response: `{"status":"ok"}`

## Troubleshooting

**Container won't start:**
- Verify `.env` has `API_ID` and `API_HASH`
- Check logs: `docker compose logs fast-mcp-telegram`
- Ensure `traefik-public` network exists: `docker network ls`

**Auth fails:**
- Verify token is correct in your MCP client config
- For URL path auth, ensure the token appears after `/v1/url_auth/` and before `/mcp`
- Clear browser cache and re-authenticate at `/setup` if needed

**Traefik routing issues:**
- Verify domain DNS points to your server
- Check Traefik logs for routing errors
- Ensure the `traefik-public` network is shared between Traefik and the container