<img alt="Hero image" src="https://github.com/user-attachments/assets/635236f6-b776-41c7-b6e5-0dd14638ecc1" />

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://github.com/leshchenko1979/fast-mcp-telegram)

**Fast MCP Telegram Server** - Production-ready Telegram integration for AI assistants with comprehensive search, messaging, and direct API access capabilities.

## Demo

1. Open https://tg-mcp.l1979.ru/setup to begin the authentication flow.
2. After finishing, you'll receive a ready-to-use `mcp.json` with your Bearer token.
3. Use the config with your MCP client to check out this MCP server capabilities.
4. Or try the HTTP-MTProto Bridge right away with curl (replace TOKEN):
```bash
curl -X POST "https://tg-mcp.l1979.ru/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "message": "Hello from Demo!"}}'
```

## Features

| Feature | Description |
|---------|-------------|
| :closed_lock_with_key: **Multi-User Authentication** | Production-ready Bearer token auth with session isolation and LRU cache management |
| :globe_with_meridians: **HTTP-MTProto Bridge** | Direct curl access to any Telegram API method with entity resolution and safety guardrails |
| :mag: **Unified Message API** | Single `get_messages` tool for search, browse, read by IDs, and replies - 5 modes in one |
| :speech_balloon: **Universal Replies** | Get replies from channel posts, forum topics, or any message with one parameter |
| :mag_right: **Intelligent Search** | Global & per-chat message search with multi-query support and intelligent deduplication |
| :building_construction: **Dual Transport** | Seamless development (stdio) and production (HTTP) deployment support |
| :file_folder: **Secure File Handling** | Rich media sharing with SSRF protection, size limits, album support, optional HTTP attachment streaming |
| :envelope: **Advanced Messaging** | Send, edit, reply, post to forum topics, formatting, file attachments, and phone number messaging |
| :microphone: **Voice Transcription** | Automatic speech-to-text for Premium accounts with parallel processing and polling |
| :card_file_box: **Unified Session Management** | Single configuration system for setup and server, with multi-account support |
| :busts_in_silhouette: **Smart Contact Discovery** | Search users, groups, channels with uniform entity schemas, forum detection, profile enrichment |
| :zap: **High Performance** | Async operations, parallel queries, connection pooling, and memory optimization |
| :shield: **Production Reliability** | Auto-reconnect, structured logging, comprehensive error handling with clear actionable messages |
| :dart: **AI-Optimized** | Literal parameter constraints, LLM-friendly API design, and MCP ToolAnnotations |
| :globe_with_meridians: **Web Setup Interface** | Browser-based authentication flow with immediate config generation |

## Quick Start

### 1. Install
```bash
pip install fast-mcp-telegram
```

### 2. Authenticate
```bash
fast-mcp-telegram-setup --api-id="your_api_id" --api-hash="your_api_hash" --phone-number="+123456789"
```

Or use the web interface: run `fast-mcp-telegram` and open `/setup`

### 3. Configure MCP Client

**STDIO:**
```json
{
  "mcpServers": {
    "telegram": {
      "command": "fast-mcp-telegram",
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash"
      }
    }
  }
}
```

**HTTP_AUTH:**
```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-server.com",
      "headers": {
        "Authorization": "Bearer AbCdEfGh123456789..."
      }
    }
  }
}
```

### 4. Start Using
```json
{"tool": "search_messages_globally", "params": {"query": "hello", "limit": 5}}
{"tool": "get_messages", "params": {"chat_id": "me", "limit": 10}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello!"}}
```

## Deploy to Production

This project uses **GitHub Actions** for automatic builds and deployments.

1. Fork this repository
2. Add secrets in GitHub Settings: `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`
3. Edit `.env` in your fork
4. Push to `main` — deployment happens automatically

**Manual deployment:** Use `scripts/sync-vds-service.sh`

See [Deployment Guide](docs/Deployment.md) for details.

## Available Tools

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `search_messages_globally` | Search across all chats | Multi-term queries, date filtering, chat type filtering |
| `get_messages` | Unified message retrieval | Search/browse, read by IDs, get replies (posts/topics/messages), 5 modes |
| `send_message` | Send new message | File attachments (URLs/local), formatting (markdown/html), reply to forum topics |
| `edit_message` | Edit existing message | Text formatting, preserves message structure |
| `find_chats` | Find users/groups/channels | Multi-term search, contact discovery, username/phone lookup |
| `get_chat_info` | Get detailed profile info | Member counts, bio/about, online status, forum topics, enriched data |
| `send_message_to_phone` | Message phone numbers | Auto-contact management, optional cleanup, file support |
| `invoke_mtproto` | Direct Telegram API access | Raw MTProto methods, entity resolution, safety guardrails |

See [Tools Reference](docs/Tools-Reference.md) for detailed documentation with examples.

## Security

- Bearer token authentication with session isolation
- SSRF protection for file downloads
- Dangerous method blocking with opt-in override

See [SECURITY.md](SECURITY.md) for details.

## Documentation

- [Installation Guide](docs/Installation.md) - Local and production setup
- [Deployment Guide](docs/Deployment.md) - Docker and VDS deployment
- [Tools Reference](docs/Tools-Reference.md) - Complete tools documentation
- [MTProto Bridge](docs/MTProto-Bridge.md) - Direct API access via curl
- [Operations Guide](docs/Operations.md) - Monitoring and troubleshooting

## License

MIT License - see [LICENSE](LICENSE)