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

- `search_messages(query: str, chat_id: str = None, limit: int = 20, offset: int = 0, min_date: str = None, max_date: str = None)`
  - Search for messages in Telegram chats
  - Supports both global search and chat-specific search
  - Supports pagination with `limit` and `offset` parameters
  - Dates should be in ISO format
  - Example:
    ```json
    {
      "tool": "search_messages",
      "params": {
        "query": "hello",
        "limit": 10,
        "offset": 20
      }
    }
    ```

- `advanced_search(query: str, filters: str = None, date_range: str = None, chat_ids: str = None, message_types: str = None, limit: int = 20)`
  - Advanced search with filtering options
  - `filters`, `date_range` should be JSON strings
  - `chat_ids`, `message_types` should be comma-separated strings

- `pattern_search(pattern: str, chat_ids: List[str] = None, pattern_type: str = None, limit: int = None)`
  - Search messages using regex patterns
  - Supports multiple chat IDs
  - Optional pattern type specification

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
