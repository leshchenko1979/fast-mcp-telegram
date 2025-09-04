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
- [🔧 Available Tools](#-available-tools)
- [📊 Health & Session Monitoring](#-health--session-monitoring)
- [📁 Project Structure](#-project-structure)
- [📦 Dependencies](#-dependencies)
- [🔒 Security & Authentication](#-security--authentication)
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
| 🔐 **Multi-User Auth** | Bearer token authentication with session isolation |
| 🏗️ **Dual Transport** | HTTP (multi-user) and stdio (single-user) support |
| 📊 **Session Management** | LRU cache, automatic cleanup, health monitoring |
| ⚡ **Performance** | Async operations, parallel queries, connection pooling |
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
- [💻 Local Development](CONTRIBUTING.md#-development-setup)

---

## 📦 PyPI Installation

### 1. Install from PyPI
```bash
pip install fast-mcp-telegram
```

### 2. Telegram Authentication & Token Generation

The setup process creates an authenticated session and generates a unique Bearer token for your use:

```bash
fast-mcp-telegram-setup --api-id="your_api_id" --api-hash="your_api_hash" --phone="+123456789"

# Additional options available:
# --overwrite          # Auto-overwrite existing session
# --session-name NAME  # Use custom session name (advanced users)
```

**📝 Note:** The setup script automatically loads `.env` files from the current directory if they exist, making authentication seamless.

**🔑 Bearer Token Output:** After successful authentication, you'll receive a Bearer token:
```
✅ Setup complete!
📁 Session saved to: ~/.config/fast-mcp-telegram/AbCdEfGh123456789.session
🔑 Bearer Token: AbCdEfGh123456789KLmnOpQr...
💡 Use this Bearer token for authentication when using the MCP server:
   Authorization: Bearer AbCdEfGh123456789KLmnOpQr...
```

### 3. Configure Your MCP Client

**For stdio transport (single-user):**
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

**For HTTP transport with Bearer token authentication:**
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
{"tool": "search_messages", "params": {"query": "hello", "limit": 5}}
{"tool": "send_or_edit_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**ℹ️ Session Info:** 
- **Single-user (stdio)**: Session saved to `~/.config/fast-mcp-telegram/telegram.session`
- **Multi-user (HTTP)**: Sessions saved as `~/.config/fast-mcp-telegram/{token}.session`
- **Session Monitoring**: Use `/health` HTTP endpoint to monitor active sessions and server statistics

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

# Domain Configuration
DOMAIN=your-domain.com

# Optional: MCP Server Configuration
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Optional: Logging
LOG_LEVEL=INFO
```

**Note:** Phone number is specified during setup via CLI options rather than environment variables for better security and flexibility.

### 2. Telegram Authentication & Token Generation

**Important:** The setup process creates an authenticated Telegram session file and generates a Bearer token for HTTP authentication.

```bash
# 1. Run authentication setup with your phone number
docker compose --profile setup run --rm setup --phone="+1234567890"

# Alternative: Use all CLI options (bypasses .env file reading)
docker compose --profile setup run --rm setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone="+1234567890"

# 2. Note the Bearer token output after successful setup
# 🔑 Bearer Token: AbCdEfGh123456789KLmnOpQr...

# 3. Start the main MCP server
docker compose --profile server up -d
```

**Setup Options:**
- **Default**: Use `--phone` with .env file for API credentials
- **Full CLI**: Specify all credentials via command line options
- **Additional options**: `--overwrite`, `--session-name` available

**Profile System:**
- `--profile setup`: Runs only the Telegram authentication setup
- `--profile server`: Runs only the MCP server (after authentication)
- No profile: No services start (prevents accidental startup)

**Authentication Output:**
- **Session file**: `~/.config/fast-mcp-telegram/{token}.session`
- **Bearer token**: Unique token for HTTP authentication
- **Multi-user support**: Each setup creates isolated session

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
# After completing setup, start the MCP server
docker compose --profile server up --build -d

# Check logs
docker compose logs -f fast-mcp-telegram

# Check health
docker compose ps
```

**Note:** Always run setup first with `docker compose --profile setup up` before starting the server.

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

**Post-deployment setup:**
1. SSH to your server and run the Telegram authentication setup:
   ```bash
   ssh your_server_user@your.server.com
   cd /path/to/deployment
   docker compose --profile setup run --rm setup --phone="+1234567890"
   ```
2. After setup completes, start the MCP server:
   ```bash
   docker compose --profile server up -d
   ```

The deployment script will:
- Transfer project files to your server
- Copy environment file
- Build the Docker containers (but won't start services automatically)

### 6. Configure Your MCP Client

**HTTP transport with Bearer token authentication:**

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-domain.com",
      "headers": {
        "Authorization": "Bearer AbCdEfGh123456789KLmnOpQr..."
      }
    }
  }
}
```

**Alternative curl-based configuration:**

```json
{
  "mcpServers": {
    "telegram": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Authorization: Bearer AbCdEfGh123456789KLmnOpQr...",
        "https://your-domain.com/mcp"
      ],
      "env": {}
    }
  }
}
```

**⚠️ Important:** Replace `AbCdEfGh123456789KLmnOpQr...` with your actual Bearer token from the setup process.

### 7. Verify Deployment

```bash
# Check container status
docker compose ps

# View logs
docker compose logs fast-mcp-telegram

# Test health endpoint (includes session statistics)
curl -s https://your-domain.com/health
```

**Environment Variables:**
- `MCP_TRANSPORT=http` - HTTP transport mode
- `MCP_HOST=0.0.0.0` - Bind to all interfaces
- `MCP_PORT=8000` - Service port
- `API_ID` / `API_HASH` - Telegram API credentials (used by setup)
- Phone number provided via CLI `--phone` option during setup

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

### 📊 Health & Session Monitoring
**Monitor server health and session statistics**

For HTTP deployments, the server provides a `/health` endpoint for monitoring:

```bash
# Check server health and session statistics
curl -s https://your-domain.com/health
```

**Response includes:**
- Server status and transport mode
- Active session count and limits
- Per-session statistics (token prefix, last access time, connection status)
- Service metadata

**Example response:**
```json
{
  "status": "healthy",
  "service": "telegram-mcp-server",
  "transport": "http",
  "active_sessions": 3,
  "max_sessions": 10,
  "sessions": [
    {
      "token_prefix": "AbCdEfGh...",
      "hours_since_access": 0.25,
      "is_connected": true,
      "last_access": "Thu Jan 4 16:30:15 2025"
    }
  ]
}
```

## 📁 Project Structure

```
fast-mcp-telegram/
├── src/                  # Source code directory
│   ├── client/           # Telegram client management
│   ├── config/           # Configuration settings
│   ├── tools/            # MCP tool implementations
│   ├── utils/            # Utility functions and helpers
│   ├── __init__.py       # Package initialization
│   ├── server.py         # Main server implementation
│   └── setup_telegram.py # Telegram authentication setup
├── tests/                # Comprehensive test suite
│   ├── __init__.py       # Tests package initialization
│   ├── conftest.py       # Shared fixtures and configuration
│   ├── test_*.py         # Organized test modules by functionality
│   └── README.md         # Test documentation and guidelines
├── scripts/              # Deployment and utility scripts
│   └── deploy-mcp.sh     # Enhanced deployment script
├── logs/                 # Log files directory (auto-created)
├── pyproject.toml        # Project configuration and dependencies
├── docker-compose.yml    # Production Docker configuration
├── Dockerfile            # Optimized multi-stage build
├── .env                  # Environment variables (create this)
├── .gitignore            # Git ignore patterns
├── .dockerignore         # Docker build exclusions
└── LICENSE               # MIT License

**Session Management:** Session files are stored in the standard user config directory:
- **All installations:** `~/.config/fast-mcp-telegram/telegram.session` (persistent storage)
- **Multi-user:** `~/.config/fast-mcp-telegram/{token}.session` (token-based isolation)

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

---

## 🔒 Security & Authentication

**🚨 CRITICAL SECURITY WARNING:** This MCP server supports both single-user and multi-user deployments with Bearer token authentication.

### Bearer Token Authentication System
- **Per-Session Authentication**: Each session requires a unique Bearer token
- **Session Isolation**: Each token creates an isolated Telegram session
- **Token Generation**: Cryptographically secure 256-bit tokens via setup script
- **HTTP Authentication**: Mandatory Bearer tokens for HTTP transport (`Authorization: Bearer <token>`)
- **Development Mode**: `DISABLE_AUTH=true` bypasses authentication for development

### Multi-User Security Model
- **Session Separation**: Each user gets their own authenticated session file
- **Token Privacy**: Bearer tokens should be treated as passwords and kept secure
- **Session Files**: Contain complete Telegram access for the associated token
- **Account Access**: Anyone with a valid Bearer token can perform **ANY action** on that associated Telegram account

### Production Security Recommendations
1. **Secure Token Distribution**: Distribute Bearer tokens through secure channels only
2. **Token Rotation**: Regularly generate new tokens and invalidate old ones
3. **Access Monitoring**: Monitor session activity through `/health` HTTP endpoint
4. **Network Security**: Use HTTPS/TLS and consider IP restrictions
5. **Session Management**: Regularly clean up unused sessions and tokens

---

## 🤝 Contributing

We welcome contributions from the community! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for detailed development setup, testing guidelines, and contribution process.

### Quick Start for Contributors

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

For detailed development setup and contribution guidelines, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

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
