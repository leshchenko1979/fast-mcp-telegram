<img alt="Hero image" src="https://github.com/user-attachments/assets/635236f6-b776-41c7-b6e5-0dd14638ecc1" />

**Telegram MCP Server** — Model Context Protocol (MCP) gateway for Telegram. 8 context-efficient tools, multi-tenant, MTProto bridge.

## Try the Demo

1. Open https://tg-mcp.l1979.ru/setup
2. **Scan the QR code** from Telegram mobile (Settings → Devices → Scan QR) — no phone typing, no OTP, no 2FA. Or enter your phone number as fallback.
3. Copy your Bearer token from the success page

Then choose your path:

**MCP Client (AI assistants)**
- From the [setup page](/setup), download the `mcp.json` file
- Add the server to your AI client and ask: "send hello to my saved messages in telegram"

**Direct API (curl)**
- Run the command below (replace TOKEN with yours):
```bash
curl -X POST "https://tg-mcp.l1979.ru/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "message": "Hello!"}}'
```

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://github.com/leshchenko1979/fast-mcp-telegram)
[![Health Status](https://gatus.l1979.ru/api/v1/endpoints/apps_fast-mcp-telegram/uptimes/30d/badge.svg)](https://gatus.l1979.ru/endpoints/apps_fast-mcp-telegram)
[![Glama Score](https://glama.ai/mcp/servers/leshchenko1979/fast-mcp-telegram/badges/score.svg)](https://glama.ai/mcp/servers/leshchenko1979/fast-mcp-telegram)

## How It Works

This server sits between your AI agent and Telegram's API:

```
Your agent → MCP/HTTP → this server → MTProto → Telegram
```

**What it does:** Authenticates you with Telegram (QR or phone/bot token), exposes 8 AI-friendly tools instead of 80+ micro-APIs, and bridges raw MTProto for power users. Multi-tenant — one server, many users, isolated sessions.

## Features


| Feature                                                                                             | Description                                                                                                    |
| --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| :building_construction: **[Dual Transport](docs/Installation.md#overview)**                         | Stdio for local MCP clients, HTTP for remote deploys (`http-auth` production, optional `http-no-auth` for dev) |
| :closed_lock_with_key: **[Multi-User Authentication](docs/Installation.md#remote-setup-http-auth)** | Shared `http-auth` server: one Bearer token per user, one Telegram account per MCP connection. **QR login** for instant auth — no phone/OTP/2FA. |
| :dart: **[AI-Optimized](docs/Tools-Reference.md#overview)**                                         | 8 consolidated tools vs 80+ micro-tools — context-efficient design, LLM-friendly API, MCP ToolAnnotations     |
| :globe_with_meridians: **[HTTP-MTProto Bridge](docs/MTProto-Bridge.md#key-benefits)**               | Direct curl access to any Telegram API method with entity resolution and safety guardrails                     |
| :shield: **[Session ACL](docs/Installation.md#session-acl-http-auth)** | Opt-in per-principal limits on `http-auth` (`ACL_ENABLED`) — chat lanes, `read_only`, `blocked_peers`, `allow_mtproto`, `ACL_DENY_UNLISTED_PRINCIPALS`; see [SECURITY.md](SECURITY.md#opt-in-session-acl-http-auth) |
| :tv: **[QR & Web Setup](docs/Installation.md#web-setup-interface)**                              | Scan QR from Telegram mobile for instant auth (no phone/OTP/2FA) or use phone/code/2FA fallback — live at `/setup` |
| :label: **[One Agent, Multiple Accounts](docs/Installation.md#multi-account-mcp-tool-prefix)**     | Optional `PREFIX_MCP_TOOLS_WITH_ACCOUNT` — when **one** agent uses several MCP connections (same server, different tokens), prefixes tool names so they do not collide; not needed for standard multi-user hosting |
| :rocket: **[MTProto Proxy Support](docs/Installation.md#mtproto-proxy)**                            | Connect via MTProto proxy with automatic Fake TLS (EE prefix) and standard proxy detection                     |
| :card_file_box: **[Unified Session Management](docs/Installation.md#configuration-reference)**      | Single configuration system for setup and server; per-token session files on shared multi-user hosts          |
| :cloud: **[S3 Session Storage](docs/Installation.md#s3-session-storage-optional)**                  | Store sessions in S3-compatible object storage for ephemeral hosted deployments (Smithery, Fly.io, Railway)  |
| :mag_right: **[Intelligent Search](docs/Search-Guidelines.md#what-works)**                          | Global & per-chat message search with multi-query support and intelligent deduplication                        |
| :mag: **[Unified Message API](docs/Tools-Reference.md#2-read)**                                     | Single `get_messages` tool for search, browse, read by IDs, and replies - 5 modes in one                       |
| :speech_balloon: **[Universal Replies](docs/Tools-Reference.md#2-read)**                            | Get replies from channel posts, forum topics, or any message with one parameter                                |
| :busts_in_silhouette: **[Smart Contact Discovery](docs/Tools-Reference.md#1-discovery)**            | Search users, groups, channels with uniform entity schemas, forum detection, profile enrichment                |
| :file_folder: **[Folder Filtering](docs/Tools-Reference.md#1-discovery)**                           | Filter chats by dialog folder (archived, custom folders) with integer ID or name matching                      |
| :envelope: **[Advanced Messaging](docs/Tools-Reference.md#3-write)**                                | Send, edit, reply, post to forum topics, formatting, file attachments, and phone number messaging              |
| :paperclip: **[Secure File Handling](docs/Tools-Reference.md#3-write)**                             | Rich media sharing with SSRF protection, size limits, album support, optional HTTP attachment streaming        |
| :outbox_tray: **[Inline File Uploads](docs/Tools-Reference.md#3-write)**                           | Data: URI (base64) file uploads in `files` param — work in all transport modes, filenames preserved, images sent as photos |
| :microphone: **[Voice Transcription](docs/Tools-Reference.md#get_messages)**                       | Automatic speech-to-text for Premium accounts with parallel processing and polling                             |
| :zap: **High Performance**                                                                          | Async operations, parallel queries, and memory-conscious batching                                              |
| :shield: **Production Reliability**                                                                 | Auto-reconnect, configurable logging, comprehensive error handling                                               |


> **Prerequisite:** Install `uv` — see [docs](https://docs.astral.sh/uv/#installation) if you don't have it. Or use Docker (see [Installation Guide](docs/Installation.md)).

## Quick Start

### 1. Install and authenticate

**Quickest path (remote server):** Open `/setup` → scan QR → copy token (see [Try the Demo](#try-the-demo)).

**CLI path (local stdio):** Run `fast-mcp-telegram-setup` once to create a Telegram session — then `fast-mcp-telegram` serves it:
```bash
uvx --from fast-mcp-telegram fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+123456789"
```

**Bot token alternative (no phone, no OTP):**
Set `BOT_API_TOKEN` instead of `--phone-number`. See [Installation Guide](docs/Installation.md).

### 2. Configure MCP Client

**stdio mode (local):** Add to your MCP client config (e.g. `claude_desktop_config.json`) — stdio (standard input/output) is the default transport for local MCP clients:
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

**http-auth mode (remote):** Add to your MCP client config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://tg-mcp.l1979.ru/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

Get your token by scanning the QR code on the [setup page](/setup) or see [Installation Guide](docs/Installation.md) for deploying your own server.

### 3. Start Using
```json
{"tool": "search_messages_globally", "params": {"query": "hello", "limit": 5}}
{"tool": "get_messages", "params": {"chat_id": "me", "limit": 10}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello!"}}
```

## Deploy to Remote Server

Deploy your own MCP server on a VDS — see [Installation Guide](docs/Installation.md) for step-by-step instructions.

## Available Tools

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `search_messages_globally` | Search across all chats | Multi-term queries, date filtering, chat type filtering |
| `get_messages` | Unified message retrieval | Search/browse, read by IDs, get replies (posts/topics/messages), date filtering in all modes |
| `send_message` | Send new message | File attachments (URLs/local/data URIs), formatting (markdown/html), reply to forum topics |
| `edit_message` | Edit existing message | Text formatting, preserves message structure |
| `find_chats` | Find users/groups/channels | Multi-term search, contact discovery, folder filtering, username/phone lookup |
| `get_chat_info` | Get detailed profile info | Member counts, bio/about, online status, forum topics, enriched data |
| `send_message_to_phone` | Message phone numbers | Auto-contact management, optional cleanup, file support (URLs/data URIs) |
| `invoke_mtproto` | Direct Telegram API (power user) | Raw MTProto methods, entity resolution, safety guardrails — see [MTProto Bridge](docs/MTProto-Bridge.md) |

See [Tools Reference](docs/Tools-Reference.md) for detailed documentation with examples.


## Documentation

- [Installation Guide](docs/Installation.md) - Local setup and remote server deployment
- [Tools Reference](docs/Tools-Reference.md) - Complete tools documentation
- [MTProto Bridge](docs/MTProto-Bridge.md) - Direct API access via curl
- [Contributing](CONTRIBUTING.md) - Guidelines for contributors
- [Security](SECURITY.md) - Security features and best practices

## Telemetry

Anonymous tool telemetry since v0.30.1 — heartbeat every 6h, no credentials or message content collected. Opt out with `DO_NOT_TRACK=1`. See [ADR 0005](docs/adr/0005-anonymous-tool-telemetry.md).

Auth flow telemetry since v0.38.0 — atomic events during setup (phone, QR, bot token, reauthorize). Buffered flush on flow completion. See [ADR 0008](docs/adr/0008-auth-telemetry-events.md).

## License

MIT License - see [LICENSE](LICENSE)

mcp-name: io.github.leshchenko1979/fast-mcp-telegram


