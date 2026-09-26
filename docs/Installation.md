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

**Step 1 — Authenticate (choose one)**

**Option A: QR code (recommended — no phone, no OTP)**
```bash
uvx --from fast-mcp-telegram fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash"
```
A QR code appears in your terminal. Open Telegram mobile → Settings → Devices → Link Desktop Device → scan. If the account has 2FA, you'll be prompted for the password. Works over SSH.

**Option B: Phone number**
```bash
uvx --from fast-mcp-telegram fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+1234567890"
```

**Option C: Bot token (no phone, no OTP)**
Create a bot via [@BotFather](https://t.me/BotFather), then:
```bash
uvx --from fast-mcp-telegram fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --bot-api-token="1234567890:ABCdef..."
```

Or skip the setup step entirely — just add `BOT_API_TOKEN` to your env and the server auto-authenticates on startup when no session file exists.

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

### Deploy script (VDS)

For operators with SSH access to a production host, [`scripts/deploy.sh`](../scripts/deploy.sh) rsyncs the working tree, builds a version-tagged Docker image on the remote, runs `docker compose up --wait`, and rolls back to the previous tag if the health check fails within 90 seconds.

```bash
./scripts/deploy.sh              # uses git describe for the image tag
./scripts/deploy.sh v0.42.0      # explicit version tag
```

Defaults: remote host `apps` (from `~/.ssh/config`), remote dir `/root/fast-mcp-telegram`. Override with `REMOTE_HOST` and `REMOTE_DIR`. Requires Docker on the remote and a committed tree (rsync excludes `.env` and session files).

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

> **Reverse proxy:** HTTP mode sets FastMCP `allowed_hosts=["*"]` so Traefik or similar proxies can forward any `Host` header; restrict at the proxy if needed.

**MCP discovery (HTTP modes):** `GET /.well-known/mcp/server-card.json` returns server metadata and the registered tool list (built from the live FastMCP registry). Useful for Smithery and similar installers; does not require an active Telegram session.

### HTTP auth: two deployment patterns

Remote `http-auth` supports two different setups. Do not confuse them when reading docs or choosing env vars.

| Pattern | Who | MCP wiring | `PREFIX_MCP_TOOLS_WITH_ACCOUNT` |
|---------|-----|------------|--------------------------------|
| **Multi-user server** | Many users on one hosted server | Each user: **one** MCP connection, **one** Bearer token → **one** Telegram account | **Off** (default). Each connection already sees only that account's tools. |
| **One agent, multiple accounts** | One operator / one agent session | **Several** MCP entries to the **same** server URL, **different** tokens (see [below](#multi-account-mcp-tool-prefix)) | **On** when the client merges tool lists and names collide (`send_message` × N). |

**Multi-user server** is the usual production model: authenticate at [web setup](#web-setup-interface), use your token in a single MCP client entry. **Do not enable** `PREFIX_MCP_TOOLS_WITH_ACCOUNT` for that case.

**One agent, multiple accounts** is for a single agent that must talk to several Telegram identities via one server in one session — enable the prefix only then.

---

## One agent, multiple accounts (tool name prefix)

This section applies only to **one agent, multiple accounts** (second row above), not to ordinary multi-user hosting.

When one agent's MCP config lists **multiple connections** to the same server URL (each with its own Bearer token from [web setup](#web-setup-interface)), tool names would otherwise be identical across connections (`send_message`, `find_chats`, …). Enable per-session prefixes so each connection exposes distinct names (e.g. `alice_send_message` vs `bob_send_message`).

**Enable in `.env` or docker-compose:**

```bash
PREFIX_MCP_TOOLS_WITH_ACCOUNT=true
```

**How it works:**

1. In **one agent's** MCP config, add multiple server entries pointing at the same URL — one entry per Telegram account, each with its own Bearer token.
2. On `tools/list`, the server prefixes each tool name with that connection's account label.
3. Prefix label: Telegram **@username** when set, otherwise **numeric user ID** (e.g. `123456789_send_message`). Setting a @username is recommended for readable tool names in the agent.
4. On `call_tool`, use the prefixed name that matches the connection's token.

**Trade-off:** The agent may see `N × num_tools` entries (typically manageable for 2–3 accounts). Default is off — single-connection and multi-user-server deployments are unchanged.

---

## Web Setup Interface

The web setup interface manages Telegram sessions directly from your browser. Access it at `https://your-domain.com/setup` when running in `http-auth` mode.

### Create or Manage Sessions

**Create New Session:** The setup page shows a **QR code by default**. Open Telegram mobile → Settings → Devices → Scan QR code. Once scanned, your bearer token appears immediately — no phone typing, no verification code, no 2FA input needed.

**Alternative — Phone (no mobile app):** Click **"Create New Session"**, enter your phone number (with country code, e.g., `+1234567890`), then enter the verification code Telegram sends. If 2FA is enabled, enter your password.

**Reauthorize Existing Session:** Enter your bearer token, then scan the QR or confirm your phone number. Your session refreshes with the same token.

**Delete Session:** Click **"Delete Session"**, enter your bearer token, then confirm deletion (cannot be undone).

---

## Session ACL (http-auth)

Optional **per-principal limits** on shared `http-auth` hosts: choose which chats each principal may use and whether it may send messages or call raw Telegram APIs. Clients still authenticate with Bearer tokens. See [SECURITY.md](../SECURITY.md#opt-in-session-acl-http-auth) for terminology (principal vs Bearer).

**Scope:** `ACL_ENABLED=true` applies only in **`http-auth`** mode. Stdio and `http-no-auth` are unchanged.

**Enable:**

1. Set `ACL_ENABLED=true` (and optionally `ACL_CONFIG_PATH`) in the server environment.
2. Create the ACL file — default `{session_directory}/acl.yaml`, or the path from `ACL_CONFIG_PATH`. Start from [acl.yaml.example](../acl.yaml.example).
3. List **only** principals you want to restrict under `principals:`. **Unlisted principals keep full tool access** unless `ACL_DENY_UNLISTED_PRINCIPALS=true`.
4. Restart or redeploy. The server **refuses to start** if ACL is enabled but the file is missing, invalid, or still uses legacy `tokens:` (`read_only` requires a non-empty `chats` list).

**Settings (summary):**

| Setting | Effect |
| --- | --- |
| `chats` | Chat ids, `@username`, or `me` this principal may use |
| Empty or omitted `chats` on a **listed** principal | Chat tools return an error (not an empty result list) |
| `read_only: true` | Blocks send, edit, `invoke_mtproto`, and `/mtproto-api/*` |
| `allow_global_search: false` | Blocks `search_messages_globally` and raw MTProto |
| `allow_mtproto: false` | Default for listed principals; blocks raw MTProto unless `true` with `read_only: false` and `allow_global_search: true` |
| `ACL_DENY_UNLISTED_PRINCIPALS=true` | Any principal not listed under `principals:` is denied |

**Operator runbook:** [SECURITY.md](../SECURITY.md#opt-in-session-acl-http-auth) · **Design:** [ADR 0001](adr/0001-agent-scoped-session-acl.md) · **Local testing:** [CONTRIBUTING.md](../CONTRIBUTING.md#acl-development-and-testing-not-via-cursor-mcp)

---

## S3 Session Storage (optional)

For **ephemeral hosted deployments** (Smithery Hosted, Fly.io, Railway) where containers have no persistent volumes. Session files are stored in S3-compatible object storage — downloaded on connect, uploaded on disconnect.

When disabled (`S3_SESSION_STORAGE` empty), sessions are local files — no change from current behavior.

### Setup

1. Create an S3 bucket (AWS S3, MinIO, Cloudflare R2, Tigris, Hetzner, etc.)
2. Set environment variables:

```bash
S3_SESSION_STORAGE=true
AWS_S3_BUCKET=fast-mcp-telegram-sessions
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
# Optional: custom endpoint for non-AWS S3
# AWS_ENDPOINT_URL=http://minio:9000
# AWS_REGION=us-east-1
```

3. Install with S3 extras: `uv pip install fast-mcp-telegram[s3]`

### Platform quick-start

| Platform | S3 service | How |
|----------|-----------|-----|
| **Fly.io** | Tigris | `fly storage create` — auto-sets `AWS_*` vars |
| **Railway** | S3 add-on | One-click — auto-sets `AWS_*` vars |
| **Cloudflare** | R2 | Free egress. Set `AWS_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com` |
| **AWS** | S3 | IAM role or `AWS_*` vars |
| **Self-hosted** | MinIO | Docker sidecar, `AWS_ENDPOINT_URL=http://minio:9000` |

### How it works

- **On first connect:** downloads `{token}.session` from S3 to local disk, verifies integrity
- **On eviction/disconnect:** WAL-checkpoints the SQLite session file, uploads to S3
- **On setup:** after QR/phone auth, session is uploaded to S3 immediately
- **On setup_delete:** session is evicted (flush + upload), then deleted from S3
- **Fallback:** if S3 is unavailable, falls back to local file mode

### ADR and design doc

Architecture decisions: [ADR 0009](adr/0009-s3-session-storage.md). Implementation details: [design doc](design/s3-session-storage-design.md).

---

## Configuration Reference

### Environment Variables

```bash
# Required (pick one auth method)
# — User account (phone + OTP):
API_ID=your_api_id
API_HASH=your_api_hash
# — Bot account (no phone, no OTP):
# BOT_API_TOKEN=1234567890:ABCdef...

# Optional
SERVER_MODE=http-auth             # stdio (default) or http-auth for remote
HOST=127.0.0.1                    # Bind address (use 0.0.0.0 for production HTTP behind a proxy)
PORT=8000                          # Server port (http-auth mode)
LOG_LEVEL=INFO                    # Logging verbosity
SESSION_NAME=telegram             # Session file name (stdio mode only)
SESSION_DIR=~/.config/fast-mcp-telegram  # Custom session directory
MTPROTO_PROXY=tg://proxy?server=your-proxy.com&port=443&secret=your-secret  # Firewall proxy
TELEGRAM_INACTIVE_SESSION_DAYS=30 # Auto-delete .session files unused >N days (0 = disable)

# Session ACL (http-auth only) — see #session-acl-http-auth
ACL_ENABLED=false                  # Opt-in per-principal MCP limits (http-auth)
ACL_CONFIG_PATH=                   # Override default {session_directory}/acl.yaml
ACL_DENY_UNLISTED_PRINCIPALS=false # Deny principals omitted from principals: map
```

**Tip:** The CLI setup automatically loads `.env` files from your current directory.

### MTProto Proxy

For connections behind a firewall. Supported formats:
- `tg://proxy?server=&port=&secret=` (URL)
- `host:port:secret` (simple)
- `ee` or `7` prefix for fake TLS (auto-detected)

> **Note:** Fake TLS (EE prefix) support requires the `TelethonFakeTLS` package: `pip install TelethonFakeTLS`. Without it, Fake TLS proxies fall back to standard TCP.

### Multiple Accounts

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

- **[Tools Reference](docs/Tools-Reference.md)** - Available MCP tools and usage
- **[SECURITY.md](../SECURITY.md)** - Security best practices
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Development setup for contributors

---

**Need help?** Open an [issue](https://github.com/leshchenko1979/fast-mcp-telegram/issues) on GitHub!