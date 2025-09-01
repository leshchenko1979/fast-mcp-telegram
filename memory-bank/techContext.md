

## Technologies Used

### Core Framework
- **FastMCP**: MCP (Modular Control Platform) server framework
- **Telethon**: Python library for Telegram's MTProto API
- **Python 3.x**: Primary development language
- **asyncio**: For parallel query execution and async operations

### Key Dependencies
```python
# Core dependencies from pyproject.toml (managed by uv)
fastmcp          # MCP server framework
telethon         # Telegram API client
loguru           # Advanced logging
asyncio          # Async/await support (built-in)
```

**Dependency Management**: uv with pyproject.toml and uv.lock for reproducible builds

### Development Tools
- **Cursor IDE**: Primary development environment
- **Git**: Version control
- **Ruff**: Manual code formatting and linting
- **uv**: Package management and virtual environment

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
├── pyproject.toml         # UV dependency configuration
├── uv.lock               # Locked dependencies for reproducible builds
└── .dockerignore         # Docker build exclusions
```

### MCP Server Configuration (Local stdio)
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

### MCP Server Configuration (Cursor over HTTP)
```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://tg-mcp.redevest.ru/mcp",
      "headers": {}
    }
  }
}
```

### Deployment Files
- `Dockerfile`: Multi-stage uv-based build with builder/runtime stages for optimized images
- `pyproject.toml`: UV dependency configuration with project metadata
- `uv.lock`: Locked dependencies for reproducible builds
- `docker-compose.yml`: Traefik labels for `tg-mcp.redevest.ru`, mounts `./mcp_telegram.session -> /data/mcp_telegram.session`, healthcheck via curl, network `traefik-public`
- `scripts/deploy-mcp.sh`: macOS-friendly deploy over SSH, streams git files, copies `.env`, copies session files, composes up with `--env-file .env`

### Env
- `.env` contains `API_ID`, `API_HASH`, `PHONE_NUMBER`, `VDS_USER`, `VDS_HOST`, `VDS_PROJECT_PATH`
  - On server, compose uses `.env`; service env sets `MCP_TRANSPORT=http`, `MCP_HOST=0.0.0.0`, `MCP_PORT=8000`, `SESSION_NAME=/data/mcp_telegram`

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
import asyncio  # For parallel query execution
from src.tools.search import search_messages
from src.tools.messages import send_message, edit_message, read_messages_by_ids
from src.tools.links import generate_telegram_links
from src.tools.mtproto import invoke_mtproto_method
from src.tools.contacts import get_contact_info, search_contacts_telegram
```

### Module Dependencies
- **server.py**: Orchestrates all tool modules
- **search.py**: Core search functionality with multi-query support
- **messages.py**: Message sending, editing, and reading functionality
- **client/connection.py**: Telegram client management
- **utils/entity.py**: Entity resolution utilities
- **utils/message_format.py**: Shared message formatting utilities

## Logging Configuration

### Logging Architecture
```python
# Loguru + stdlib bridge configuration
- Loguru for advanced formatting and features
- InterceptHandler bridges stdlib loggers to Loguru
- Emitter metadata tracking (logger/module/function/line)
- Module-level log level control for spam reduction
```

### Spam Reduction Strategy
```python
# Module-level filtering (src/config/logging.py)
telethon_root = logging.getLogger("telethon")
telethon_root.setLevel(logging.DEBUG)  # Keep important logs

# Noisy submodules set to INFO level
noisy_modules = [
    "telethon.network.mtprotosender",   # _send_loop, _recv_loop, _handle_update
    "telethon.extensions.messagepacker", # packing/debug spam
    "telethon.network",                 # other network internals
]
for name in noisy_modules:
    logging.getLogger(name).setLevel(logging.INFO)
```

### Log Format
```python
# File format with emitter tracking
format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[emitter_logger]}:{extra[emitter_module]}:{extra[emitter_func]}:{extra[emitter_line]} - {message}"

# Console format (shorter time)
format="{time:HH:mm:ss.SSS} | {level:<8} | {extra[emitter_logger]}:{extra[emitter_module]}:{extra[emitter_func]}:{extra[emitter_line]} - {message}"
```

### Performance Impact
- **Before**: 9,000+ DEBUG messages per session, 924KB log files
- **After**: ~16 lines per session, 0 spam phrases
- **Preserved**: Connection, error, and important operation messages
- **Maintained**: Full debugging capability for application code

## Tool Usage Patterns

### Search Tool Parameters
```python
async def search_messages(
    query: str,                    # Search query (comma-separated for multiple terms)
    chat_id: str = None,           # Target chat ID (for per-chat search)
    limit: int = 50,               # Maximum results (limited to prevent context overflow)
    chat_type: str = None,         # Filter by chat type
    min_date: str = None,          # Date range filter
    max_date: str = None,          # Date range filter
    auto_expand_batches: int = 2,  # Auto-expansion for filtered results
    include_total_count: bool = False,  # Include total count in response
)
```

### Multi-Query Search Implementation
```python
# Query normalization
queries: List[str] = [q.strip() for q in query.split(',') if q.strip()] if query else []

# Parallel execution for per-chat search
search_tasks = [
    _search_chat_messages(client, entity, (q or ""), limit, chat_type, auto_expand_batches)
    for q in queries
]
all_partial_results = await asyncio.gather(*search_tasks)

# Parallel execution for global search
search_tasks = [
    _search_global_messages(client, q, limit, min_datetime, max_datetime, chat_type, auto_expand_batches)
    for q in queries if q and str(q).strip()
]
all_partial_results = await asyncio.gather(*search_tasks)
```

