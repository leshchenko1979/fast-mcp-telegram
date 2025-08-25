

## Technologies Used

### Core Framework
- **FastMCP**: MCP (Modular Control Platform) server framework
- **Telethon**: Python library for Telegram's MTProto API
- **Python 3.x**: Primary development language

### Key Dependencies
```python
# Core dependencies from requirements.txt
fastmcp          # MCP server framework
telethon         # Telegram API client
loguru           # Advanced logging
```

### Development Tools
- **Cursor IDE**: Primary development environment
- **Git**: Version control
- **Python venv**: Virtual environment management

## Development Setup

### Environment Configuration
```bash
# Project structure
tg_mcp/
├── src/                    # Source code
│   ├── server.py          # MCP server entry point
│   ├── tools/             # Tool implementations
│   ├── client/            # Telegram client management
│   ├── config/            # Configuration and logging
│   └── utils/             # Utility functions
├── tests/                 # Test suite
├── memory-bank/           # Project documentation
└── requirements.txt       # Dependencies
```

### MCP Server Configuration
```json
{
  "mcpServers": {
    "mcp-telegram": {
      "command": "python3",
      "args": ["/Users/leshchenko/coding_projects/tg_mcp/src/server.py"],
      "cwd": "/Users/leshchenko/coding_projects/tg_mcp",
      "env": {
        "PYTHONPATH": "/Users/leshchenko/coding_projects/tg_mcp"
      }
    }
  }
}
```

## Technical Constraints

### Telegram API Limitations
- **Rate Limiting**: API calls are subject to Telegram's rate limits
- **Session Management**: Requires proper session handling and authentication
- **Search Limitations**: Global search has different capabilities than per-chat search
- **Entity Resolution**: Chat IDs can be in multiple formats (username, numeric ID, channel ID)

### MCP Protocol Constraints
- **Tool Registration**: All tools must be properly registered with FastMCP
- **Async Operations**: All Telegram operations must be async
- **Error Handling**: Errors must be properly propagated to MCP clients
- **Documentation**: Tool descriptions must be clear for AI model consumption

## Dependencies and Imports

### Import Structure
```python
# Server imports
from fastmcp import FastMCP
from src.tools.search import search_messages
from src.tools.messages import send_message, edit_message, read_messages_by_ids
from src.tools.links import generate_telegram_links
from src.tools.mtproto import invoke_mtproto_method
from src.tools.contacts import get_contact_info, search_contacts_telegram
```

### Module Dependencies
- **server.py**: Orchestrates all tool modules
- **search.py**: Core search functionality
- **messages.py**: Message sending, editing, and reading functionality
- **client/connection.py**: Telegram client management
- **utils/entity.py**: Entity resolution utilities
- **utils/message_format.py**: Shared message formatting utilities

## Tool Usage Patterns

### Search Tool Parameters
```python
async def search_messages(
    query: str,                    # Search query (can be empty for chat_id searches)
    chat_id: str = None,           # Target chat ID (for per-chat search)
    limit: int = 50,               # Maximum results (limited to prevent context overflow)
    offset: int = 0,               # Pagination offset
    chat_type: str = None,         # Filter by chat type
    min_date: str = None,          # Date range filter
    max_date: str = None,          # Date range filter
    auto_expand_batches: int = 2,  # Auto-expansion for filtered results
    include_total_count: bool = False,  # Include total count in response
)


```

async def send_or_edit_message(
    chat_id: str,                  # Target chat ID
    message: str,                  # Message text
    reply_to_msg_id: int = None,   # Reply to specific message (only for sending)
    parse_mode: str = None,        # Formatting mode (None, 'md', 'html')
    message_id: int = None,        # Message ID to edit (if provided, edits instead of sending)
)
```

### Key Usage Scenarios
1. **Per-chat Search**: `chat_id` provided, `query` optional
2. **Global Search**: `chat_id` not provided, `query` required
3. **Date-filtered Search**: Use `min_date` and `max_date` parameters
4. **Type-filtered Search**: Use `chat_type` parameter
5. **Message Formatting**: Use `parse_mode` for Markdown or HTML formatting
6. **Contact Resolution**: Use `search_contacts` for contact name to chat_id resolution
7. **Message Editing**: Use `message_id` parameter to edit existing messages
8. **Direct Message Reading**: Use `read_messages` to get specific messages by ID
9. **Search with Count**: Use `include_total_count=True` in search_messages for per-chat searches

### Performance Considerations
- **Search Limit**: Default limit is 50 results to prevent LLM context window overflow
- **Pagination**: Use `offset` parameter for accessing additional results beyond the limit
- **Auto-expansion**: Limited to 2 additional batches by default to balance completeness with performance

### LLM Usage Guidelines
- **Start Small**: Begin searches with limit=10-20 for initial exploration
- **Use Filters**: Apply date ranges and chat type filters before increasing limits
- **Avoid Large Limits**: Never request more than 50 results in a single search
- **Pagination Strategy**: Use offset parameter to access additional results when needed
- **Contact Searches**: Keep contact search limits at 20 or lower (contact results are typically smaller)
- **Performance Impact**: Large result sets can cause context overflow and incomplete processing

## Development Workflow

### Testing
- **Unit Tests**: Located in `tests/` directory
- **Integration Tests**: Test MCP server functionality
- **Manual Testing**: Using Cursor IDE with MCP client

### Deployment
- **Local Development**: Using stdio transport
- **HTTP Server**: For testing with HTTP transport
- **Production**: MCP server runs as part of Cursor IDE

## Technical Constraints and Limitations

### Telegram API Limitations
- **Rate Limiting**: API calls are subject to Telegram's rate limits
- **Search Limitations**: Global search has different capabilities than per-chat search
- **Entity Resolution**: Chat IDs can be in multiple formats (username, numeric ID, channel ID)
- **Session Management**: Requires proper session handling and authentication

### MCP Protocol Constraints
- **Tool Registration**: All tools must be properly registered with FastMCP
- **Async Operations**: All Telegram operations must be async
- **Error Handling**: Errors must be properly propagated to MCP clients
- **Documentation**: Tool descriptions must be clear for AI model consumption


