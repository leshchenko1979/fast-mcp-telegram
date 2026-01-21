# 📦 Installation Guide

Get your Telegram MCP server running in minutes!

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Telegram API credentials ([get them here](https://my.telegram.org/auth))
- MCP client (Cursor IDE, Claude Desktop, etc.)

### 🖥️ For Local Use (Cursor IDE / Claude Desktop)

**2-minute setup:**

```bash
# 1. Install
pip install fast-mcp-telegram

# 2. Authenticate
fast-mcp-telegram-setup \
  --api-id="your_api_id" \
  --api-hash="your_api_hash" \
  --phone-number="+1234567890"

# ✅ Done! Session saved to ~/.config/fast-mcp-telegram/telegram.session
```

**3. Configure your MCP client:**

Add to your `mcp.json`:
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

**4. Start using it!** Search for messages, send messages, and more.

---

### 🌐 For Remote Servers (Production)

**3-minute setup:**

```bash
# 1. Install
pip install fast-mcp-telegram

# 2. Start server with authentication
SERVER_MODE=http-auth fast-mcp-telegram

# 3. Open browser → http://your-server.com/setup
#    - Choose "Create New Session"
#    - Enter phone number
#    - Enter verification code
#    - Download mcp.json

# ✅ Done! Use the downloaded mcp.json in your MCP client
```

## 🌐 Web Setup Interface

The web setup interface provides a user-friendly way to manage Telegram sessions directly from your browser. Access it at `http://your-server.com/setup` when running in `http-auth` mode.

### 📱 Available Options

#### 1. **Create New Session** 🔐
Set up a completely new Telegram session:

1. Click **"Create New Session"**
2. Enter your phone number (include country code, e.g., `+1234567890`)
3. Telegram will send you a verification code
4. Enter the 5-digit code when prompted
5. If 2FA is enabled, enter your password
6. Download the generated `mcp.json` configuration file
7. Use this file in your MCP client

#### 2. **Reauthorize Existing Session** 🔄
Refresh an expired or unauthorized session while keeping your bearer token:

1. Click **"Reauthorize Existing Session"**
2. Enter your existing bearer token
3. Confirm your phone number
4. Enter the verification code sent by Telegram
5. If 2FA is enabled, enter your password
6. Your session is refreshed with the same token

#### 3. **Delete Session** 🗑️
Permanently remove a session file:

1. Click **"Delete Session"**
2. Enter your bearer token
3. Confirm deletion (⚠️ **This action cannot be undone**)
4. Session file is permanently removed

### 🔄 Session Management

**Reauthorizing Expired Sessions:**
- Use the **"Reauthorize Existing Session"** option
- Your bearer token remains the same
- No need to update MCP client configuration
- Phone verification prevents unauthorized access

**Removing Sessions:**
- Use the **"Delete Session"** option for permanent removal
- Requires bearer token authentication
- Safely disconnects active connections
- Completely removes session files from server

### 🔧 Troubleshooting Web Setup

**❌ "Session not found" error:**
- Verify your bearer token is correct
- Check that the session file exists on the server

**❌ "Invalid token" error:**
- Ensure you're not using reserved names like "telegram" or "default"
- Bearer tokens must be URL-safe strings

**❌ Phone verification issues:**
- Include country code in phone number (+1, +44, etc.)
- Wait for SMS or use Telegram app for code
- Check that your phone number is registered with Telegram

**❌ 2FA password issues:**
- Use your Telegram cloud password (not app lock PIN)
- If forgotten, reset via Telegram settings

---

## 🤔 Which Setup Method Do I Need?

| I want to... | Use this |
|--------------|----------|
| Use Cursor IDE or Claude Desktop locally | **CLI Setup** (above) |
| Deploy to a remote server with web interface | **Web Setup** (above) |
| Use multiple Telegram accounts | [Multiple Accounts](#-multiple-accounts) |
| Manage sessions without CLI access | **Web Setup** → "Reauthorize Existing Session" |
| Permanently remove a session | **Web Setup** → "Delete Session" |

---

## 📚 Detailed Configuration

### Understanding Server Modes

Fast MCP Telegram runs in three modes:

| Mode | Security | Best For | Setup Method |
|------|----------|----------|--------------|
| **Local** (`stdio`) | File-based | Cursor IDE, local clients | CLI |
| **Dev HTTP** (`http-no-auth`) | No auth ⚠️ | Local testing only | CLI |
| **Production** (`http-auth`) | Token-based | Remote servers | Web or CLI |

### Environment Configuration

Create a `.env` file for easy configuration:

```bash
# Required
API_ID=your_api_id
API_HASH=your_api_hash

# Optional
SERVER_MODE=stdio              # Local mode (default)
PORT=8000                      # Server port
LOG_LEVEL=INFO                 # Logging verbosity
SESSION_NAME=telegram          # Session identifier
```

**💡 Tip:** The CLI setup automatically loads `.env` files from your current directory.

### MCP Client Configuration Examples

<details>
<summary><b>Local Mode (STDIO)</b> - Click to expand</summary>

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
</details>

<details>
<summary><b>Development HTTP (No Auth)</b> - Click to expand</summary>

```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8000"
    }
  }
}
```

⚠️ **Security Warning:** Only use this mode in trusted local environments.
</details>

<details>
<summary><b>Production HTTP (With Auth)</b> - Click to expand</summary>

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-server.com",
      "headers": {
        "Authorization": "Bearer your_token_from_setup"
      }
    }
  }
}
```

**Getting the token:**
- **Web Setup:** Automatically included in downloaded `mcp.json`
- **CLI Setup:** Displayed in terminal output after authentication
</details>

---

## 👥 Multiple Accounts

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
      "command": "fast-mcp-telegram",
      "env": {
        "API_ID": "your_api_id",
        "API_HASH": "your_api_hash",
        "SESSION_NAME": "personal"
      }
    },
    "telegram-work": {
      "command": "fast-mcp-telegram",
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

## 🔧 Troubleshooting

<details>
<summary><b>Session already exists</b></summary>

Use the `--overwrite` flag to replace:
```bash
fast-mcp-telegram-setup --overwrite --api-id="..." --api-hash="..." --phone-number="..."
```
</details>

<details>
<summary><b>Authentication failed</b></summary>

Double-check:
- API credentials are correct
- Phone number includes country code (e.g., `+1234567890`)
- You're entering the correct verification code
</details>

<details>
<summary><b>Permission denied</b></summary>

Ensure the session directory is writable:
```bash
chmod 755 ~/.config/fast-mcp-telegram
```
</details>

<details>
<summary><b>Connection issues</b></summary>

- Check your internet connection
- Verify firewall settings
- For servers, ensure the port is open
</details>

### 📖 More Resources

- **[Operations Guide](Operations.md)** - Monitoring, debugging, health checks
- **[Tools Reference](Tools-Reference.md)** - Available MCP tools and usage
- **[SECURITY.md](../SECURITY.md)** - Security best practices
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Development setup for contributors

---

## 💡 Advanced Topics

### Session Management

Sessions are stored in `~/.config/fast-mcp-telegram/`:
- **Local modes:** `{SESSION_NAME}.session` (default: `telegram.session`)
- **Production mode:** `{bearer_token}.session` (auto-managed per user)

**Configuration priority:**
1. CLI argument: `--session-name myaccount`
2. Environment variable: `SESSION_NAME=myaccount`
3. `.env` file: `SESSION_NAME=myaccount`
4. Default: `telegram`

### Health Monitoring

Check server status and active sessions:
```bash
curl http://localhost:8000/health
```

Returns session count, uptime, and system statistics.

---

**Need help?** Open an [issue](https://github.com/leshchenko1979/fast-mcp-telegram/issues) on GitHub!