### Message Tool Parameters
```python
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
3. **Multi-Query Search**: Use comma-separated terms in single query string
4. **Date-filtered Search**: Use `min_date` and `max_date` parameters
5. **Type-filtered Search**: Use `chat_type` parameter
6. **Message Formatting**: Use `parse_mode` for Markdown or HTML formatting
7. **Contact Resolution**: Use `search_contacts` for contact name to chat_id resolution
8. **Message Editing**: Use `message_id` parameter to edit existing messages
9. **Direct Message Reading**: Use `read_messages` to get specific messages by ID
10. **Search with Count**: Use `include_total_count=True` in search_messages for per-chat searches

### Multi-Query Search Examples
```python
# Multiple terms in single query
search_messages(query="deadline, due date", limit=30)

# Russian terms
search_messages(query="рынок складов, складская недвижимость, warehouse market", limit=50)

# Per-chat multi-query
search_messages(chat_id="-1001234567890", query="launch, release notes")
```

### Performance Considerations
- **Search Limit**: Default limit is 50 results to prevent LLM context window overflow
- **Result Limiting**: Use `limit` parameter to control the number of results returned
- **Auto-expansion**: Limited to 2 additional batches by default to balance completeness with performance
- **Parallel Execution**: Multi-query searches execute simultaneously for better performance
- **Deduplication**: Results automatically deduplicated to prevent duplicates across queries

### LLM Usage Guidelines
- **Start Small**: Begin searches with limit=10-20 for initial exploration
- **Use Filters**: Apply date ranges and chat type filters before increasing limits
- **Avoid Large Limits**: Never request more than 50 results in a single search
- **Result Strategy**: Use limit parameter to control result set size for optimal performance
- **Contact Searches**: Keep contact search limits at 20 or lower (contact results are typically smaller)
- **Performance Impact**: Large result sets can cause context overflow and incomplete processing
- **Multi-Query Efficiency**: Use comma-separated terms for related searches to get unified results

## LLM Optimization Improvements

### Tool Description Optimization (2025-09-01)
- **Problem**: Original tool descriptions were verbose and not optimized for LLM consumption
- **Solution**: Completely rewrote all tool descriptions to be concise yet comprehensive
- **Improvements**:
  - Reduced description length by ~75% while maintaining comprehensiveness
  - Added structured sections (MODES, FEATURES, EXAMPLES, Args)
  - Made examples immediately usable by LLMs
  - Consistent formatting across all tools
  - Clear parameter documentation with defaults

### 'me' Identifier Support (2025-09-01)
- **Enhancement**: Added special handling for 'me' identifier in `get_entity_by_id()` function
- **Purpose**: Direct access to Saved Messages using `chat_id='me'` instead of numeric user ID
- **Benefits**:
  - More reliable Saved Messages access
  - Consistent with Telegram API conventions
  - Works for both reading and searching operations
  - Fallback support for numeric user IDs still available

### Error Logging Improvements (2025-09-01)
- **Enhancement**: Improved error logging for message access failures
- **Changes**:
  - Added detailed warning logs when individual messages are not found
  - Includes request ID, message ID, and chat ID for debugging
  - Proper diagnostic information formatting
  - Better traceability for troubleshooting

### Consistent Error Handling Pattern (2025-09-01)
- **Problem**: Mixed error handling patterns across tools (some raised exceptions, others returned None or empty results)
- **Solution**: Unified structured error response format across all tools
- **Format**: `{"ok": false, "error": "message", "request_id": "id", "operation": "name", "params": {...}}`
- **Implementation**:
  - `get_contact_details`: Returns errors for non-existent contacts
  - `search_contacts`: Returns errors instead of empty lists for no results
  - `search_messages`: Returns errors instead of empty message arrays for no results
  - `read_messages`, `invoke_mtproto`: Already returned structured errors
- **Benefits**:
  - Predictable API responses for all operations
  - Better LLM compatibility with structured error handling
  - Improved debugging with request IDs and operation context
  - Consistent error detection pattern across server.py
  - No more None returns, empty result confusion, or exception propagation to MCP layer

### Tool Description Format Standards
```python
"""
TOOL_NAME: Brief description of functionality.

MODES/FORMATS:
- Key: Value pairs for different operation modes
- Format: Supported input formats
- Type: Different operation types

FEATURES/USAGE:
- Key capability: Brief description
- Usage pattern: How to use effectively

EXAMPLES:
Inline JSON examples showing real usage patterns

Args:
parameter_name: Description with defaults and constraints
"""
```

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
- **Error Handling**: All tools return structured error responses instead of raising exceptions
- **Error Detection**: server.py checks for `{"ok": false, ...}` pattern in responses
- **Documentation**: Tool descriptions must be clear for AI model consumption

### Multi-Query Implementation Constraints
- **Input Format**: Must use comma-separated string format for multiple queries
- **Deduplication**: Based on (chat.id, message.id) tuples for uniqueness
- **Pagination**: Applied after all queries complete and results are merged
- **Performance**: Parallel execution improves efficiency but may hit rate limits with many queries

### Logging Constraints
- **Spam Control**: Must balance debugging visibility with log readability
- **Module Filtering**: Requires understanding of Telethon's internal module structure
- **Emitter Tracking**: Need to preserve original logger metadata for debugging
- **Performance**: Logging overhead must not impact search performance

### Error Handling Constraints
- **Structured Responses**: All tools return `{"ok": false, "error": "message", ...}` instead of raising exceptions
- **Consistent Format**: Error responses include `request_id`, `operation`, and `params` fields
- **Server Detection**: server.py checks `isinstance(result, dict) and "ok" in result and not result["ok"]`
- **Graceful Degradation**: Tools handle errors internally rather than propagating exceptions
- **Request Tracking**: Each operation gets unique request_id for debugging and correlation
