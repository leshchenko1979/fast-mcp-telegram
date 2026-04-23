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
3. Download the `mcp.json` file
4. Configure your MCP client and ask your AI assistant: "send hello to my saved messages in telegram"

**Direct API (curl)**
3. Run the command below (replace TOKEN with yours):
```bash
curl -X POST "https://tg-mcp.l1979.ru/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "message": "Hello!"}}'
```
```

## Features

| Feature | Description | Details |
|---------|-------------|---------|
| :closed_lock_with_key: **Multi-User Authentication** | Production-ready Bearer token auth with session isolation and LRU cache management | [Docs](docs/Installation.md) |
| :globe_with_meridians: **HTTP-MTProto Bridge** | Direct curl access to any Telegram API method with entity resolution and safety guardrails | [Docs](docs/MTProto-Bridge.md) |
| :mag: **Unified Message API** | Single `get_messages` tool for search, browse, read by IDs, and replies - 5 modes in one | [Docs](docs/Tools-Reference.md) |
| :speech_balloon: **Universal Replies** | Get replies from channel posts, forum topics, or any message with one parameter | [Docs](docs/Tools-Reference.md) |
| :mag_right: **Intelligent Search** | Global & per-chat message search with multi-query support and intelligent deduplication | [Docs](docs/Search-Guidelines.md) |
| :building_construction: **Dual Transport** | Seamless development (stdio) and production (HTTP) deployment support | [Docs](docs/Installation.md) |
| :file_folder: **Secure File Handling** | Rich media sharing with SSRF protection, size limits, album support, optional HTTP attachment streaming | [Docs](docs/Tools-Reference.md) |
| :envelope: **Advanced Messaging** | Send, edit, reply, post to forum topics, formatting, file attachments, and phone number messaging | [Docs](docs/Tools-Reference.md) |
| :microphone: **Voice Transcription** | Automatic speech-to-text for Premium accounts with parallel processing and polling | [Docs](docs/Tools-Reference.md) |
| :card_file_box: **Unified Session Management** | Single configuration system for setup and server, with multi-account support | [Docs](docs/Installation.md) |
| :busts_in_silhouette: **Smart Contact Discovery** | Search users, groups, channels with uniform entity schemas, forum detection, profile enrichment | [Docs](docs/Tools-Reference.md) |
| :file_folder: **Folder Filtering** | Filter chats by dialog folder (archived, custom folders) with integer ID or name matching | [Docs](docs/Tools-Reference.md) |
| :robot: **Bot Chat Detection** | Bots identified with `type: "bot"` and filterable via `chat_type="bot"` | [Docs](docs/MTProto-Bridge.md) |
| :dart: **AI-Optimized** | Literal parameter constraints, LLM-friendly API design, and MCP ToolAnnotations | [Docs](docs/Tools-Reference.md) |
| :globe_with_meridians: **Web Setup Interface** | Browser-based authentication flow with immediate config generation | [Docs](docs/Installation.md) |
| :rocket: **MTProto Proxy Support** | Connect via MTProto proxy with automatic Fake TLS (EE prefix) and standard proxy detection | [Docs](docs/Installation.md) |
| :zap: **High Performance** | Async operations, parallel queries, connection pooling, and memory optimization | |
| :shield: **Production Reliability** | Auto-reconnect, structured logging, comprehensive error handling | |

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