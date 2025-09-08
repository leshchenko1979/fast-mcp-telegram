<img alt="Hero image" src="https://github.com/user-attachments/assets/996683da-1e61-4c6d-8681-6f4e6f4449ec" />

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://github.com/leshchenko1979/fast-mcp-telegram)


## 🌐 Demo

1. Open https://tg-mcp.redevest.ru/setup to begin the authentication flow.
2. After finishing, you’ll receive a ready-to-use `mcp.json` with your Bearer token. 
3. Use the config with your MCP client to check out this MCP server capabilities.

---

## 📖 Table of Contents

- [✨ Features](#-features)
- [📋 Prerequisites](#-prerequisites)
- [🚀 Choose Your Installation Path](#-choose-your-installation-path)
- [🏗️ Server Modes](#️-server-modes)
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
| 🎯 **LLM Optimization** | Literal parameter constraints guide AI model choices |

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

## 🏗️ Server Modes

The MCP server supports three distinct operation modes:

| Mode | Transport | Authentication | Use Case |
|------|----------|----------------|----------|
| **STDIO** | stdio | Disabled | Development with Cursor IDE |
| **HTTP_NO_AUTH** | HTTP | Disabled | Development HTTP server |
| **HTTP_AUTH** | HTTP | Required (Bearer token) | Production deployment |

---

## 📦 PyPI Installation

### 1. Install from PyPI
```bash
pip install fast-mcp-telegram
```

### 2. Telegram Authentication & Token Generation

The setup process creates an authenticated session and generates a unique Bearer token for your use:

```bash
fast-mcp-telegram-setup --api-id="your_api_id" --api-hash="your_api_hash" --phone-number="+123456789"

# Additional options available:
# --overwrite          # Auto-overwrite existing session
# --session-name NAME  # Use custom session name (advanced users)
```

**📝 Note:** The setup script automatically loads `.env` files from the current directory if they exist, making authentication seamless. You can create a `.env` file by copying `.env.example` and filling in your values.

**🌐 Prefer a browser?** Run the server and open `/setup` on your server to authenticate and download a ready‑to‑use `mcp.json` without running the CLI setup.

**🔑 Bearer Token Output:** After successful authentication, you'll receive a Bearer token:
```
✅ Setup complete!
📁 Session saved to: ~/.config/fast-mcp-telegram/AbCdEfGh123456789.session
🔑 Bearer Token: AbCdEfGh123456789KLmnOpQr...
💡 Use this Bearer token for authentication when using the MCP server:
   Authorization: Bearer AbCdEfGh123456789KLmnOpQr...
```

### 3. Configure Your MCP Client

**For STDIO mode (development with Cursor IDE):**
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

**For HTTP_NO_AUTH mode (development HTTP server):**
```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8000"
    }
  }
}
```

**For HTTP_AUTH mode (production with Bearer token):**
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
{"tool": "search_messages_globally", "params": {"query": "hello", "limit": 5}}
{"tool": "send_message", "params": {"chat_id": "me", "message": "Hello from AI!"}}
```

**ℹ️ Session Info:** 
- **STDIO mode**: Session saved to `~/.config/fast-mcp-telegram/telegram.session`
- **HTTP_NO_AUTH mode**: Session saved to `~/.config/fast-mcp-telegram/telegram.session`
- **HTTP_AUTH mode**: Sessions saved as `~/.config/fast-mcp-telegram/{token}.session`
- **Session Monitoring**: Use `/health` HTTP endpoint to monitor active sessions and server statistics

**✅ You're all set!** Jump to [Available Tools](#-available-tools) to explore features.

---

## 🌐 Web Setup (Browser Alternative to CLI)

In addition to the CLI setup, the server now includes a built-in browser setup flow as a first-class alternative:

- Open your server’s `/setup` route (for the demo, go to `https://tg-mcp.redevest.ru/setup`).
- Enter your phone number, then the code (and 2FA if enabled).
- The server immediately generates and displays a ready-to-use `mcp.json` with your Bearer token and a one-click download.

This is ideal if you prefer a guided flow without running the CLI. The CLI setup remains fully supported.

---

## 🐳 Docker Deployment (Production)

### Prerequisites

- **Docker & Docker Compose** installed
- **Telegram API credentials** ([get them here](https://my.telegram.org/auth))
- **Domain name** (for Traefik reverse proxy setup)

### 1. Environment Setup

Create a `.env` file in your project directory. You can copy from the example:

```bash
cp .env.example .env
```

Then edit `.env` with your actual values:

```bash
# Telegram API Credentials
API_ID=your_api_id
API_HASH=your_api_hash

# Domain Configuration (for remote docker deployment)
DOMAIN=your-domain.com

# Server Configuration
SERVER_MODE=http-auth       # stdio, http-no-auth, or http-auth
HOST=0.0.0.0                # Bind address (auto-adjusts based on server mode)
PORT=8000                   # Service port

# Optional: Session Management
MAX_ACTIVE_SESSIONS=10      # LRU cache limit for concurrent sessions

# Optional: Logging
LOG_LEVEL=INFO
```

**Note:** Phone number is specified during setup via CLI options rather than environment variables for better security and flexibility.

### 2. Telegram Authentication & Token Generation

**Important:** The setup process creates an authenticated Telegram session file and generates a Bearer token for HTTP authentication.

```bash
# 1. Run authentication setup with your phone number
docker compose --profile setup run --rm setup --phone-number="+1234567890"

# Alternative: Use all CLI options (bypasses .env file reading)
docker compose --profile setup run --rm setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+1234567890"

# 2. Note the Bearer token output after successful setup
# 🔑 Bearer Token: AbCdEfGh123456789KLmnOpQr...

# 3. Start the main MCP server (if not already running)
docker compose --profile server up -d
```

**Setup Options:**
- **Default**: Use `--phone-number` with .env file for API credentials
- **Full CLI**: Specify all credentials via command line options
- **Additional options**: `--overwrite`, `--session-name` available

**🌐 Browser alternative:** After the server is reachable, open `https://<DOMAIN>/setup` to authenticate via web and download `mcp.json` (no CLI needed). For local testing, use `http://localhost:8000/setup`.

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
# After completing setup, start the MCP server (if not already running)
docker compose --profile server up --build -d

# Check logs
docker compose logs -f fast-mcp-telegram

# Check health
docker compose ps
```

**Note:** Run setup with `docker compose --profile setup run --rm setup --phone-number="+1234567890"` to authenticate and generate a Bearer token. No server shutdown or restart required.

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
   docker compose --profile setup run --rm setup --phone-number="+1234567890"
   ```
2. After setup completes, start the MCP server (if not already running):
   ```bash
   docker compose --profile server up -d
   ```

The deployment script will:
- Transfer project files to your server
- Copy environment file
- Build the Docker containers (but won't start services automatically)

### 6. Configure Your MCP Client

**For HTTP_AUTH mode (production with Bearer token):**

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

**For HTTP_NO_AUTH mode (development HTTP server):**

```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8000"
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
- `SERVER_MODE=http-auth` - Server mode (stdio, http-no-auth, http-auth)
- `HOST=0.0.0.0` - Bind to all interfaces (auto-adjusts based on server mode)
- `PORT=8000` - Service port
- `DOMAIN` - Domain for Traefik routing and web setup
- `API_ID` / `API_HASH` - Telegram API credentials (used by setup)
- Phone number provided via CLI `--phone-number` option during setup

**Docker Compose Configuration:**
The `docker-compose.yml` automatically sets the server to `http-auth` mode for production deployment with Bearer token authentication.

---

## 🔧 Available Tools

### 🎯 LLM-Optimized Parameter Constraints
This MCP server uses `Literal` parameter types to guide AI model choices and ensure valid inputs:

- **`parse_mode`**: Constrained to `"markdown"` or `"html"` (no invalid values)
- **`chat_type`**: Limited to `"private"`, `"group"`, or `"channel"` for search filters
- **Enhanced Validation**: FastMCP automatically validates these constraints
- **Better LLM Guidance**: AI models see only valid options, reducing errors

### 📍 Supported Chat ID Formats
All tools that accept a `chat_id` parameter support these formats:
- `'me'` - Saved Messages (your own messages)
- `@username` - Username (without @ symbol)
- `123456789` - Numeric user ID
- `-1001234567890` - Channel ID (always starts with -100)

### 🔍 Search Query Guidelines
**Important**: Telegram search has specific limitations that LLMs should understand:

**✅ What Works:**
- **Exact words**: `"deadline"`, `"meeting"`, `"project"`
- **Multiple terms**: `"deadline, meeting, project"` (comma-separated)
- **Partial words**: `"proj"` (finds "project", "projects", etc.)
- **Case insensitive**: `"DEADLINE"` finds "deadline", "Deadline", etc.

**❌ What Doesn't Work:**
- **Wildcards**: `"proj*"`, `"meet%"`, `"dead*line"`
- **Regex patterns**: `"^project"`, `"deadline$"`, `"proj.*"`
- **Boolean operators**: `"project AND deadline"`, `"meeting OR call"`
- **Quotes for exact phrases**: `"exact phrase"` (treated as separate words)

**💡 Best Practices:**
- Use simple, common words that are likely to appear in messages
- Try multiple related terms: `"deadline, due, urgent"`
- Use partial words for broader matches: `"proj"` instead of `"project*"`

| Tool | Purpose | Key Features |
|------|---------|--------------|
| `search_messages_globally` | Search messages across all chats | Global search, filters by date/chat type |
| `search_messages_in_chat` | Search messages within specific chat | Per-chat search, total count support |
| `send_message` | Send new messages | Markdown/HTML formatting, replies |
| `edit_message` | Edit existing messages | Update message content with formatting |
| `read_messages` | Read specific messages by ID | Bulk reading, full metadata |
| `search_contacts` | Find users and contacts | By name, username, or phone |
| `get_contact_details` | Get user/chat profile information | Bio, status, online state |
| `send_message_to_phone` | Message by phone number | Auto-contact management |
| `invoke_mtproto` | Direct Telegram API access | Advanced operations |

### 🔍 search_messages_globally
**Search messages across all Telegram chats**

```typescript
search_messages_globally(
  query: str,                    // Search terms (comma-separated, required)
  limit?: number = 50,          // Max results
  chat_type?: 'private'|'group'|'channel', // Filter by chat type
  min_date?: string,            // ISO date format
  max_date?: string             // ISO date format
)
```

**Examples:**
```json
// Global search across all chats
{"tool": "search_messages_globally", "params": {"query": "deadline", "limit": 20}}

// Multi-term global search (comma-separated)
{"tool": "search_messages_globally", "params": {"query": "project, launch", "limit": 30}}

// Partial word search (finds "project", "projects", etc.)
{"tool": "search_messages_globally", "params": {"query": "proj", "limit": 20}}

// Filtered by date and type
{"tool": "search_messages_globally", "params": {
  "query": "meeting",
  "chat_type": "private",
  "min_date": "2024-01-01"
}}
```

**❌ Common LLM Mistakes to Avoid:**
```json
// DON'T use wildcards - these won't work:
{"tool": "search_messages_globally", "params": {"query": "proj*"}}  // ❌
{"tool": "search_messages_globally", "params": {"query": "meet%"}}  // ❌

// DON'T use regex - these won't work:
{"tool": "search_messages_globally", "params": {"query": "^project"}}  // ❌
{"tool": "search_messages_globally", "params": {"query": "deadline$"}}  // ❌

// DO use simple terms instead:
{"tool": "search_messages_globally", "params": {"query": "proj"}}      // ✅
{"tool": "search_messages_globally", "params": {"query": "meet"}}      // ✅
{"tool": "search_messages_globally", "params": {"query": "project"}}   // ✅
{"tool": "search_messages_globally", "params": {"query": "deadline"}}  // ✅
```

### 📍 search_messages_in_chat
**Search messages within a specific Telegram chat**

```typescript
search_messages_in_chat(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  query?: str,                   // Search terms (optional, returns latest if omitted)
  limit?: number = 50,          // Max results
  min_date?: string,            // ISO date format
  max_date?: string             // ISO date format
)
```

**Examples:**
```json
// Search in specific chat
{"tool": "search_messages_in_chat", "params": {"chat_id": "-1001234567890", "query": "launch"}}

// Get latest messages from Saved Messages (no query = latest messages)
{"tool": "search_messages_in_chat", "params": {"chat_id": "me", "limit": 10}}

// Multi-term search in chat (comma-separated)
{"tool": "search_messages_in_chat", "params": {"chat_id": "telegram", "query": "update, news"}}

// Partial word search in chat
{"tool": "search_messages_in_chat", "params": {"chat_id": "me", "query": "proj"}}
```

**💡 Search Tips:**
- **No query**: Returns latest messages from the chat
- **Simple terms**: Use common words that appear in messages
- **Multiple terms**: Use comma-separated words for broader results
- **Partial words**: Use shorter forms to catch variations (e.g., "proj" finds "project", "projects")

### 💬 send_message
**Send new messages with formatting**

```typescript
send_message(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  message: str,                  // Message content
  reply_to_msg_id?: number,      // Reply to specific message
  parse_mode?: 'markdown'|'html' // Text formatting
)
```

**Examples:**
```json
// Send new message
{"tool": "send_message", "params": {
  "chat_id": "me",
  "message": "Hello from AI! 🚀"
}}

// Reply with formatting
{"tool": "send_message", "params": {
  "chat_id": "@username",
  "message": "*Important:* Meeting at 3 PM",
  "parse_mode": "markdown",
  "reply_to_msg_id": 67890
}}
```

### ✏️ edit_message
**Edit existing messages with formatting**

```typescript
edit_message(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  message_id: number,            // Message ID to edit (required)
  message: str,                  // New message content
  parse_mode?: 'markdown'|'html' // Text formatting
)
```

**Examples:**
```json
// Edit existing message
{"tool": "edit_message", "params": {
  "chat_id": "-1001234567890",
  "message_id": 12345,
  "message": "Updated: Project deadline extended"
}}

// Edit with formatting
{"tool": "edit_message", "params": {
  "chat_id": "me",
  "message_id": 67890,
  "message": "*Updated:* Meeting rescheduled to 4 PM",
  "parse_mode": "markdown"
}}
```

### 📖 read_messages
**Read specific messages by ID**

```typescript
read_messages(
  chat_id: str,                  // Chat identifier (see Supported Chat ID Formats above)
  message_ids: number[]          // Array of message IDs to retrieve
)
```

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
  chat_id: str                  // User/channel identifier (see Supported Chat ID Formats above)
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
├── src/                          # Source code
│   ├── client/                   # Telegram client management
│   ├── config/                   # Configuration and logging
│   ├── server_components/        # Server modules (auth, health, tools, web setup)
│   ├── templates/                # Web setup interface templates
│   ├── tools/                    # MCP tool implementations
│   ├── utils/                    # Utility functions
│   ├── cli_setup.py              # CLI setup with pydantic-settings
│   └── server.py                 # Main server entry point
├── tests/                        # Test suite
├── memory-bank/                  # Project documentation
├── scripts/                      # Deployment scripts
├── .env.example                  # Environment template
├── docker-compose.yml            # Docker configuration
├── Dockerfile                    # Container build
├── pyproject.toml                # Project configuration
└── README.md                     # This file
```
**Session Management:** Session files are stored in the standard user config directory:
- **All installations:** `~/.config/fast-mcp-telegram/telegram.session` (persistent storage)
- **Multi-user:** `~/.config/fast-mcp-telegram/{token}.session` (token-based isolation)

**Security Note:** Session files contain sensitive authentication data and are never committed to version control. Each environment (local, Docker, remote server) maintains its own authenticated session.


## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| **fastmcp** | MCP server framework |
| **telethon** | Telegram API client |
| **loguru** | Structured logging |
| **aiohttp** | Async HTTP client |
| **python-dotenv** | Environment management |

**Version Management**: Single source of truth in `src/_version.py` with automatic synchronization across build system, runtime, and Docker deployments.

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
