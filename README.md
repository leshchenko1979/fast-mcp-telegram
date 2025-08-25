# fast-mcp-telegram

A powerful MCP server implementation built with FastMCP that provides Telegram functionality through a clean API interface, including search and messaging capabilities.

Join our [Telegram Discussion Group](https://t.me/mcp_telegram) for support, updates, and community discussions.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start & Usage](#quick-start--usage)
- [Available Tools](#available-tools)
- [Examples](#examples)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [License](#license)

## Features

- Message search
  - Global and per-chat modes
  - Filters: chat type (private/group/channel), date range, pagination
  - Auto-expansion for filtered results and optional include_total_count (per-chat)
- Messaging
  - Send new messages and edit existing ones
  - Replies and Markdown/HTML formatting
- Message access
  - Read specific messages by IDs
  - Generate direct links to messages
- Contacts
  - Search contacts
  - Get contact details
- MTProto access
  - Invoke raw MTProto methods via JSON parameters
- Reliability and logging
  - Automatic reconnect and consistent error handling
  - Structured logging with request IDs
- MCP integration
  - Works with MCP-compatible clients (e.g., Cursor IDE, Claude Desktop); Cursor example provided
  - STDIO transport and HTTP test mode

## Prerequisites

- Python 3.x
- Telegram API credentials (API ID, API Hash)
- MCP-compatible environment (e.g., Cursor IDE, Claude Desktop)

 

## Quick Start & Usage

1. Use in an MCP-compatible client (Recommended):

   Cursor example (`.cursor/mcp.json`):

   - Primary (uvx console script):

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
     Note: `uvx` will automatically download and isolate all required dependencies; no local `pip install` is needed.

   - Alternative (local development with python3):

     ```json
     {
       "mcpServers": {
         "mcp-telegram": {
           "command": "python3",
           "args": ["/path/to/your/fast-mcp-telegram/src/server.py"],
           "cwd": "/path/to/your/fast-mcp-telegram",
           "env": {
             "PYTHONPATH": "/path/to/your/fast-mcp-telegram"
           },
           "description": "Telegram MCP server with search and messaging tools"
         }
       }
     }
     ```

   Note: Replace `/path/to/your/fast-mcp-telegram` with your actual project path. The JSON above shows Cursor's configuration format; for other MCP clients (e.g., Claude Desktop), adapt to their configuration. If you modify the server code, reload the server in your MCP client for changes to take effect. See supported clients at [modelcontextprotocol.io](https://modelcontextprotocol.io/clients).

2. Install dependencies (local development only):

   ```bash
   pip install -r requirements.txt
   ```
   Skip this step if you use `uvx` — it resolves and installs dependencies automatically when launching the server.

3. Authenticate with Telegram (one-time):

   Create a `.env` file in the project root with your Telegram credentials, then run the setup script:

   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   PHONE_NUMBER=+123456789
   ```

   ```bash
   python setup_telegram.py
   ```

4. Run from the console (optional):

   - Console script (installed package):

     ```bash
     fast-mcp-telegram
     # or HTTP test mode
     fast-mcp-telegram --test-mode
     ```

   - Python module (HTTP test mode):

     ```bash
     python3 -m src.server --test-mode
     ```

   - Direct execution (STDIO transport):

     ```bash
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
    - If `chat_id` is provided, you may leave `query` empty to fetch all messages from that chat (optionally filtered by `min_date` and `max_date`).
    - If `chat_id` is not provided (global search), `query` must not be empty.
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

- `generate_links(chat_id: str, message_ids: list[int])`
  - Generate Telegram links for messages

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

- `invoke_mtproto(method_full_name: str, params_json: str)`
 - `search_contacts(query: str, limit: int = 20)`
   - Search contacts using Telegram's native search
 
 - `get_contact_details(chat_id: str)`
   - Get detailed information about a specific contact
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
