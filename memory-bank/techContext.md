
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
loguru           # Advanced logging
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
- **pytest-cov**: Coverage reporting and analysis
- **pytest-xdist**: Parallel test execution for CI/CD
- **pip**: Package management and installation

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
├── tests/                # Comprehensive test suite
│   ├── __init__.py       # Tests package initialization
│   ├── conftest.py       # Shared fixtures and configuration
│   ├── test_*.py         # Organized test modules by functionality
│   └── README.md         # Test documentation and guidelines
├── memory-bank/          # Project documentation
├── pyproject.toml       # Project configuration and dependencies
├── docker-compose.yml   # Production Docker configuration
├── Dockerfile          # Multi-stage pip build
├── .env                # Environment variables (create this)
├── .gitignore          # Git ignore patterns
└── .dockerignore       # Docker build exclusions
```

### MCP Server Configuration (STDIO Mode - Development with Cursor IDE)
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

### MCP Server Configuration (HTTP_NO_AUTH Mode - Development HTTP Server)
```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8000"
    }
  }
}
```

### MCP Server Configuration (HTTP_AUTH Mode - Production with Bearer Token)
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

### Configuration System
- **ServerConfig**: Centralized server configuration with pydantic-settings
- **Three Server Modes**: stdio (development), http-no-auth (dev server), http-auth (production)
- **Automatic CLI Parsing**: Native pydantic-settings CLI parsing with kebab-case conversion
- **Smart Defaults**: Host binding and authentication behavior based on server mode
- **SetupConfig**: Dedicated setup configuration separate from server configuration
- **Backward Compatibility**: settings.py imports from server_config for legacy support
- **Environment Template**: Comprehensive .env.example with all configuration options
- **Docker Integration**: docker-compose.yml and deploy script updated for new configuration system

### Web Setup & Runtime Config
- **Templates/HTMX**: Jinja2 templates in `src/templates` power the browser setup flow
- **Entry Point**: `/setup` launches phone → code/2FA → config (success step skipped)
- **DOMAIN**: Runtime domain for generated `mcp.json`, taken from `DOMAIN` env
- **Setup Session TTL**: `SETUP_SESSION_TTL_SECONDS` (default 900s) cleans temp `setup-*.session`

### Environment Variables for Server Configuration
```bash
# Server mode (determines transport and authentication behavior)
SERVER_MODE=stdio        # stdio (development), http-no-auth (dev server), http-auth (production)

# Network configuration (for HTTP modes)
HOST=127.0.0.1          # Bind address (auto-adjusts: 127.0.0.1 for stdio, 0.0.0.0 for HTTP)
PORT=8000               # Port for HTTP transport

# Session management
MAX_ACTIVE_SESSIONS=10  # LRU cache limit for concurrent sessions
SESSION_DIR=            # Custom session directory (defaults to ~/.config/fast-mcp-telegram/)

# Telegram API credentials (for setup)
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+123456789

