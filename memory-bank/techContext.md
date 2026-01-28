## Technologies Used

### Core Framework
- **FastMCP**: MCP (Modular Control Platform) server framework
- **Telethon**: Python library for Telegram's MTProto API
- **Python 3.x**: Primary development language
- **asyncio**: For parallel query execution and async operations

### Key Dependencies
```python
# Core dependencies from pyproject.toml (managed by setuptools)
fastmcp          # MCP server framework
telethon         # Telegram API client
# Logging handled by Python stdlib
asyncio          # Async/await support (built-in)
aiohttp          # HTTP transport for MCP
python-dotenv    # Environment variable management
```

**Dependency Management**: setuptools with pyproject.toml for package management
**Version Management**: Single source of truth in `src/_version.py` with direct import approach
**Session Management**: Session files stored in persistent user config directory (~/.config/fast-mcp-telegram/)
**Cross-Platform Support**: Automatic handling of macOS resource forks and permission differences

### Development Tools
- **Cursor IDE**: Primary development environment
- **Git**: Version control
- **Ruff**: Code formatting and linting
- **pytest**: Comprehensive testing framework with async support

## Development Setup

### Environment Configuration
```bash
# Project structure
tg_mcp/
├── src/                   # Source code
│   ├── server.py         # MCP server entry point with authentication middleware
│   ├── _version.py       # Version information (single source of truth)
│   ├── tools/            # Tool implementations (all with @with_auth_context)
│   ├── client/           # Telegram client management with token-based sessions
│   │   └── connection.py # Token management, LRU cache, session isolation
│   ├── config/           # Configuration and logging
│   └── utils/            # Utility functions
├── scripts/               # Deployment and utility scripts
│   └── deploy-mcp.sh     # Enhanced deployment script
```

### Testing Infrastructure
- **Comprehensive Test Suite**: 140+ tests covering all functionality
- **Async Test Support**: pytest-asyncio for coroutine testing
- **Coverage Reporting**: pytest-cov for test coverage analysis
- **Parallel Execution**: pytest-xdist for faster test runs
- **Test Organization**: Separate test files for each module with clear naming

## Tool Usage Patterns

### Authentication Pattern
```python
# All tools use this exact pattern for consistency
@handle_telegram_errors(operation="tool_name", params_func=extract_params)
@with_auth_context  # Must be innermost decorator
async def tool_function(token: str, ...) -> dict:
    # Function body
```

### Error Handling Pattern
```python
# Consistent error response format across all tools
return log_and_build_error(
    operation="tool_name",
    error_message="Human readable message",
    params=params,
    exception=original_exception,
)
```

### Session Management
- **Token-Based Sessions**: Each bearer token maps to isolated session file
- **LRU Cache**: Recently used sessions cached in memory for performance
- **Automatic Cleanup**: Failed sessions automatically removed and recreated
- **Cross-Server Isolation**: HTTP_AUTH mode uses random tokens; STDIO uses configured names

## Server Modes

### Three Server Modes
1. **stdio**: Local development, direct process communication
2. **http-no-auth**: HTTP transport without authentication (development only)
3. **http-auth**: Production HTTP transport with bearer token authentication

### Configuration System
- **Pydantic Settings**: Modern configuration with validation and defaults
- **Multiple Sources**: CLI args, environment variables, .env files, config files
- **Smart Defaults**: Mode-appropriate behavior and validation
- **Runtime Overrides**: DOMAIN and other settings configurable at runtime

## Message Processing

### Message Format
- **Consistent Structure**: All message results follow same schema
- **Media Placeholders**: LLM-friendly media representations instead of raw objects
- **Reply Markup**: Automatic extraction of keyboard and inline buttons
- **Forward Information**: Structured forwarded message metadata

### Search Architecture
- **Parallel Execution**: Multiple queries run concurrently for performance
- **Deduplication**: Smart deduplication by message ID across queries
- **Pagination**: Conservative has_more logic prevents missed messages
- **Filtering**: Chat type, public visibility, and date range filtering

## Deployment

### Development
- **Local Development**: Using stdio transport
- **HTTP Server**: For testing with HTTP transport

### Production
- **VDS Deployment**: Containerized with Traefik and TLS
- **Session Persistence**: Zero-downtime deployments with automatic backup/restore
- **Health Monitoring**: HTTP `/health` endpoint for session statistics

## Technical Constraints

### Telegram API Limitations
- **Rate Limiting**: API calls are subject to Telegram's rate limits
- **Search Limitations**: Global search has different capabilities than per-chat search
- **Entity Resolution**: Chat IDs can be in multiple formats (username, numeric ID, channel ID)
- **Session Management**: Requires proper session handling and authentication

### MCP Protocol Constraints
- **Tool Registration**: All tools must be properly registered with FastMCP
- **Async Operations**: All Telegram operations must be async
- **Error Handling**: All tools return structured error responses instead of raising exceptions
- **Documentation**: Tool descriptions must be clear for AI model consumption

### FastMCP Authentication Constraints
- **Critical Parameter**: `stateless_http=True` is **REQUIRED** for FastMCP to properly execute the `@with_auth_context` decorator in HTTP transport mode
- **Decorator Order**: `@with_auth_context` must be the innermost decorator on all tool functions
- **HTTP Transport**: Authentication middleware only works correctly with `stateless_http=True` parameter