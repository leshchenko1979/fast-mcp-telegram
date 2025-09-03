# 🚀 fast-mcp-telegram

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://github.com/leshchenko1979/fast-mcp-telegram)

<div align="center">

# 🤖 AI-Powered Telegram Automation

**Transform your AI assistant into a Telegram power user with full API access**

*Search messages, send automated replies, manage contacts, and control Telegram through any MCP-compatible AI client*

[![Quick Start](https://img.shields.io/badge/🚀_Quick_Start-2_min_setup-brightgreen?style=for-the-badge&logo=lightning)](#-pypi-installation)
[![Docker](https://img.shields.io/badge/🐳_Docker-Production_ready-blue?style=for-the-badge&logo=docker)](#-docker-deployment-production)
[![Community](https://img.shields.io/badge/💬_Community-Join_us-blue?style=for-the-badge&logo=telegram)](https://t.me/mcp_telegram)

**⚡ Lightning-fast setup • 🔍 Smart search • 💬 Auto-messaging • 📱 Phone integration • 🐳 Production-ready**

</div>

---

## 📖 Table of Contents

- [✨ Features](#-features)
- [📋 Prerequisites](#-prerequisites)
- [🚀 Choose Your Installation Path](#-choose-your-installation-path)
- [📦 PyPI Installation](#-pypi-installation)
- [🐳 Docker Deployment (Production)](#-docker-deployment-production)
- [💻 Local Development](#-local-development)
- [🔧 Available Tools](#-available-tools)
- [📁 Project Structure](#-project-structure)
- [📦 Dependencies](#-dependencies)
- [🔒 Security Considerations](#-security-considerations)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🙏 Acknowledgments](#-acknowledgments)

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

## 🚀 Choose Your Installation Path

| Path | Best For | Complexity | Maintenance |
|------|----------|------------|-------------|
| **📦 PyPI** | Most users, quick setup | ⭐⭐⭐⭐⭐ Easy | 🔧 Manual updates |
| **🐳 Docker (Production)** | Production deployment | ⭐⭐⭐⭐ Easy | 🐳 Container updates |
| **💻 Local Development** | Developers, contributors | ⭐⭐⭐ Medium | 🔧 Manual updates |

**Choose your path below:**
- [📦 PyPI Installation (2-minute setup)](#-pypi-installation)
- [🐳 Docker Deployment (Production)](#-docker-deployment-production)
- [💻 Local Development](#-local-development)

---

## 📦 PyPI Installation

### 1. Install from PyPI
```bash
pip install fast-mcp-telegram
```

### 2. One-Time Telegram Authentication


```bash
fast-mcp-telegram-setup --api-id="your_api_id" --api-hash="your_api_hash" --phone="+123456789"

# Additional options available:
# --overwrite          # Auto-overwrite existing session
# --session-name NAME  # Use custom session name
```

**📝 Note:** The setup script automatically loads `.env` files from the current directory if they exist, making authentication seamless.

### 3. Configure Your MCP Client
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

### 4. Start Using!
```json
{"tool": "search_messages", "params": {"query": "hello", "limit": 5}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**ℹ️ Session Info:** Your Telegram session is saved to `~/.config/fast-mcp-telegram/telegram.session` (one-time setup)

**✅ You're all set!** Jump to [Available Tools](#-available-tools) to explore features.

---

## 🐳 Docker Deployment (Production)

### Prerequisites

- **Docker & Docker Compose** installed
- **Telegram API credentials** ([get them here](https://my.telegram.org/auth))
- **Domain name** (for Traefik reverse proxy setup)

### 1. Environment Setup

Create a `.env` file in your project directory:

```bash
# Telegram API Credentials
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+1234567890

# MCP Server Configuration
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000
SESSION_NAME=telegram

# Domain Configuration (optional - defaults to your-domain.com)
DOMAIN=your-domain.com

# Optional: Logging
LOG_LEVEL=INFO
```

### 2. Telegram Authentication (One-Time Setup)

**Important:** The setup process creates an authenticated Telegram session file in the persistent user config directory.

```bash
# 1. Run authentication setup
docker compose --profile setup run --rm setup

# 2. Start the main MCP server
docker compose up -d
```

**Creates authenticated session file at `~/.config/fast-mcp-telegram/telegram.session`**

### 3. Domain Configuration (Optional)

The default domain is `your-domain.com`. To use your own domain:

1. **Set up DNS**: Point your domain to your server
2. **Configure environment**: Add `DOMAIN=your-domain.com` to your `.env` file
3. **Traefik network**: Ensure `traefik-public` network exists on your host

**Example:**
```bash
# In your .env file
DOMAIN=my-telegram-bot.example.com
```

### 4. Local Docker Deployment

```bash
# Build and start the service
docker compose up --build -d

# Check logs
docker compose logs -f fast-mcp-telegram

# Check health
docker compose ps
```

The service will be available at `http://localhost:8000` (internal) and through Traefik if configured.

### 5. Remote Server Deployment

For production deployment on a remote server:

```bash
# Set up environment variables for remote deployment
export VDS_USER=your_server_user
export VDS_HOST=your.server.com
export VDS_PROJECT_PATH=/path/to/deployment

# Run the deployment script
./scripts/deploy-mcp.sh
```

The script will:
- Transfer project files to your server
- Copy environment file
- Build and start the Docker containers

### 6. Configure Your MCP Client

For HTTP-based MCP clients:

```json
{
  "mcpServers": {
    "telegram": {
      "command": "curl",
      "args": ["-X", "POST", "https://your-domain.com/mcp"],
      "env": {}
    }
  }
}
```

Or for direct HTTP connection:

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-domain.com"
    }
  }
}
```

### 7. Verify Deployment

```bash
# Check container status
docker compose ps

# View logs
docker compose logs fast-mcp-telegram

# Test health endpoint
curl -s https://your-domain.com/health
```

**Environment Variables:**
- `MCP_TRANSPORT=http` - HTTP transport mode
- `MCP_HOST=0.0.0.0` - Bind to all interfaces
- `MCP_PORT=8000` - Service port
- `SESSION_NAME=telegram` - Telegram session name

---

## 💻 Local Development

### 1. Clone and Setup
```bash
git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
cd fast-mcp-telegram
pip install -e .[dev]  # Install all dependencies including dev tools
```

### 2. Authenticate with Telegram

**Setup Command Options:**

```bash
# Automatic .env file loading (recommended)
echo "API_ID=your_api_id" > .env
echo "API_HASH=your_api_hash" >> .env
echo "PHONE_NUMBER=+123456789" >> .env
python src/setup_telegram.py

# Using CLI arguments
python src/setup_telegram.py --api-id="your_api_id" --api-hash="your_api_hash" --phone="+123456789"

# Using environment variables
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" \
python src/setup_telegram.py

# Additional options available:
# --overwrite          # Auto-overwrite existing session
# --session-name NAME  # Use custom session name
```

**📝 Note:** The setup script automatically loads `.env` files from the project directory if they exist, making authentication seamless.

### 3. Configure Your MCP Client
```json
{
  "mcpServers": {
    "telegram": {
      "command": "python3",
      "args": ["src/server.py"],
      "cwd": "/path/to/fast-mcp-telegram"
    }
  }
}
```

### 4. Start Using!
```json
{"tool": "search_messages", "params": {"query": "hello", "limit": 5}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**ℹ️ Session Info:** Your Telegram session is saved to `~/.config/fast-mcp-telegram/telegram.session` (one-time setup)

**✅ You're all set!** Continue below for development tools.

---

## 🛠️ Development

```bash
pip install -e .[dev]  # Install dev dependencies
ruff format .         # Format code
ruff check .          # Lint code
python src/server.py  # Test server
```

---

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
├── scripts/           # Deployment and utility scripts
│   └── deploy-mcp.sh  # Enhanced deployment script
├── logs/              # Log files directory
├── pyproject.toml     # Project configuration and dependencies
├── docker-compose.yml # Production Docker configuration
├── Dockerfile         # Single-stage pip build
├── .env               # Environment variables (create this)
├── .gitignore         # Git ignore patterns
└── LICENSE            # MIT License

**Session Management:** Session files are stored in the standard user config directory:
- **All installations:** `~/.config/fast-mcp-telegram/telegram.session` (persistent storage)

**Security Note:** Session files contain sensitive authentication data and are never committed to version control. Each environment (local, Docker, remote server) maintains its own authenticated session.
```

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| **fastmcp** | MCP server framework |
| **telethon** | Telegram API client |
| **loguru** | Structured logging |
| **aiohttp** | Async HTTP client |
| **python-dotenv** | Environment management |

**Installation:** `pip install -e .` (dependencies managed via `pyproject.toml`)

---

## 🔒 Security

**🚨 CRITICAL SECURITY WARNING:** Once authenticated, anyone with access to this MCP server can perform **ANY action** on your Telegram account. Implement proper access controls before deployment.

**Session files contain your complete Telegram access - keep them secure and never commit to version control.**

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

**Development setup:**
```bash
pip install -e .[dev]  # Install dev dependencies
ruff format .         # Format code
ruff check .          # Lint code
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