# Web setup configuration
DOMAIN=your-domain.com  # Domain for web setup and config generation
```

### Testing Infrastructure
- **pytest Framework**: Comprehensive testing with async support and fixtures
- **Test Organization**: Scalable structure with logical separation of test modules by functionality
- **Shared Fixtures**: `conftest.py` provides reusable test setup (mock_client, test_server, client_session)
- **Coverage Analysis**: Automated coverage reporting with multiple output formats
- **Parallel Execution**: Support for concurrent test execution in CI/CD environments
- **Mock Infrastructure**: Comprehensive mocking for external dependencies and APIs
- **Async Testing**: Full async/await support for modern Python concurrency patterns
- **Comprehensive Test Coverage**: Systematic testing of core functionality and edge cases

### Deployment Files
- `Dockerfile`: Optimized pip-based build with proper user permissions
- `pyproject.toml`: Comprehensive dependency configuration with setuptools and pytest settings
- `docker-compose.yml`: Production configuration with Traefik labels, health checks, and session persistence
- `scripts/deploy-mcp.sh`: Enhanced deployment script with session backup/restore, permission auto-fixing, macOS resource fork cleanup, and detailed progress logging
- `.gitignore`: Git ignore patterns for logs, cache files, and environment variables
- `.dockerignore`: Comprehensive exclusions for optimized container builds

### Env
- `.env` contains `API_ID`, `API_HASH`, `PHONE_NUMBER`, `VDS_USER`, `VDS_HOST`, `VDS_PROJECT_PATH`
- **Automatic Loading**: setup_telegram.py automatically loads .env files from the project directory
- **Seamless Authentication**: Users can create .env files and run setup without manual credential entry
- **Path Resolution**: Script searches for .env files relative to the project root directory
- **User Feedback**: Provides confirmation when .env file is successfully loaded
- On server, compose uses `.env`; service env sets `MCP_TRANSPORT=http`, `MCP_HOST=0.0.0.0`, `MCP_PORT=8000`
- Session files stored in persistent user config directory (~/.config/fast-mcp-telegram/) for cross-platform compatibility

### VDS Testing Environment
- **Production Server**: VDS at `<VDS_IP>` with Traefik reverse proxy
- **Domain**: `<DOMAIN>` with SSL certificates via Let's Encrypt
- **Container Management**: Docker Compose with health checks and automatic restarts
- **Session Persistence**: Automatic backup/restore of session files across deployments
- **Authentication Testing**: Real Telegram API calls with bearer token authentication
- **Log Monitoring**: Real-time log analysis for authentication flow verification
- **Health Monitoring**: Container health checks and `/health` endpoint monitoring
- **Traefik Integration**: Domain routing, SSL termination, and load balancing

### VDS Testing Commands
- **SSH Access**: `ssh root@<VDS_IP>` (credentials from `.env` file)
- **Deployment**: `./scripts/deploy-mcp.sh` (automated with session management)
- **Container Status**: `ssh root@<VDS_IP> "cd /opt/fast-mcp-telegram && docker compose ps"`
- **Container Logs**: `ssh root@<VDS_IP> "cd /opt/fast-mcp-telegram && docker compose logs --tail=20 fast-mcp-telegram"`
- **Health Check**: `curl -X GET "https://<DOMAIN>/health" --insecure`

## Technical Constraints

### Telegram API Limitations
- **Rate Limiting**: API calls are subject to Telegram's rate limits
- **Session Management**: Requires proper session handling and authentication
- **Search Limitations**: Global search has different capabilities than per-chat search
- **Entity Resolution**: Chat IDs can be in multiple formats (username, numeric ID, channel ID)

### Session Management Architecture
- **Storage Location**: Persistent user config directory (~/.config/fast-mcp-telegram/) for cross-platform compatibility
- **Automatic Permissions**: Container user (1000:1000) access automatically configured
- **Cross-Platform Support**: Handles macOS resource forks and permission differences
- **Deployment Persistence**: Sessions automatically backed up and restored across deployments
- **Git Security**: Session files excluded from version control for security

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
- **Loguru + stdlib bridge**: Advanced formatting and features
- **InterceptHandler**: Bridges stdlib loggers to Loguru
- **Emitter metadata tracking**: logger/module/function/line
- **Module-level log level control**: For spam reduction

### Spam Reduction Strategy
- **Telethon root logger**: Set to DEBUG for important logs
- **Noisy submodules**: Set to INFO level (mtprotosender, messagepacker, network)
- **Performance Impact**: Reduced from 9,000+ to ~16 lines per session

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

## Development Workflow

### Testing
- **Unit Tests**: Located in `tests/` directory
- **Integration Tests**: Test MCP server functionality
- **Manual Testing**: Using Cursor IDE with MCP client

### Deployment
- **Local Development**: Using stdio transport
- **HTTP Server**: For testing with HTTP transport
- **Production**: MCP server runs as part of Cursor IDE

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
- **Production Requirement**: Without this parameter, authentication decorators are bypassed, causing fallback to default sessions