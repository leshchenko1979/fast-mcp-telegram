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

- Python 3.x
- Telegram API credentials (API ID, API Hash)
- MCP-compatible environment (e.g., Cursor IDE, Claude Desktop)

 

## Quick Start & Usage

### 1. Authenticate with Telegram (one-time setup)

**Option A: Using uvx (Recommended)**
```bash
uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git fast-mcp-telegram-setup
```
- Works from any directory
- Automatically handles all dependencies
- Session files saved to `~/.config/fast-mcp-telegram/`
- Provide your Telegram credentials when prompted

**Option B: Local development setup**
1. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/leshchenko1979/fast-mcp-telegram.git
   cd fast-mcp-telegram
   pip install -r requirements.txt
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
        "args": ["--from", "git+https://github.com/leshchenko1979/fast-mcp-telegram.git", "fast-mcp-telegram"],
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
SESSION_DIR="/Users/myuser/work" SESSION_NAME="work_telegram" uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git fast-mcp-telegram-setup

SESSION_DIR="/Users/myuser/personal" SESSION_NAME="personal_telegram" uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git fast-mcp-telegram-setup
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
uvx --from git+https://github.com/leshchenko1979/fast-mcp-telegram.git fast-mcp-telegram --test-mode

# Using local installation
pip install -e .
fast-mcp-telegram --test-mode

