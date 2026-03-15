<img alt="Hero image" src="https://github.com/user-attachments/assets/635236f6-b776-41c7-b6e5-0dd14638ecc1" />

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://github.com/leshchenko1979/fast-mcp-telegram)

**Fast MCP Telegram Server** - Production-ready Telegram integration for AI assistants with comprehensive search, messaging, and direct API access capabilities.

## 🌐 Demo

1. Open https://tg-mcp.l1979.ru/setup to begin the authentication flow.
2. After finishing, you'll receive a ready-to-use `mcp.json` with your Bearer token.
3. Use the config with your MCP client to check out this MCP server capabilities.
4. Or try the HTTP‑MTProto Bridge right away with curl (replace TOKEN):
```bash
curl -X POST "https://tg-mcp.l1979.ru/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "message": "Hello from Demo!"}}'
```

## 📖 Table of Contents

- [✨ Features](#-features)
- [🎯 Design Philosophy](#-design-philosophy)
- [🚀 Quick Start](#-quick-start)
- [🏗️ Server Modes](#️-server-modes)
- [🌐 HTTP-MTProto Bridge](#-http-mtproto-bridge)
- [📚 Documentation](#-documentation)
- [🔒 Security](#-security)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 **Multi-User Authentication** | Production-ready Bearer token auth with session isolation and LRU cache management |
| 🌐 **HTTP-MTProto Bridge** | Direct curl access to any Telegram API method with entity resolution and safety guardrails |
| 🔍 **Unified Message API** | Single `get_messages` tool for search, browse, read by IDs, and replies - 5 modes in one |
| 💬 **Universal Replies** | Get replies from channel posts, forum topics, or any message with one parameter |
| 🔎 **Intelligent Search** | Global & per-chat message search with multi-query support and intelligent deduplication |
| 🏗️ **Dual Transport** | Seamless development (stdio) and production (HTTP) deployment support |
| 📁 **Secure File Handling** | Rich media sharing with SSRF protection, size limits, and album support |
| ✉️ **Advanced Messaging** | Send, edit, reply, post to forum topics, formatting, file attachments, and phone number messaging |
| 🎤 **Voice Transcription** | Automatic speech-to-text for Premium accounts with parallel processing and polling |
| 📊 **Unified Session Management** | Single configuration system for setup and server, with multi-account support |
| 👥 **Smart Contact Discovery** | Search users, groups, channels with uniform entity schemas, forum detection, profile enrichment |
| ⚡ **High Performance** | Async operations, parallel queries, connection pooling, and memory optimization |
| 🛡️ **Production Reliability** | Auto-reconnect, structured logging, comprehensive error handling with clear actionable messages |
| 🎯 **AI-Optimized** | Literal parameter constraints, LLM-friendly API design, and MCP ToolAnnotations |
| 🌍 **Web Setup Interface** | Browser-based authentication flow with immediate config generation |

## 🎯 Design Philosophy

**Save context space for LLMs by making tools as general-purpose as possible.** Fewer, more capable tools consume less of the AI's context window than many narrow-purpose tools. We consolidate functionality (e.g. `get_messages` handles search, browse, read-by-ID, and replies in one tool; `invoke_mtproto` provides raw API access for edge cases), use uniform schemas across tools so responses can be automatically processed when possible, and keep descriptions concise. We accept more parameters per tool and slightly more complex signatures in exchange for fewer tools and less context. When adding capabilities, we prefer extending existing tools over introducing new ones.

## 🛠️ Available Tools

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `search_messages_globally` | Search across all chats | Multi-term queries, date filtering, chat type filtering |
| `get_messages` | Unified message retrieval | Search/browse, read by IDs, get replies (posts/topics/messages), 5 modes |
| `send_message` | Send new message | File attachments (URLs/local), formatting (markdown/html), unified `reply_to_id` (message, forum topic, or channel post comment) |
| `edit_message` | Edit existing message | Text formatting, preserves message structure |
| `find_chats` | Find users/groups/channels | Multi-term search, contact discovery, username/phone lookup |
| `get_chat_info` | Get detailed profile info | Member counts, bio/about, online status, forum topics, enriched data |
| `send_message_to_phone` | Message phone numbers | Auto-contact management, optional cleanup, file support |
| `invoke_mtproto` | Direct Telegram API access | Raw MTProto methods, entity resolution, safety guardrails |

**📖 For detailed tool documentation with examples, see [Tools Reference](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Tools-Reference.md)**

## 🚀 Quick Start

### 1. Install from PyPI
```bash
pip install fast-mcp-telegram
```

### 2. Authenticate with Telegram
```bash
fast-mcp-telegram-setup --api-id="your_api_id" --api-hash="your_api_hash" --phone-number="+123456789"
```

**🌐 Prefer a browser?** Run the server and open `/setup` to authenticate and download a ready‑to‑use `mcp.json`. You can also reauthorize existing sessions through the same interface.

### 3. Configure Your MCP Client

**STDIO Mode (Development with Cursor IDE):**
```json
{
  "mcpServers": {
    "telegram": {
      "command": "fast-mcp-telegram",
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash",
        "PHONE_NUMBER": "+123456789"
      }
    }
  }
}
```

**HTTP_AUTH Mode (Production with Bearer Token):**
```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-server.com",
      "headers": {
        "Authorization": "Bearer AbCdEfGh123456789KLmnOpQr..."
      }
    }
  }
}
```

### 4. Start Using!
```json
// Global search across all chats
{"tool": "search_messages_globally", "params": {"query": "hello", "limit": 5}}

// Get latest messages from a chat
{"tool": "get_messages", "params": {"chat_id": "me", "limit": 10}}

// Search within a specific chat
{"tool": "get_messages", "params": {"chat_id": "@username", "query": "project"}}

// Read specific messages by ID
{"tool": "get_messages", "params": {"chat_id": "me", "message_ids": [123, 124]}}

// Get replies (channel posts, forum topics, or message replies)
{"tool": "get_messages", "params": {"chat_id": "-1001234567890", "reply_to_id": 42}}

// Send a message
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**📝 For detailed installation instructions, see [Installation Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Installation.md)**

## 🏗️ Server Modes

| Mode | Transport | Authentication | Use Case |
|------|----------|----------------|----------|
| **STDIO** | stdio | Disabled | Development with Cursor IDE |
| **HTTP_NO_AUTH** | HTTP | Disabled | Development HTTP server |
| **HTTP_AUTH** | HTTP | Required (Bearer token) | Production deployment |

## 🌐 HTTP-MTProto Bridge

**Direct curl access to any Telegram API method** - Execute any Telegram MTProto method via HTTP requests with automatic entity resolution and safety guardrails.

### Quick Examples
```bash
# Send message with automatic entity resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "@username", "message": "Hello from curl!"}}'

# Send message using params_json (works with n8n and other tools)
curl -X POST "https://your-domain.com/mtproto-api/messages.SendMessage" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params_json": "{\"peer\": \"@username\", \"message\": \"Hello from curl!\"}"}'

# Get message history with peer resolution
curl -X POST "https://your-domain.com/mtproto-api/messages.getHistory" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"params": {"peer": "me", "limit": 10}}'
```

**📖 For complete MTProto Bridge documentation, see [MTProto Bridge Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/MTProto-Bridge.md)**

## 📚 Documentation

- **[Installation Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Installation.md)** - Detailed installation and configuration
- **[Deployment Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Deployment.md)** - Docker deployment and production setup
- **[Tools Reference](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Tools-Reference.md)** - Complete tools documentation with examples
- **[Search Guidelines](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Search-Guidelines.md)** - Search best practices and limitations
- **[Operations Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Operations.md)** - Health monitoring and troubleshooting
- **[Project Structure](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/docs/Project-Structure.md)** - Code organization and architecture
- **[Contributing Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/CONTRIBUTING.md)** - Development setup and contribution guidelines

## 🔒 Security

**Key Security Features:**
- Bearer token authentication with session isolation
- SSRF protection for file downloads
- Dangerous method blocking with opt-in override
- Session file security and automatic cleanup

**📖 For complete security information, see [SECURITY.md](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/SECURITY.md)**

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/CONTRIBUTING.md) for:

- Development setup instructions
- Testing guidelines
- Code quality standards
- Pull request process

**Quick Start for Contributors:**
1. Fork the repository
2. Read the [Contributing Guide](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/CONTRIBUTING.md)
3. Create a feature branch
4. Make your changes and add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/leshchenko1979/fast-mcp-telegram/blob/master/LICENSE) file for details.

## 🙏 Acknowledgments

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram API library
- [Model Context Protocol](https://modelcontextprotocol.io) - Protocol specification

---

<div align="center">

**Made with ❤️ for the AI automation community**

[⭐ Star us on GitHub](https://github.com/leshchenko1979/fast-mcp-telegram) • [💬 Join our community](https://t.me/mcp_telegram)

</div>

---

mcp-name: io.github.leshchenko1979/fast-mcp-telegram
