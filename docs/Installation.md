# Installation Guide

Get your Telegram MCP server running in minutes!

## Overview

Fast MCP Telegram runs in two modes:

| Mode | Security | Best For | Setup Method |
|------|----------|----------|--------------|
| **Local** (`stdio`) | File-based | Local MCP clients | CLI |
| **Production** (`http-auth`) | Token-based | Remote servers | Web or CLI |

---

## Local Setup (stdio)

**Step 1 — Authenticate**
```bash
uvx --from fast-mcp-telegram fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+1234567890"
```

**Step 2 — Configure your MCP client:**

Add to your `mcp.json`:
```json
{
  "mcpServers": {
    "telegram": {
      "command": "uvx",
      "args": ["fast-mcp-telegram"],
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash"
      }
    }
  }
}
```

**Step 3 — Start using it!**

Configure your MCP client to connect. See [Tools Reference](Tools-Reference.md) for available tools.

## Remote Setup (http-auth)

Deploy on a VDS with Docker Compose and Traefik — SSL is managed centrally, no per-service TLS config needed.

**Step 1 — Get the Docker Compose file**

Option A (clone):
```bash
git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
cd fast-mcp-telegram
```

Option B (download only):
```bash
curl -O https://raw.githubusercontent.com/leshchenko1979/fast-mcp-telegram/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/leshchenko1979/fast-mcp-telegram/main/.env.example
mv .env.example .env
```

**Step 2 — Configure environment**

Edit `.env` with at minimum:
```bash
API_ID=your_api_id
API_HASH=your_api_hash
DOMAIN=your-domain.com
```

**Step 3 — Add Traefik labels**

Edit your `docker-compose.yml` and add these labels to the existing `fast-mcp-telegram` service:

```yaml
services:
  fast-mcp-telegram:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.fast-mcp-telegram.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.fast-mcp-telegram.entrypoints=websecure"
      - "traefik.http.routers.fast-mcp-telegram.tls.certresolver=le"
```

The service must be on the `traefik-public` network (already configured). Traefik handles SSL via `certResolver: le`.

**Step 4 — Start the server**

```bash
docker compose up -d --pull
docker compose logs -f
```

**Step 5 — Authenticate via web interface**

See [Web Setup Interface](#web-setup-interface) for detailed instructions.

**Step 6 — Connect your MCP client**

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

**URL path auth (for clients without header support):**
```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-domain.com/v1/url_auth/YOUR_TOKEN/mcp"
    }
  }
}
```

**Health check:** `curl https://your-domain.com/health`

---

## Web Setup Interface

The web setup interface manages Telegram sessions directly from your browser. Access it at `https://your-domain.com/setup` when running in `http-auth` mode.

### Session Management

Sessions are stored in `~/.config/fast-mcp-telegram/`:
- **Local:** `{SESSION_NAME}.session` (default: `telegram.session`)
- **Production:** `{bearer_token}.session` (auto-managed per user)

Use different Telegram accounts for personal, work, or testing:

```bash
# Create sessions for different accounts
SESSION_NAME=personal fast-mcp-telegram-setup \
  --api-id="xxx" --api-hash="yyy" --phone-number="+111"

SESSION_NAME=work fast-mcp-telegram-setup \
  --api-id="xxx" --api-hash="yyy" --phone-number="+222"
```

**Configure in MCP client:**
```json
{
  "mcpServers": {
    "telegram-personal": {
      "command": "uvx",
      "args": ["fast-mcp-telegram"],
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash",
        "SESSION_NAME": "personal"
      }
    },
    "telegram-work": {
      "command": "uvx",
      "args": ["fast-mcp-telegram"],
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash",
        "SESSION_NAME": "work"
      }
    }
  }
}
```

---

## More Resources

- **[Operations Guide](Operations.md)** - Monitoring, debugging, health checks
- **[Tools Reference](Tools-Reference.md)** - Available MCP tools and usage
- **[SECURITY.md](../SECURITY.md)** - Security best practices
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Development setup for contributors

---

**Need help?** Open an [issue](https://github.com/leshchenko1979/fast-mcp-telegram/issues) on GitHub!