# Direct Python execution (STDIO transport)
python3 src/server.py
```

## Available Tools

The server provides the following MCP tools:

- `search_messages(query: str, chat_id: str = None, limit: int = 50, offset: int = 0, chat_type: str = None, min_date: str = None, max_date: str = None, auto_expand_batches: int = 2, include_total_count: bool = False)`
  - Search for messages in Telegram chats
  - Supports both global search and chat-specific search
  - Supports pagination with `limit` and `offset` parameters
  - Supports filtering by chat type with the optional `chat_type` parameter:
    - `"private"` — only personal dialogs (one-to-one)
    - `"group"` — only group chats
    - `"channel"` — only channels/supergroups
    - `None` (default) — all types
  - Supports date range filtering with `min_date` and `max_date` (ISO format, e.g. `2024-05-15` or `2024-05-15T12:00:00`)
  - Supports `auto_expand_batches` (int, default 2): maximum additional batches to fetch if not enough filtered results are found
  - **Query parameter behavior:**
    - `query` accepts a single string; use comma-separated terms for multiple queries (e.g., `"deadline, due date"`). The tool searches each term in parallel and returns a single deduplicated set of results.
    - If `chat_id` is provided, you may leave `query` empty to fetch all messages from that chat (optionally filtered by `min_date` and `max_date`).
    - If `chat_id` is not provided (global search), at least one non-empty query term is required.
  - **Examples:**
    - Multiple queries (global, comma-separated):
      ```json
      {
        "tool": "search_messages",
        "params": {
          "query": "deadline, due date",
          "limit": 30
        }
      }
      ```
    - Multiple queries (per-chat, comma-separated):
      ```json
      {
        "tool": "search_messages",
        "params": {
          "query": "launch, release notes",
          "chat_id": "-1001234567890",
          "limit": 20
        }
      }
      ```
  - **Example: Fetch all messages from a chat in a date range:**
    ```json
    {
      "tool": "search_messages",
      "params": {
        "query": "",
        "chat_id": "123456789",
        "min_date": "2024-05-01",
        "max_date": "2024-05-31",
        "limit": 50
      }
    }
    ```
  - **Note:**
    - For global search (no `chat_id`), you must provide a non-empty `query`.
    - For per-chat search, an empty `query` will return all messages in the specified chat (optionally filtered by date).

- `send_or_edit_message(chat_id: str, message: str, reply_to_msg_id: int = None, parse_mode: str = None, message_id: int = None)`
  - Send messages to Telegram chats or edit existing messages
  - Supports replying to messages (when sending new messages)
  - Supports editing existing messages (when message_id is provided)
  - **parse_mode options:**
    - `None` (default): Plain text
    - `'md'` or `'markdown'`: Markdown formatting (*bold*, _italic_, [link](url), `code`)
    - `'html'`: HTML formatting (<b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>)
  - **Example sending new message with formatting:**
    ```json
    {
      "tool": "send_or_edit_message",
      "params": {
        "chat_id": "123456789",
        "message": "*Important Update*: The warehouse market is showing _strong growth_ trends. See [detailed report](https://example.com/report) for more information.",
        "parse_mode": "markdown"
      }
    }
    ```
  - **Example editing existing message:**
    ```json
    {
      "tool": "send_or_edit_message",
      "params": {
        "chat_id": "123456789",
        "message": "*Updated*: The warehouse market analysis has been revised with new data.",
        "message_id": 12345,
        "parse_mode": "markdown"
      }
    }
    ```

- `read_messages(chat_id: str, message_ids: list[int])`
  - Read specific messages by their IDs in a given chat
  - `chat_id` may be `@username`, a numeric user/chat ID, or a channel ID like `-100...`
  - Returns a list of message objects consistent with `search_messages` output
  - Example:
    ```json
    {
      "tool": "read_messages",
      "params": {
        "chat_id": "@flipping_invest",
        "message_ids": [993]
      }
    }
    ```

- `search_contacts(query: str, limit: int = 20)`
  - Search contacts using Telegram's native search

- `get_contact_details(chat_id: str)`
  - Get detailed information about a specific contact

- `invoke_mtproto(method_full_name: str, params_json: str)`
  - Dynamically invoke any raw MTProto method supported by Telethon
  - **Parameters:**
    - `method_full_name` (str): Full class name of the MTProto method, e.g., `"messages.GetHistory"`
    - `params_json` (str): JSON string with method parameters. All required fields must be provided (see Telegram API docs).
  - **Example:**
    ```json
    {
      "tool": "invoke_mtproto",
      "params": {
        "method_full_name": "messages.GetHistory",
        "params": {
          "peer": "@flipping_invest",
          "limit": 1,
          "offset_id": 0,
          "offset_date": 0,
          "add_offset": 0,
          "max_id": 0,
          "min_id": 0,
          "hash": 0
        }
      }
    }
    ```
  - **Note:**
    - You must provide all required parameters for the method. For `messages.GetHistory`, this includes `peer`, `limit`, `offset_id`, `offset_date`, `add_offset`, `max_id`, `min_id`, and `hash` (set `hash` to `0` unless you are using advanced caching).
    - The result will be a raw dictionary as returned by Telethon, including all message and chat metadata.
  - **Warning:**
    - This tool is for advanced users. Incorrect parameters may result in errors from the Telegram API or Telethon.
    - Refer to the [Telegram API documentation](https://core.telegram.org/methods) and [Telethon docs](https://docs.telethon.dev/en/latest/) for method details and required fields.

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


These examples illustrate how natural language requests can be mapped to MCP tool calls for powerful Telegram automation and search.

## Project Structure

```
fast-mcp-telegram/
├── src/                # Source code directory
│   ├── client/        # Telegram client management
│   ├── config/        # Configuration settings
│   ├── tools/         # MCP tool implementations
│   ├── utils/         # Utility functions
│   ├── __init__.py    # Package initialization
│   └── server.py      # Main server implementation
├── logs/              # Log files directory
├── setup_telegram.py  # Telegram setup script
├── setup.py          # Package setup configuration
├── requirements.txt  # Project dependencies
├── .env             # Environment variables (create this)
├── .gitignore       # Git ignore patterns
└── LICENSE          # MIT License

Note: *.session and *.session-journal files will be created after authentication
```

## Dependencies

The project relies on the following main packages:
```
fastmcp         # FastMCP framework for MCP servers
loguru          # Logging
aiohttp         # Async HTTP
telethon  # Telegram client
python-dotenv  # Environment management
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
