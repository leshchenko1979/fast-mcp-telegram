# fast-mcp-telegram

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/fast-mcp-telegram.svg)](https://pypi.org/project/fast-mcp-telegram/)
[![Telegram](https://img.shields.io/badge/Telegram-API-blue?logo=telegram)](https://t.me/mcp_telegram)

A powerful MCP server for Telegram automation with search, messaging, and contact management capabilities. Built with FastMCP for seamless AI agent integration.

**🚀 2-minute setup • 📱 Full Telegram API • 🤖 AI-ready • ⚡ FastMCP powered**

[Quick Start](#quick-start) • [Documentation](#available-tools) • [Community](https://t.me/mcp_telegram)

---

## 🔥 Quick Start (2 minutes)

### 1. Install & Authenticate
```bash
# Install dependencies
uv sync

# Set up Telegram authentication
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" \
python src/setup_telegram.py
```

### 2. Configure MCP Client
```json
{
  "mcpServers": {
    "mcp-telegram": {
      "command": "python3",
      "args": ["/path/to/fast-mcp-telegram/src/server.py"],
      "cwd": "/path/to/fast-mcp-telegram",
      "description": "Telegram MCP server"
    }
  }
}
```

### 3. Start Using!
```json
{"tool": "search_messages", "params": {"query": "hello", "limit": 5}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Search** | Global & per-chat message search with filters |
| 💬 **Messaging** | Send, edit, reply with formatting support |
| 👥 **Contacts** | Search users, get profiles, manage contacts |
| 📱 **Phone Integration** | Message by phone number, auto-contact management |
| 🔧 **Low-level API** | Direct MTProto access for advanced operations |
| ⚡ **Performance** | Async operations, connection pooling, caching |
| 🛡️ **Reliability** | Auto-reconnect, structured logging, error handling |

## 📋 Prerequisites

- **Python 3.10+**
- **Telegram API credentials** ([get them here](https://my.telegram.org/auth))
- **MCP-compatible client** (Cursor, Claude Desktop, etc.)

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)

## 🛠️ Installation

### Option A: uvx (Recommended)
```bash
# Install and setup in one command
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" \
uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master fast-mcp-telegram-setup
```

### Option B: Local Development
```bash
# Clone and install
git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
cd fast-mcp-telegram
uv sync

# Authenticate with Telegram
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" \
python src/setup_telegram.py
```

## ⚙️ Configuration

### Cursor IDE (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "telegram": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master", "fast-mcp-telegram"],
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash",
        "PHONE_NUMBER": "+123456789"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "telegram": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master", "fast-mcp-telegram"],
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash",
        "PHONE_NUMBER": "+123456789"
      }
    }
  }
}
```

### Session Management
- **Default location**: `~/.config/fast-mcp-telegram/mcp_telegram.session`
- **Custom location**: Set `SESSION_DIR` and `SESSION_NAME` environment variables
- **Multiple accounts**: Use different `SESSION_NAME` values

## 🧪 Development

### Code Quality
```bash
uv sync --all-extras  # Install dev dependencies
uv run ruff format . # Format code
uv run ruff check .  # Lint code
```

### Testing the Server
```bash
# Direct console usage
python3 src/server.py

# With test mode
uv run fast-mcp-telegram --test-mode
```

## 🔧 Available Tools

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `search_messages` | Search messages globally or in specific chats | Filters by date, chat type, multiple queries |
| `send_or_edit_message` | Send new messages or edit existing ones | Markdown/HTML formatting, replies |
| `read_messages` | Read specific messages by ID | Bulk reading, full metadata |
| `search_contacts` | Find users and contacts | By name, username, or phone |
| `get_contact_details` | Get user/chat profile information | Bio, status, online state |
| `send_message_to_phone` | Message by phone number | Auto-contact management |
| `invoke_mtproto` | Direct Telegram API access | Advanced operations |

### 📍 search_messages
**Search messages with advanced filtering**

```typescript
search_messages(
  query: str,                    // Search terms (comma-separated)
  chat_id?: str,                 // Specific chat ID ('me' for Saved Messages)
  limit?: number = 50,          // Max results
  chat_type?: 'private'|'group'|'channel', // Filter by chat type
  min_date?: string,            // ISO date format
  max_date?: string             // ISO date format
)
```

**Examples:**
```json
// Global search
{"tool": "search_messages", "params": {"query": "deadline", "limit": 20}}

// Chat-specific search
{"tool": "search_messages", "params": {"chat_id": "-1001234567890", "query": "launch"}}

// Filtered by date and type
{"tool": "search_messages", "params": {
  "query": "project",
  "chat_type": "private",
  "min_date": "2024-01-01"
}}
```

### 💬 send_or_edit_message
**Send or edit messages with formatting**

```typescript
send_or_edit_message(
  chat_id: str,                  // Target chat ID ('me', username, or numeric ID)
  message: str,                  // Message content
  reply_to_msg_id?: number,      // Reply to specific message
  parse_mode?: 'markdown'|'html', // Text formatting
  message_id?: number            // Edit existing message (omit for new)
)
```

**Examples:**
```json
// Send new message
{"tool": "send_or_edit_message", "params": {
  "chat_id": "me",
  "message": "Hello from AI! 🚀"
}}

// Edit existing message
{"tool": "send_or_edit_message", "params": {
  "chat_id": "-1001234567890",
  "message": "Updated: Project deadline extended",
  "message_id": 12345
}}

// Reply with formatting
{"tool": "send_or_edit_message", "params": {
  "chat_id": "@username",
  "message": "*Important:* Meeting at 3 PM",
  "parse_mode": "markdown",
  "reply_to_msg_id": 67890
}}
```

### 📖 read_messages
**Read specific messages by ID**

```typescript
read_messages(
  chat_id: str,                  // Chat identifier ('me', username, or numeric ID)
  message_ids: number[]          // Array of message IDs to retrieve
)
```

**Supported chat formats:**
- `'me'` - Saved Messages
- `@username` - Username
- `123456789` - User ID
- `-1001234567890` - Channel ID

**Examples:**
```json
// Read multiple messages from Saved Messages
{"tool": "read_messages", "params": {
  "chat_id": "me",
  "message_ids": [680204, 680205, 680206]
}}

// Read from a channel
{"tool": "read_messages", "params": {
  "chat_id": "-1001234567890",
  "message_ids": [123, 124, 125]
}}
```

### 👥 search_contacts
**Find users and contacts**

```typescript
search_contacts(
  query: str,                  // Search term (name, username, or phone)
  limit?: number = 20          // Max results to return
)
```

**Search capabilities:**
- **Saved contacts** - Your Telegram contacts
- **Global users** - Public Telegram users
- **Channels & groups** - Public channels and groups

**Query formats:**
- Name: `"John Doe"`
- Username: `"telegram"` (without @)
- Phone: `"+1234567890"`

**Examples:**
```json
// Find by username
{"tool": "search_contacts", "params": {"query": "telegram"}}

// Find by name
{"tool": "search_contacts", "params": {"query": "John Smith"}}

// Find by phone
{"tool": "search_contacts", "params": {"query": "+1234567890"}}
```

### ℹ️ get_contact_details
**Get user/chat profile information**

```typescript
get_contact_details(
  chat_id: str                  // User/channel identifier
)
```

**Returns:** Bio, status, online state, profile photos, and more

**Examples:**
```json
// Get user details by ID
{"tool": "get_contact_details", "params": {"chat_id": "133526395"}}

// Get details by username
{"tool": "get_contact_details", "params": {"chat_id": "telegram"}}

// Get channel information
{"tool": "get_contact_details", "params": {"chat_id": "-1001234567890"}}
```

### 📱 send_message_to_phone
**Message by phone number (auto-contact management)**

```typescript
send_message_to_phone(
  phone_number: str,           // Phone with country code (+1234567890)
  message: str,                // Message content
  first_name?: str = "Contact", // For new contacts
  last_name?: str = "Name",    // For new contacts
  remove_if_new?: boolean = false, // Remove temp contact after send
  parse_mode?: 'markdown'|'html'   // Text formatting
)
```

**Features:**
- Auto-creates contact if phone not in contacts
- Optional contact cleanup after sending
- Full formatting support

**Examples:**
```json
// Basic message to new contact
{"tool": "send_message_to_phone", "params": {
  "phone_number": "+1234567890",
  "message": "Hello from AI! 🤖"
}}

// Message with formatting and cleanup
{"tool": "send_message_to_phone", "params": {
  "phone_number": "+1234567890",
  "message": "*Urgent:* Meeting rescheduled to 4 PM",
  "parse_mode": "markdown",
  "remove_if_new": true
}}
```

### 🔧 invoke_mtproto
**Direct Telegram API access**

```typescript
invoke_mtproto(
  method_full_name: str,       // Full API method name (e.g., "messages.GetHistory")
  params_json: str            // JSON string of method parameters
)
```

**Use cases:** Advanced operations not covered by standard tools

**Examples:**
```json
// Get your own user information
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "users.GetFullUser",
  "params_json": "{\"id\": {\"_\": \"inputUserSelf\"}}"
}}

// Get chat message history
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "messages.GetHistory",
  "params_json": "{\"peer\": {\"_\": \"inputPeerChannel\", \"channel_id\": 123456, \"access_hash\": 0}, \"limit\": 10}"
}}
```



## 💡 Examples

### 🔍 **Message Search & Analysis**

**Find recent project mentions in team chats:**
```json
{
  "tool": "search_messages",
  "params": {
    "query": "deadline, milestone, blocker",
    "chat_type": "group",
    "min_date": "2024-01-01",
    "limit": 25
  }
}
```

**Monitor competitor mentions across channels:**
```json
{
  "tool": "search_messages",
  "params": {
    "query": "competitor_name",
    "chat_type": "channel",
    "limit": 50
  }
}
```

### 💬 **Automated Communication**

**Daily standup summary to team:**
```json
{
  "tool": "send_or_edit_message",
  "params": {
    "chat_id": "@team_chat",
    "message": "*Daily Standup - Today*\n\n✅ Completed: API optimization\n🚧 In Progress: UI improvements\n❓ Blockers: None\n\n*Tomorrow:* Database migration",
    "parse_mode": "markdown"
  }
}
```

**Smart reply to customer inquiry:**
```json
{
  "tool": "send_or_edit_message",
  "params": {
    "chat_id": "customer_chat_id",
    "message": "Thanks for reaching out! I'll look into this right away and get back to you within 2 hours.",
    "reply_to_msg_id": 12345
  }
}
```

### 👥 **Contact Management**

**Find team member for collaboration:**
```json
{
  "tool": "search_contacts",
  "params": {
    "query": "john developer"
  }
}
```

**Get colleague's availability:**
```json
{
  "tool": "get_contact_details",
  "params": {
    "chat_id": "@john_dev"
  }
}
```

### 📱 **Phone Integration**

**Emergency notification:**
```json
{
  "tool": "send_message_to_phone",
  "params": {
    "phone_number": "+1234567890",
    "message": "🚨 ALERT: Server down in production. Team notified.",
    "remove_if_new": false
  }
}
```

### 🤖 **Advanced Automation**

**Content moderation workflow:**
```json
// 1. Search for flagged content
{
  "tool": "search_messages",
  "params": {
    "query": "inappropriate_content",
    "chat_type": "channel",
    "limit": 10
  }
}

// 2. Get message details
{
  "tool": "read_messages",
  "params": {
    "chat_id": "channel_id",
    "message_ids": [123, 124, 125]
  }
}

// 3. Notify moderators
{
  "tool": "send_or_edit_message",
  "params": {
    "chat_id": "@moderators",
    "message": "⚠️ Content flagged for review in #general",
    "parse_mode": "markdown"
  }
}
```

### 📊 **Data Export & Reporting**

**Weekly activity report:**
```json
{
  "tool": "invoke_mtproto",
  "params": {
    "method_full_name": "messages.GetHistory",
    "params_json": "{\"peer\": {\"_\": \"inputPeerChannel\", \"channel_id\": 123456, \"access_hash\": 0}, \"limit\": 100, \"offset_date\": 1704067200}"
  }
}
```

## 🔧 Troubleshooting

### Common Issues

**❌ "Authentication failed"**
```bash
# Check your credentials
echo "API_ID: $API_ID"
echo "API_HASH: $API_HASH"
echo "PHONE_NUMBER: $PHONE_NUMBER"

# Re-run setup if credentials changed
python src/setup_telegram.py
```

**❌ "Session file not found"**
- **uvx users:** Check `~/.config/fast-mcp-telegram/`
- **Local dev:** Check project root for `mcp_telegram.session`
- **Multiple accounts:** Use different `SESSION_NAME` values

**❌ "Rate limited"**
- Telegram API has rate limits (30 requests/second for most operations)
- Add delays between bulk operations
- Consider using `invoke_mtproto` for large data exports

**❌ "Phone verification code expired"**
```bash
# Delete session and re-authenticate
rm ~/.config/fast-mcp-telegram/mcp_telegram.session
python src/setup_telegram.py
```

**❌ "Chat not found"**
- Verify chat ID format:
  - `me` for Saved Messages
  - `@username` for public chats
  - Numeric ID for private chats
  - `-100xxxxxxxxx` for channels

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python src/server.py
```

### Network Issues

**Proxy configuration:**
```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
```

**DNS issues:**
```bash
# Force IPv4
export TELETHON_FORCE_IPV4=true
```

### Getting Help

- 📖 **Documentation:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
- 💬 **Community:** [Telegram Discussion Group](https://t.me/mcp_telegram)
- 🐛 **Issues:** [GitHub Issues](https://github.com/leshchenko1979/fast-mcp-telegram/issues)

---

## 📁 Project Structure

```
fast-mcp-telegram/
├── src/               # Source code directory
│   ├── client/        # Telegram client management
│   ├── config/        # Configuration settings
│   ├── tools/         # MCP tool implementations
│   ├── utils/         # Utility functions
│   ├── __init__.py    # Package initialization
│   ├── server.py      # Main server implementation
│   └── setup_telegram.py  # Telegram setup script
├── logs/              # Log files directory
├── pyproject.toml     # Package setup configuration
├── uv.lock            # Dependency lock file
├── .env               # Environment variables (create this)
├── .gitignore         # Git ignore patterns
└── LICENSE            # MIT License

Note: *.session and *.session-journal files will be created after authentication
```

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| **fastmcp** | MCP server framework |
| **telethon** | Telegram API client |
| **loguru** | Structured logging |
| **aiohttp** | Async HTTP client |
| **python-dotenv** | Environment management |

**Installation:** `uv sync` (dependencies managed via `pyproject.toml`)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

**Development setup:**
```bash
uv sync --all-extras  # Install dev dependencies
uv run ruff format . # Format code
uv run ruff check .  # Lint code
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram API library
- [Model Context Protocol](https://modelcontextprotocol.io) - Protocol specification

---

<div align="center">

**Made with ❤️ for the AI automation community**

[⭐ Star us on GitHub](https://github.com/leshchenko1979/fast-mcp-telegram) • [💬 Join our community](https://t.me/mcp_telegram)

</div>
