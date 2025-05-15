# MCP Telegram Server

A powerful MCP server implementation that provides Telegram functionality through a clean API interface, including message search, sending, and chat management capabilities.

Join our [Telegram Discussion Group](https://t.me/mcp_telegram) for support, updates, and community discussions.

## Features

- Message search with multiple modes:
  - Basic search by text
  - Advanced search with custom filters
  - Pattern-based search using regex
- Chat management:
  - List available dialogs
  - Send messages with optional reply support
  - Generate message links
- Analytics and data:
  - Chat statistics and analytics
  - Chat data export functionality
- Robust error handling and logging
- Built on MCP (Model Control Protocol) architecture

## Prerequisites

- Python 3.x
- Telegram API credentials (API ID, API Hash)
- MCP-compatible environment (like Cursor IDE)

## Installation

1. Clone the repository and navigate to the project directory:
```bash
git clone https://github.com/leshchenko1979/tg_mcp.git
cd tg_mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your Telegram credentials:
```env
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+123456789
```

4. Run the setup script to authenticate with Telegram:
```bash
python setup_telegram.py
```

This will create a session file (`mcp_telegram_search.session`) that stores your Telegram session data.

## Cursor Configuration

To use this server with Cursor IDE:

1. Create an `mcp.json` file in your `.cursor` directory with the following content:
```json
{
  "mcpServers": {
    "mcp-telegram": {
      "command": "cmd /c set PYTHONPATH=%PYTHONPATH%;<path_to_server> && mcp run <path_to_server>/src/server.py",
      "description": "Telegram MCP server"
    }
  }
}
```

Note: Replace `<path_to_server>` with the absolute path to your installation directory.

2. Ensure your `.env` file is properly configured as described in the Installation section.

3. The server will automatically connect to Cursor when you open the project, making all Telegram tools available through the IDE.

Note: If you modify the server code, you'll need to reload the server in Cursor for changes to take effect.

## Usage

The server can be run using MCP:

```bash
mcp run <path_to_server>/server.py
```

## Available Tools

The server provides the following MCP tools:

- `search_messages(query: str, chat_id: str = None, limit: int = 20, offset: int = 0, chat_type: str = None, min_date: str = None, max_date: str = None, auto_expand_batches: int = 2)`
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
  - Example (search in private chats for messages in May 2024):
    ```json
    {
      "tool": "search_messages",
      "params": {
        "query": "warehouse",
        "limit": 10,
        "chat_type": "private",
        "min_date": "2024-05-01",
        "max_date": "2024-05-31",
        "auto_expand_batches": 2
      }
    }
    ```

- `send_telegram_message(chat_id: str, message: str, reply_to_msg_id: int = None, parse_mode: str = None)`
  - Send messages to Telegram chats
  - Supports replying to messages
  - Optional markdown/HTML parsing

- `get_dialogs(limit: int = 50, offset: int = 0)`
  - List available Telegram dialogs
  - Supports pagination with `limit` and `offset` parameters
  - Returns chat IDs, names, types, and unread counts
  - Example:
    ```json
    {
      "tool": "get_dialogs",
      "params": {
        "limit": 10,
        "offset": 30
      }
    }
    ```

- `get_statistics(chat_id: str)`
  - Get statistics for a specific chat

- `generate_links(chat_id: str, message_ids: list[int])`
  - Generate Telegram links for messages

- `export_data(chat_id: str, format: str = "json")`
  - Export chat data in specified format

## Example Use Cases & AI Agent Requests

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
      "tool": "send_telegram_message",
      "params": {
        "chat_id": "123456789",
        "message": "Summary of the current warehouse market situation (2025):\n\n- The volume of new warehouse construction in Russia reached a record 1.2 million sq.m in Q1 2025, a 12% increase year-over-year, mainly due to high demand in previous years. However, forecasts indicate a 29% year-over-year decrease in new warehouse supply in Moscow and the region by the end of 2026, down to 1.2 million sq.m, due to high financing costs and rising construction expenses.\n- Developers are increasingly shifting from speculative projects to build-to-suit and owner-occupied warehouses, with many taking a wait-and-see approach.\n- The share of e-commerce companies among tenants has dropped sharply (from 57% to 15-34%), while the share of logistics, transport, and distribution companies is growing.\n- Despite a drop in demand and a slight increase in vacancy (up to 2-4%), rental rates for class A warehouses continue to rise.\n- Regional expansion of retailers has led to record-high new supply, with the Moscow region remaining the leader (44% of new supply in Q1 2025).\n- The market is experiencing a cooling after several years of rapid growth, but there is potential for renewed activity if monetary policy eases.\n\nIf you need more details or analytics, let me know!"
      }
    }
    ```


These examples illustrate how natural language requests can be mapped to MCP tool calls for powerful Telegram automation and search.

## Project Structure

```
tg_mcp/
├── src/                # Source code directory
│   ├── client/        # Telegram client management
│   ├── config/        # Configuration settings
│   ├── monitoring/    # Monitoring and health checks
│   ├── tools/         # MCP tool implementations
│   ├── utils/         # Utility functions
│   ├── __init__.py    # Package initialization
│   └── server.py      # Main server implementation
├── tests/             # Test directory
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
loguru          # Logging
aiohttp         # Async HTTP
mcp[cli]        # Model Control Protocol
telethon>=1.34.0  # Telegram client
python-dotenv>=1.0.0  # Environment management
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
