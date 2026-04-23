<img alt="Hero image" src="https://github.com/user-attachments/assets/635236f6-b776-41c7-b6e5-0dd14638ecc1" />

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://github.com/leshchenko1979/fast-mcp-telegram)
[![Health Status](https://gatus.l1979.ru/api/v1/endpoints/always-on_fast-mcp-telegram/uptimes/30d/badge.svg)](https://gatus.l1979.ru/endpoints/always-on_fast-mcp-telegram)

**Fast MCP Telegram Server** - Telegram integration with direct API access, powerful search, and advanced messaging for AI assistants.

## Try the Demo

1. Open https://tg-mcp.l1979.ru/setup and complete authentication
2. Copy your Bearer token from the setup page

Then choose your path:

**MCP Client (AI assistants)**
- Download the `mcp.json` file
- Add the server to your AI client and ask: "send hello to my saved messages in telegram"

**Direct API (curl)**
- Run the command below (replace TOKEN with yours):
```bash
curl -X POST "https://tg-mcp.l1979.ru/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "message": "Hello!"}}'
```

## Features

| Feature | Description |
|---------|-------------|
| [:globe_with_meridians:] [**HTTP-MTProto Bridge**](docs/MTProto-Bridge.md#key-benefits) | Direct curl access to any Telegram API method with entity resolution and safety guardrails |
| [:dart:] [**AI-Optimized**](docs/Tools-Reference.md#overview) | Literal parameter constraints, LLM-friendly API design, and MCP ToolAnnotations |
| [:closed_lock_with_key:] [**Multi-User Authentication**](docs/Installation.md#local-setup-stdio) | Production-ready Bearer token auth with session isolation and LRU cache management |
| [:tv:] [**Web Setup Interface**](docs/Installation.md#web-setup-interface) | Browser-based authentication flow with immediate config generation |
| [:building_construction:] [**Dual Transport**](docs/Installation.md#local-setup-stdio) | Seamless development (stdio) and production (HTTP) deployment support |
| [:rocket:] [**MTProto Proxy Support**](docs/Installation.md#remote-setup-http-auth) | Connect via MTProto proxy with automatic Fake TLS (EE prefix) and standard proxy detection |
| [:card_file_box:] [**Unified Session Management**](docs/Installation.md#configuration-reference) | Single configuration system for setup and server, with multi-account support |
| [:mag_right:] [**Intelligent Search**](docs/Search-Guidelines.md#what-works) | Global & per-chat message search with multi-query support and intelligent deduplication |
| [:mag:] [**Unified Message API**](docs/Tools-Reference.md#2-read) | Single `get_messages` tool for search, browse, read by IDs, and replies - 5 modes in one |
| [:speech_balloon:] [**Universal Replies**](docs/Tools-Reference.md#2-read) | Get replies from channel posts, forum topics, or any message with one parameter |
| [:busts_in_silhouette:] [**Smart Contact Discovery**](docs/Tools-Reference.md#1-discovery) | Search users, groups, channels with uniform entity schemas, forum detection, profile enrichment |
| [:file_folder:] [**Folder Filtering**](docs/Tools-Reference.md#1-discovery) | Filter chats by dialog folder (archived, custom folders) with integer ID or name matching |
| [:envelope:] [**Advanced Messaging**](docs/Tools-Reference.md#3-write) | Send, edit, reply, post to forum topics, formatting, file attachments, and phone number messaging |
| [:file_folder:] [**Secure File Handling**](docs/Tools-Reference.md#3-write) | Rich media sharing with SSRF protection, size limits, album support, optional HTTP attachment streaming |
| [:microphone:] [**Voice Transcription**](docs/Tools-Reference.md#4-advanced) | Automatic speech-to-text for Premium accounts with parallel processing and polling |
| [:robot:] [**Bot Chat Detection**](docs/MTProto-Bridge.md#advanced-features) | Bots identified with `type: "bot"` and filterable via `chat_type="bot"` |
| :zap: **High Performance** | Async operations, parallel queries, connection pooling, and memory optimization |
| :shield: **Production Reliability** | Auto-reconnect, structured logging, comprehensive error handling |

## Quick Start

### 1. Install and authenticate
```bash
uvx --from fast-mcp-telegram fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+123456789"
```

Sessions are stored in `~/.config/fast-mcp-telegram/`.

### 2. Configure MCP Client

**stdio mode (local):**
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

**http-auth mode (remote):** See [Installation Guide](docs/Installation.md) for deploying your own server and authenticating via web interface.

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
| `get_messages` | Unified message retrieval | Search/browse, read by IDs, get replies (posts/topics/messages), 5 modes |
| `send_message` | Send new message | File attachments (URLs/local), formatting (markdown/html), reply to forum topics |
| `edit_message` | Edit existing message | Text formatting, preserves message structure |
| `find_chats` | Find users/groups/channels | Multi-term search, contact discovery, folder filtering, username/phone lookup |
| `get_chat_info` | Get detailed profile info | Member counts, bio/about, online status, forum topics, enriched data |
| `send_message_to_phone` | Message phone numbers | Auto-contact management, optional cleanup, file support |
| `invoke_mtproto` | Direct Telegram API access | Raw MTProto methods, entity resolution, safety guardrails |

See [Tools Reference](docs/Tools-Reference.md) for detailed documentation with examples.

## HTTP-MTProto Bridge

**Direct curl access to any Telegram API method** — available for programmatic integration.

```bash
curl -X POST "https://tg-mcp.l1979.ru/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "message": "Hello from curl!"}}'
```

Supports any Telegram method, automatic entity resolution, and TL object construction.

**Integration examples:**
- CI/CD: send deploy notifications to Telegram channels
- Monitoring: push alerts and system metrics to admin groups
- Webhooks: receive external events and forward to Telegram
- Backup: export chat history to external storage systems
- Custom bots: extend functionality with external services

See [MTProto Bridge](docs/MTProto-Bridge.md) for full documentation.

## Documentation

- [Installation Guide](docs/Installation.md) - Local setup and remote server deployment
- [Tools Reference](docs/Tools-Reference.md) - Complete tools documentation
- [MTProto Bridge](docs/MTProto-Bridge.md) - Direct API access via curl
- [Contributing](CONTRIBUTING.md) - Guidelines for contributors
- [Security](SECURITY.md) - Security features and best practices

## License

MIT License - see [LICENSE](LICENSE)