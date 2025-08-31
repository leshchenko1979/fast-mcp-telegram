# fast-mcp-telegram

A powerful MCP server implementation built with FastMCP that provides Telegram functionality through a clean API interface, including search and messaging capabilities.

Join our [Telegram Discussion Group](https://t.me/mcp_telegram) for support, updates, and community discussions.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start & Usage](#quick-start--usage)
- [Available Tools](#available-tools)
- [Result Structure & Completeness](#result-structure--completeness)
- [Examples](#examples)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [License](#license)

## Features

- Message search
  - Global and per-chat modes
  - Multiple query support with comma-separated terms and parallel execution
  - Filters: chat type (private/group/channel), date range, pagination
  - Auto-expansion for filtered results and optional include_total_count (per-chat)
- Messaging
  - Send new messages and edit existing ones
  - Replies and Markdown/HTML formatting
- Message access
  - Read specific messages by IDs
  - Generate direct links to messages
- Results
  - Full-fidelity message objects: id, date, chat, text, link, sender, reply_to_msg_id, media, forwarded_from
  - LLM-optimized media placeholders with mime_type, file_size, and filename (no raw Telethon objects)
  - Consistent result structures across tools
- Contacts
  - Search contacts
  - Get contact details
- MTProto access
  - Invoke raw MTProto methods via JSON parameters
- Reliability and logging
  - Automatic reconnect and consistent error handling
  - Structured logging with request IDs
  - Module-level filtering reduces Telethon network spam by 99% while preserving important connection and error information
- MCP integration
  - Works with MCP-compatible clients (e.g., Cursor IDE, Claude Desktop); Cursor example provided
  - STDIO transport and HTTP test mode

## Prerequisites

- Python 3.10 or higher
- Telegram API credentials (API ID, API Hash)
- MCP-compatible environment (e.g., Cursor IDE, Claude Desktop)

 

## Quick Start & Usage

### 1. Authenticate with Telegram (one-time setup)

**Option A: Using uvx (Recommended)**

First, set your Telegram API credentials as environment variables:
```bash
export API_ID="your_api_id"
export API_HASH="your_api_hash"
export PHONE_NUMBER="+123456789"
```

Then run the setup:
```bash
uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master fast-mcp-telegram-setup
```

Or run it all in one command:
```bash
API_ID="your_api_id" API_HASH="your_api_hash" PHONE_NUMBER="+123456789" uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master fast-mcp-telegram-setup
```

- Works from any directory
- Automatically handles all dependencies
- Session files saved to `~/.config/fast-mcp-telegram/`
- You'll be prompted for the verification code from Telegram

**Option B: Local development setup**
1. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
   cd fast-mcp-telegram
   uv sync
   ```

2. Create a `.env` file with your credentials:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   PHONE_NUMBER=+123456789
   ```

3. Run the setup script:
   ```bash
   python setup_telegram.py
   ```
   Session files will be saved in the project directory.

### 2. Configure your MCP client

**Cursor example (`.cursor/mcp.json`):**

- **Option A: Using uvx (Recommended)**
  ```json
  {
    "mcpServers": {
      "mcp-telegram": {
        "command": "uvx",
        "args": ["--from", "git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master", "fast-mcp-telegram"],
        "env": {
          "API_ID": "your_api_id",
          "API_HASH": "your_api_hash",
          "PHONE_NUMBER": "+123456789"
        },
        "description": "Telegram MCP server with search and messaging tools"
      }
    }
  }
  ```

- **Option B: Local development**
  ```json
  {
    "mcpServers": {
      "mcp-telegram": {
        "command": "python3",
        "args": ["/path/to/fast-mcp-telegram/src/server.py"],
        "cwd": "/path/to/fast-mcp-telegram",
        "env": {
          "PYTHONPATH": "/path/to/fast-mcp-telegram"
        },
        "description": "Telegram MCP server with search and messaging tools"
      }
    }
  }
  ```

**Notes:**
- Replace credential placeholders with your actual Telegram API credentials
- For other MCP clients (Claude Desktop, etc.), adapt the configuration format
- See supported clients at [modelcontextprotocol.io](https://modelcontextprotocol.io/clients)
- Reload the server in your MCP client after making configuration changes

### 3. Session File Information

**Default Locations:**
- **uvx users:** `~/.config/fast-mcp-telegram/mcp_telegram.session`
- **Local development:** `mcp_telegram.session` (in project directory)

**Environment Variable Controls:**

You can customize session file location using environment variables:

```bash
# Custom session directory
export SESSION_DIR="/path/to/your/custom/directory"

# Custom session file name (useful for multiple accounts)
export SESSION_NAME="my_custom_session"

# Example: Multiple accounts
SESSION_DIR="/Users/myuser/work" SESSION_NAME="work_telegram" uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master fast-mcp-telegram-setup

SESSION_DIR="/Users/myuser/personal" SESSION_NAME="personal_telegram" uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master fast-mcp-telegram-setup
```

**Important:**
- Session files are **persistent** - they survive server restarts and `uvx` cleanup
- **One-time authentication** - You only need to enter verification codes once
- **Cross-platform** - Session files work across different machines (if copied)
- **Multiple accounts** - Use different `SESSION_NAME` values for separate Telegram accounts

### 4. Optional: Direct console usage

For testing or development, you can run the server directly:

```bash
# Using uvx (temporary installation)
uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git@master fast-mcp-telegram --test-mode

# Using local installation
uv sync
uv run fast-mcp-telegram --test-mode

# Direct Python execution (STDIO transport)
python3 src/server.py
```

## Available Tools

The server provides the following MCP tools with concise, LLM-optimized descriptions:

### `search_messages(query: str, chat_id: str = None, limit: int = 50, offset: int = 0, chat_type: str = None, min_date: str = None, max_date: str = None, auto_expand_batches: int = 2, include_total_count: bool = False)`

Search Telegram messages with advanced filtering and pagination.

**MODES:**
- Per-chat: Set chat_id + optional query (use 'me' for Saved Messages)
- Global: No chat_id + required query (searches all chats)

**FEATURES:**
- Multiple queries: "term1, term2, term3"
- Date filtering: ISO format (min_date="2024-01-01")
- Chat type filter: "private", "group", "channel"
- Pagination: offset + limit (keep limit ≤ 50)

**EXAMPLES:**
```json
{"tool": "search_messages", "params": {"query": "deadline", "limit": 20}}  // Global search
{"tool": "search_messages", "params": {"chat_id": "me", "limit": 10}}      // Saved Messages
{"tool": "search_messages", "params": {"chat_id": "-1001234567890", "query": "launch"}}  // Specific chat
```

### `send_or_edit_message(chat_id: str, message: str, reply_to_msg_id: int = None, parse_mode: str = None, message_id: int = None)`

Send new message or edit existing message in Telegram chat.

**MODES:**
- Send: message_id=None (default)
- Edit: message_id=<existing_message_id>

**FORMATTING:**
- parse_mode=None: Plain text
- parse_mode="markdown": *bold*, _italic_, [link](url), `code`
- parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

**EXAMPLES:**
```json
{"tool": "send_or_edit_message", "params": {"chat_id": "me", "message": "Hello!"}}  // Send to Saved Messages
{"tool": "send_or_edit_message", "params": {"chat_id": "-1001234567890", "message": "Updated text", "message_id": 12345}}  // Edit message
```

### `read_messages(chat_id: str, message_ids: list[int])`

Read specific messages by their IDs from a Telegram chat.

**SUPPORTED CHAT FORMATS:**
- 'me': Saved Messages
- Numeric ID: User/chat ID (e.g., 133526395)
- Username: @channel_name or @username
- Channel ID: -100xxxxxxxxx

**USAGE:**
- First use search_messages() to find message IDs
- Then read specific messages using those IDs
- Returns full message content with metadata

**EXAMPLES:**
```json
{"tool": "read_messages", "params": {"chat_id": "me", "message_ids": [680204, 680205]}}  // Saved Messages
{"tool": "read_messages", "params": {"chat_id": "-1001234567890", "message_ids": [123, 124]}}  // Channel
```

### `search_contacts(query: str, limit: int = 20)`

Search Telegram contacts and users by name, username, or phone number.

**SEARCH SCOPE:**
- Your saved contacts
- Global Telegram users
- Public channels and groups

**QUERY TYPES:**
- Name: "John Doe" or "Иванов"
- Username: "@username" (without @)
- Phone: "+1234567890"

**WORKFLOW:**
1. Search for contact: search_contacts("John Doe")
2. Get chat_id from results
3. Search messages: search_messages(chat_id=chat_id, query="topic")

**EXAMPLES:**
```json
{"tool": "search_contacts", "params": {"query": "@telegram"}}      // Find user by username
{"tool": "search_contacts", "params": {"query": "John Smith"}}     // Find by name
{"tool": "search_contacts", "params": {"query": "+1234567890"}}    // Find by phone
```

### `get_contact_details(chat_id: str)`

Get detailed profile information for a specific Telegram user or chat.

**USE CASES:**
- Get full user profile after finding chat_id
- Retrieve contact details, bio, and status
- Check if user is online/bot/channel

**SUPPORTED FORMATS:**
- Numeric user ID: 133526395
- Username: "telegram" (without @)
- Channel ID: -100xxxxxxxxx

**EXAMPLES:**
```json
{"tool": "get_contact_details", "params": {"chat_id": "133526395"}}      // User by ID
{"tool": "get_contact_details", "params": {"chat_id": "telegram"}}       // User by username
{"tool": "get_contact_details", "params": {"chat_id": "-1001234567890"}} // Channel by ID
```

### `send_message_to_phone(phone_number: str, message: str, first_name: str = "Contact", last_name: str = "Name", remove_if_new: bool = False, reply_to_msg_id: int = None, parse_mode: str = None)`

Send message to phone number, auto-managing Telegram contacts.

**FEATURES:**
- Auto-creates contact if phone not in contacts
- Sends message immediately after contact creation
- Optional contact cleanup after sending
- Full message formatting support

**CONTACT MANAGEMENT:**
- Checks existing contacts first
- Creates temporary contact only if needed
- Removes temporary contact if remove_if_new=True

**REQUIREMENTS:**
- Phone number must be registered on Telegram
- Include country code: "+1234567890"

**EXAMPLES:**
```json
{"tool": "send_message_to_phone", "params": {"phone_number": "+1234567890", "message": "Hello from Telegram!"}}  // Basic send
{"tool": "send_message_to_phone", "params": {"phone_number": "+1234567890", "message": "*Important*", "remove_if_new": true}}  // Auto cleanup
```

### `invoke_mtproto(method_full_name: str, params_json: str)`

Execute low-level Telegram MTProto API methods directly.

**USE CASES:**
- Access advanced Telegram API features
- Custom queries not covered by standard tools
- Administrative operations

**METHOD FORMAT:**
- Full class name: "messages.GetHistory", "users.GetFullUser"
- Telegram API method names with proper casing

**PARAMETERS:**
- JSON string with method parameters
- Parameter names match Telegram API documentation
- Supports complex nested objects

**EXAMPLES:**
```json
{"tool": "invoke_mtproto", "params": {"method_full_name": "users.GetFullUser", "params_json": "{\"id\": {\"_\": \"inputUserSelf\"}}" }}  // Get self info
{"tool": "invoke_mtproto", "params": {"method_full_name": "messages.GetHistory", "params_json": "{\"peer\": {\"_\": \"inputPeerChannel\", \"channel_id\": 123456, \"access_hash\": 0}, \"limit\": 10}"}}  // Get chat history
```

## Result Structure & Completeness

The server returns full-fidelity, richly structured results to minimize follow-up queries and preserve important Telegram context.

- Search and read responses:
  - Top-level fields: `messages` (list), `has_more` (bool), and `total_count` (int, per-chat searches only when requested).
  - Each message includes: `id`, `date`, `chat`, `text`, `link`, `sender`, and when available `reply_to_msg_id`, `media`, `forwarded_from`.
  - **Media objects** are LLM-optimized placeholders containing:
    - `mime_type`: File type (e.g., "application/pdf", "video/mp4", "image/jpeg")
    - `approx_size_bytes`: File size in bytes (when available)
    - `filename`: Original filename for documents (when available)
    - No raw Telethon objects or binary data

Example message object:

```json
{
  "id": 123,
  "date": "2025-08-25T12:34:56",
  "chat": { "id": 123456, "type": "Channel", "title": "Example" },
  "text": "Hello",
  "link": "https://t.me/c/123456/123",
  "sender": { "id": 111, "username": "alice" },
  "reply_to_msg_id": 100,
  "media": { },
  "forwarded_from": { }
}
```

- Send/edit responses:
  - Include `message_id`, `date`, `chat`, `text`, `status` (e.g., `sent` or `edited`), `sender`, and optional `edit_date` when edited.

Example send/edit result:

```json
{
  "message_id": 456,
  "date": "2025-08-25T12:35:10",
  "chat": { "id": 123456, "type": "Channel", "title": "Example" },
  "text": "Updated content",
  "status": "edited",
  "sender": { "id": 111, "username": "alice" },
  "edit_date": "2025-08-25T12:36:00"
}
```

## Examples

Here are some practical scenarios and example user requests you can make to an AI Agent using this MCP Telegram server:


- **Find all private conversations about warehouses since a specific date**
  - User: `Find all private chats about warehouses since May 1, 2025.`
  - AI Agent action:
    ```json
    {
      "tool": "search_messages",
      "params": {
        "query": "warehouse",
        "chat_type": "private",
        "min_date": "2025-05-01"
      }
    }
    ```

- **Get the latest warehouse market analytics from broker channels**
  - User: `Find the latest warehouse market analytics from broker channels.`
  - AI Agent action:
    ```json
    {
      "tool": "search_messages",
      "params": {
        "query": "warehouse market analytics",
        "chat_type": "channel",
        "limit": 10
      }
    }
    ```

- **Summarize the current warehouse market and send to an assistant**
  - User: `Summarize the current state of the warehouse market and send it to my assistant, Jane Smith.`
  - AI Agent action (after resolving the chat_id for Jane Smith):
    ```json
    {
      "tool": "send_or_edit_message",
      "params": {
        "chat_id": "123456789",
        "message": "Summary of the current warehouse market situation (2025):\n\n- The volume of new warehouse construction in Russia reached a record 1.2 million sq.m in Q1 2025, a 12% increase year-over-year, mainly due to high demand in previous years. However, forecasts indicate a 29% year-over-year decrease in new warehouse supply in Moscow and the region by the end of 2026, down to 1.2 million sq.m, due to high financing costs and rising construction expenses.\n- Developers are increasingly shifting from speculative projects to build-to-suit and owner-occupied warehouses, with many taking a wait-and-see approach.\n- The share of e-commerce companies among tenants has dropped sharply (from 57% to 15-34%), while the share of logistics, transport, and distribution companies is growing.\n- Despite a drop in demand and a slight increase in vacancy (up to 2-4%), rental rates for class A warehouses continue to rise.\n- Regional expansion of retailers has led to record-high new supply, with the Moscow region remaining the leader (44% of new supply in Q1 2025).\n- The market is experiencing a cooling after several years of rapid growth, but there is potential for renewed activity if monetary policy eases.\n\nIf you need more details or analytics, let me know!"
      }
    }
    ```


- **Send a message to a phone number not in contacts**
  - User: `Send a message to +1234567890 saying "Hello from MCP server!"`
  - AI Agent action:
    ```json
    {
      "tool": "send_message_to_phone",
      "params": {
        "phone_number": "+1234567890",
        "message": "Hello from MCP server!",
        "first_name": "Contact",
        "last_name": "Name",
        "remove_if_new": false,
        "parse_mode": null
      }
    }
    ```

These examples illustrate how natural language requests can be mapped to MCP tool calls for powerful Telegram automation and search.

## Project Structure

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

## Dependencies

The project uses [uv](https://github.com/astral-sh/uv) for dependency management and relies on the following main packages:
```
fastmcp         # FastMCP framework for MCP servers
loguru          # Logging
aiohttp         # Async HTTP
telethon        # Telegram client
python-dotenv   # Environment management
```

Dependencies are managed through `pyproject.toml` and locked in `uv.lock`.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
