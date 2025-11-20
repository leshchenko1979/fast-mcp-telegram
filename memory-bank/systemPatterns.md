## Architecture Overview
The fast-mcp-telegram system follows a modular MCP server architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   FastMCP       │    │   Telegram API  │
│   (AI Model)    │◄──►│   Server        │◄──►│   (Telethon)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                             │
                      ┌─────────────────┐
                      │   Tool Modules  │
                      │   (search, etc) │
                      └─────────────────┘
```

## Key Technical Decisions

### 1. Configuration Architecture (Updated 2025-10-11)
- **ServerConfig Class**: Centralized server configuration with pydantic-settings
- **Three Server Modes**: Clear enum-based modes (stdio, http-no-auth, http-auth)
- **Automatic CLI Parsing**: Native pydantic-settings CLI parsing with kebab-case conversion
- **Smart Defaults**: Host binding and authentication behavior based on server mode
- **Unified Session Configuration**: SetupConfig inherits from ServerConfig for consistent session management
- **Session Name Control**: `session_name` field (default: "telegram") configurable via CLI/env/dotenv
- **Session Path Property**: `session_path` combines `session_directory` and `session_name`
- **Configuration Priority**: CLI args → env vars → .env file → defaults
- **Backward Compatibility**: settings.py imports from server_config for legacy support

### 2. Authentication Architecture
- **Token-Based Sessions**: Bearer tokens create isolated user sessions
- **Context Variables**: `_current_token` for request-scoped authentication
- **LRU Cache Management**: Configurable `MAX_ACTIVE_SESSIONS` with automatic eviction
- **Transport-Specific Auth**: Mandatory for HTTP, optional for stdio (legacy)
- **Session File Format**: `{token}.session` for multi-user isolation
- **Authentication Middleware**: `@with_auth_context` decorator on all MCP tools

### 2.1. Connection Management Architecture (2025-10-17)
- **Exponential Backoff**: Intelligent retry delays (2^failure_count seconds, max 60s) to prevent connection storms
- **Circuit Breaker Pattern**: Opens after 5 failures in 5 minutes, preventing futile reconnection attempts
- **Session Health Monitoring**: Tracks failure counts, timestamps, and connection quality per token
- **Automatic Session Cleanup**: Removes failed sessions after 10+ failures and 1+ hour of inactivity
- **Connection Failure Tracking**: `_connection_failures` dict tracks (failure_count, last_failure_time) per token
- **Health Statistics**: Real-time monitoring of connection failures and session health via `/health` endpoint
- **Error Detection**: Enhanced error handling for "wrong session ID" and other connection issues
- **Session Restoration**: Preserves bearer tokens while allowing fresh session data replacement

### 3. Server Mode Architecture
- **STDIO Mode**: Development with Cursor IDE (no auth, default session only)
- **HTTP_NO_AUTH Mode**: Development HTTP server (auth disabled)
- **HTTP_AUTH Mode**: Production HTTP server (auth required)
- **Transport Selection**: Automatic transport selection based on server mode
- **Host Binding**: Smart defaults (127.0.0.1 for stdio, 0.0.0.0 for HTTP)

### 4. MTProto Architecture (2025-10-02)
- **Unified Implementation**: Single `invoke_mtproto_impl()` function for all MTProto operations
- **Interface Unification**: MCP tool and HTTP bridge use identical behavior and defaults
- **Method Normalization**: Automatic conversion of method names to proper Telegram API format
- **Dangerous Method Protection**: Centralized protection with configurable override
- **Entity Resolution**: Automatic resolution of usernames, IDs, and phone numbers
- **Parameter Sanitization**: Security validation and cleanup of all parameters
- **Single Source of Truth**: All MTProto logic centralized in one function

### 5. Search Architecture
- **Dual Search Modes**: Global search vs per-chat search
- **Multi-Query Support**: Comma-separated terms with parallel execution
- **Query Handling**: Different logic for empty vs non-empty queries
- **Entity Resolution**: Automatic chat ID resolution from various formats
- **Deduplication**: Results merged and deduplicated based on message identity

### 6. Public Visibility Filtering Architecture (2025-11-19)
- **Boolean Parameter Design**: `public: bool | None` where `True`=discoverable (has username), `False`=invite-only (no username), `None`=no filtering
- **Private Chat Protection**: Private chats (User entities) are never filtered by the `public` parameter - they always appear regardless of username presence
- **Selective Filtering**: Groups and channels are filtered normally by username presence, but private chats bypass this filtering entirely
- **User Experience**: Prevents confusing scenarios where direct message contacts disappear from search results
- **Architectural Rule**: "Private chats should never be filtered by visibility" - implemented in `_matches_public_filter()` function
- **Cross-Tool Consistency**: Same filtering logic applied to both `search_messages_globally` and `find_chats` tools

### 7. Code Quality Patterns (2025-10-02)
- **DRY Principle**: Eliminated code duplication across files and functions
- **Single Responsibility**: Each function has one clear purpose
- **Centralized Constants**: Shared constants in single locations
- **Clear Function Boundaries**: Logical separation without artificial barriers
- **Consistent Error Handling**: Standardized error response patterns
- **Section Organization**: Clear section headers and logical grouping
- **Helper Function Extraction**: Focused helper functions for specific tasks

### 7.1. Performance Optimization Patterns (2025-10-02)
- **functools.cache Usage**: Applied to pure functions for automatic caching and memory management
- **Telethon Function Mapping**: Cached module introspection for case-insensitive method resolution
- **Entity Processing**: Cached entity type normalization and dictionary building for repeated operations
- **Async Caching Strategy**: Manual caching for async operations where functools.cache doesn't work well
- **Thread Safety**: functools.cache provides built-in thread safety for concurrent operations
- **Memory Management**: Automatic cache eviction and memory management without manual intervention

### 8. Uniform Entity Schema (2025-09-17)
- All tools format chat/user data via `utils.entity.build_entity_dict`
- Schema: `id`, `title`, `type` (private|group|channel), `username`, `first_name`, `last_name`
- Counts: `members_count` for groups, `subscribers_count` for channels (opportunistic in builder; guaranteed via async helper)
- `title` fallback: explicit title → full name → `@username`
- Quick lookup tools (e.g., `find_chats`) return lightweight schema; detailed info via `get_chat_info` uses async helper to enrich with counts and `about`/`bio`

### 9. Multi-Query Implementation
- **Input Format**: Single string with comma-separated terms (e.g., "deadline, due date")
- **Parallel Execution**: `asyncio.gather()` for simultaneous query processing
- **Deduplication Strategy**: `(chat.id, message.id)` tuple-based deduplication
- **Pagination**: Applied after all queries complete and results are merged

### 10. Tool Registration Pattern
- **FastMCP Integration**: Uses FastMCP framework for MCP compliance
- **Module Registration**: Tools registered via `src/server_components/tools_register.register_tools(mcp)`
- **Async Operations**: All Telegram operations are async for performance
- **Error Handling**: All tools return structured error responses instead of raising exceptions
- **Literal Parameter Constraints**: Uses `typing.Literal` to constrain parameter values and guide LLM choices

### 11. Data Flow Patterns
```
User Request → MCP Tool → Search Function → Telegram API → Results → Response
```

### 12. Authentication Flow
```
HTTP Request → extract_bearer_token() → @with_auth_context → set_request_token() → _get_client_by_token() → Session Cache/New Session → Tool Execution
```

### 13. Multi-Query Search Flow
```
Input: "term1, term2, term3"
     ↓
Split into individual queries
     ↓
Create parallel search tasks
     ↓
Execute with asyncio.gather()
     ↓
Merge and deduplicate results
     ↓
Apply limit (no pagination)
     ↓
Return unified result set
```

### 14. Session Management Architecture (Updated 2025-10-11)
- **Unified Configuration**: ServerConfig and SetupConfig share session configuration (session_name, session_directory)
- **Session Name Control**: `session_name` field configurable via CLI/env/dotenv (default: "telegram")
- **Session Path Property**: `session_path = session_directory / session_name` (computed property)
- **Mode-Specific Behavior**:
  - **STDIO/HTTP_NO_AUTH**: Use `{session_name}.session` (default: `telegram.session`)
  - **HTTP_AUTH**: Use `{bearer_token}.session` (one per authenticated user)
- **Token-Based Sessions**: Each Bearer token gets isolated session file in HTTP_AUTH mode
- **LRU Cache Management**: In-memory cache with configurable `MAX_ACTIVE_SESSIONS` limit
- **Automatic Eviction**: Oldest sessions disconnected when cache reaches capacity
- **Session Location**: `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Multi-Account Support**: Use SESSION_NAME to manage multiple Telegram accounts
- **Configuration Priority**: CLI args → env vars → .env file → defaults
- **Auto-Cleanup on Auth Errors**: Invalid session files automatically deleted
- **Git Integration**: Proper .gitignore with .gitkeep for structure maintenance
- **Cross-Platform**: Automatic handling of macOS resource forks and permission differences
- **Permission Auto-Fix**: Automatic chown/chmod for container user access (1000:1000)
- **Backup/Restore**: Comprehensive session persistence across deployments

### 15. Professional Testing Infrastructure
- **Test Framework**: Modern pytest-based testing with comprehensive async support
- **Test Organization**: Scalable structure with logical separation of test modules by functionality
- **Shared Fixtures**: Centralized test setup and reusable fixtures for consistent testing
- **Coverage Analysis**: Automated coverage reporting with multiple output formats
- **Parallel Execution**: Support for concurrent test execution in CI/CD pipelines
- **Mock Infrastructure**: Comprehensive mocking for external dependencies and APIs
- **Async Testing**: Full async/await support for modern Python concurrency patterns

### 16. Deployment & Transport
- Transport: Streamable HTTP with SSE mounted at `/mcp`
- Ingress: Traefik `websecure` with Let's Encrypt, configurable router domain
- CORS: Permissive during development for Cursor compatibility
- Sessions: Standard `~/.config/fast-mcp-telegram/` directory with automatic permission management
- Volume Mounting: Standard user config directory mounts
- Web Setup: HTMX/Jinja2 templates under `src/templates`, routes: `/setup`, `/setup/phone`, `/setup/verify`, `/setup/2fa`, `/setup/generate`, `/download-config/{token}`
- Setup Session Cleanup: Opportunistic TTL-based cleanup (default 900s) for temporary `setup-*.session` files

### 17. Web Setup Interface Architecture
- **HTMX Integration**: Dynamic form updates with `hx-target="#step"` for seamless UX
- **Template Structure**: Base template with fragment-based form components
- **Visual Hierarchy**: Larger interactive elements (1.1rem inputs, 1rem buttons) with smaller instructional text (0.85rem)
- **Clean Layout**: Minimal text, no empty visual elements, progressive disclosure
- **Error Handling**: Context-specific error messages with retry capability
- **Session Management**: TTL-based setup session cleanup with automatic resource management

### 18. Logging Strategy
- Loguru: File rotation + console with structured logging
- Bridged Loggers: `uvicorn`, `uvicorn.access`, and `telethon` redirected into Loguru at DEBUG
- Modular Architecture: Dedicated `logging_utils.py` for logging functions, `error_handling.py` for error management
- Parameter Sanitization: Automatic phone masking, content truncation, and security enhancements
- Request ID Tracking: Enhanced logging with optional request ID support for operation correlation
- Traceability: Detailed RPC traces enabled for production diagnosis with flattened error structures

### 19. Deployment Automation Patterns
- **Session Backup**: Automatic backup of `~/.config/fast-mcp-telegram/*` before deployment
- **Permission Management**: Auto-fix ownership (1000:1000) and permissions (664/775)
- **Cross-Platform Cleanup**: Automatic removal of macOS resource fork files (._*)
- **Git-Aware Transfer**: Exclude sessions directory from git transfers for security
- **Local-Remote Sync**: Bidirectional synchronization of session files
- **Error Recovery**: Robust error handling with detailed logging and counts

### 20. VDS Testing and Diagnosis Methodology
- **Environment Access**: SSH connection using credentials from `.env` file (`VDS_USER`, `VDS_HOST`, `VDS_PROJECT_PATH`)
- **Deployment Process**: Automated deployment via `./scripts/deploy-mcp.sh` with session management and health checks
- **Container Management**: Docker Compose commands for status monitoring, log analysis, and health verification
- **Authentication Testing**: Curl-based testing with proper MCP protocol headers and bearer token authentication
- **Log Analysis**: Real-time monitoring of server logs for authentication flow, token extraction, and session creation
- **Session File Management**: Verification of token-specific session files in `~/.config/fast-mcp-telegram/` directory
- **Traefik Integration**: Domain routing verification and SSL certificate management through Traefik logs
- **Health Monitoring**: Container health checks and `/health` endpoint monitoring for system status
- **Production Validation**: End-to-end testing with real Telegram API calls to confirm functionality
- **Debugging Approach**: Systematic issue elimination through targeted testing and log analysis

## Critical Implementation Paths

### Search Flow
1. **Input Validation**: Check query and chat_id parameters
2. **Query Normalization**: Split comma-separated terms into individual queries
3. **Mode Selection**: Determine global vs per-chat search
4. **Entity Resolution**: Convert chat_id to Telegram entity
5. **Parallel Execution**: Create and execute search tasks for each query
6. **Result Processing**: Merge, deduplicate, and format results

### Web Setup Authentication Flow
1. **Phone Submission**: User enters phone number, system sends verification code
2. **Code Verification**: User enters code, system validates and checks for 2FA requirement
3. **2FA Handling**: If required, user enters 2FA password, system validates
4. **Config Generation**: System generates MCP configuration with bearer token
5. **Session Cleanup**: Temporary setup sessions cleaned up via TTL

### Current Search Logic
```python
# Query normalization
queries: List[str] = [q.strip() for q in query.split(',') if q.strip()] if query else []

if chat_id:
    # Per-chat search: Search within specific chat
    entity = await get_entity_by_id(chat_id)
    search_tasks = [
        _search_chat_messages(client, entity, (q or ""), limit, chat_type, auto_expand_batches)
        for q in queries
    ]
    all_partial_results = await asyncio.gather(*search_tasks)
    # Merge and deduplicate results
else:
    # Global search: Search across all chats
    search_tasks = [
        _search_global_messages(client, q, limit, min_datetime, max_datetime, chat_type, auto_expand_batches)
        for q in queries if q and str(q).strip()
    ]
    all_partial_results = await asyncio.gather(*search_tasks)
    # Merge and deduplicate results
```

## Component Relationships

### Core Modules
- **server.py**: MCP server entry point; registers routes and tools on startup
- **server_components/health.py**: Health endpoint registrar; `register_health_routes(mcp)`
- **server_components/web_setup.py**: Web setup routes registrar; `register_web_setup_routes(mcp)`
- **server_components/tools_register.py**: Tool registrar; `register_tools(mcp)`
- **search.py**: Search functionality implementation with multi-query support
- **client/connection.py**: Telegram client management with token-based sessions and LRU cache
- **utils/entity.py**: Entity resolution and formatting
- **utils/logging_utils.py**: Consolidated logging utilities with operation tracking and request ID support
- **utils/mcp_config.py**: Shared MCP configuration generation for CLI and web setup (2025-10-11)
- **config/settings.py**: Configuration management with dynamic version reading from pyproject.toml
- **config/server_config.py**: Unified server configuration with session management (2025-10-11)
- **config/logging.py**: Logging configuration and diagnostic formatting
- **cli_setup.py**: CLI-based Telegram authentication setup with MCP config output (2025-10-11)
- **~/.config/fast-mcp-telegram/**: Standard location for Telegram session files
- **scripts/deploy-mcp.sh**: Enhanced deployment script with session management

### Testing Infrastructure
- **tests/conftest.py**: Centralized test fixtures and shared configuration
- **tests/test_*.py**: Organized test modules by functional areas and components
- **Mock Implementations**: Comprehensive mocking for external APIs and services
- **Test Utilities**: Reusable testing helpers and authentication simulators

### Tool Dependencies
- **search_messages**: Depends on search.py and entity resolution
- **send_message**: Depends on messages.py with formatting, file sending, and album support
- **send_message_to_phone**: Depends on messages.py with contact management and file sending
- **search_contacts**: Depends on contacts.py for contact resolution

### Infrastructure Components
- **Dockerfile**: Multi-stage UV build with sessions directory creation
- **docker-compose.yml**: Production configuration with optimized volume mounts
- **.gitignore**: Git integration with sessions directory handling

## Design Patterns in Use

### 1. Factory Pattern
- Entity resolution from various ID formats
- Client connection management

### 2. Strategy Pattern
- Different search strategies for global vs per-chat
- Different result formatting strategies

### 3. Builder Pattern
- Result object construction with optional fields
- Link generation for messages

### 4. Parallel Processing Pattern
- Multiple query execution using asyncio.gather()
- Result aggregation and deduplication

### 5. Helper Function Pattern (File Sending)
- **Modular Validation**: `_validate_file_paths()` separates validation logic
- **Download/Upload**: `_download_and_upload_files()` handles URL-to-Telegram conversion
- **Routing Logic**: `_send_files_to_entity()` routes to appropriate send method
- **Unified Interface**: `_send_message_or_files()` provides single entry point
- **Album Support**: Multiple URLs downloaded and uploaded first to enable album grouping
- **Security**: Local path validation ensures stdio mode requirement

### 5.1. Security-First File Handling Pattern (2025-10-01)
- **URL Security Validation**: `_validate_url_security()` prevents SSRF attacks by blocking localhost, private IPs, and suspicious domains
- **Enhanced HTTP Client**: Disabled redirects, connection limits, security headers, and timeouts prevent abuse
- **File Size Limits**: Configurable maximum file size with both header and content validation
- **Configuration-Driven Security**: `allow_http_urls`, `max_file_size_mb`, `block_private_ips` settings for flexible security policies
- **Comprehensive Validation**: Multi-layer validation at URL parsing, HTTP request, and content levels
- **Security Testing**: Automated test suite validates all security measures work correctly

### 6. Error Handling Pattern
- **Structured Error Responses**: All tools return `{"ok": false, "error": "message", "operation": "name"}` instead of raising exceptions or empty results
- **Simplified Error Format**: Clean structure without request ID overhead, includes `operation` and sanitized `params` when relevant
- **Server Error Detection**: server.py checks `isinstance(result, dict) and "ok" in result and not result["ok"]`
- **Graceful Degradation**: Tools handle errors internally rather than propagating exceptions to MCP layer
- **Parameter Sanitization**: Automatic phone masking (`+1234567890` → `+12***90`), content truncation, and size limits for secure logging
- **Flattened Structure**: Direct field access (`error_type`, `exception_message`) instead of nested diagnostic info
- **No Empty Results**: Tools like `search_messages` and `search_contacts` return errors instead of empty arrays when no results found

### 6.1. Connection Stability Pattern (2025-10-17)
- **Exponential Backoff**: Progressive retry delays (2^failure_count seconds, max 60s) to prevent connection storms
- **Circuit Breaker**: Opens after 5 failures in 5 minutes, preventing futile reconnection attempts
- **Failure Tracking**: Per-token failure counting with timestamps for intelligent retry decisions
- **Session Health Monitoring**: Real-time tracking of connection quality and automatic cleanup of failed sessions
- **Error Pattern Detection**: Specific handling for "wrong session ID" and other connection-related errors
- **Graceful Degradation**: System continues operating with reduced functionality rather than complete failure
- **Resource Protection**: Prevents excessive CPU/memory usage from connection storms

### 6.1 Shared Utility Pattern (2025-10-11)
- **MCP Config Generation**: `utils/mcp_config.py` provides `generate_mcp_config()` and `generate_mcp_config_json()`
- **Single Source of Truth**: Both CLI setup and web setup use the same utility for MCP configuration
- **Mode-Aware Generation**: Generates different configs for STDIO, HTTP_NO_AUTH, and HTTP_AUTH modes
- **DRY Compliance**: Eliminated 60+ lines of duplicate code across cli_setup.py and web_setup.py
- **Comprehensive Testing**: Dedicated test suite validates all modes and edge cases
- **Easy Maintenance**: Changes to MCP config format only need to be made in one place

### 6.2 MTProto API Endpoint Pattern (2025-10-01)
- **Custom Routes**: `/mtproto-api/{method}` and versioned alias `/mtproto-api/v1/{method}` registered in `server_components/mtproto_api.py`
- **Auth Centralization**: `extract_bearer_token_from_request(request)` in `server_components/auth.py` used for HTTP_AUTH mode; bypass in other modes per config
- **Method Normalization**: `utils.helpers.normalize_method_name()` performs case-insensitive resolution by introspecting `telethon.tl.functions.{module}` and caching `lower(BaseName)->BaseName`
- **Dangerous Methods Guard**: Static denylist blocks destructive methods unless `allow_dangerous=true`
- **Entity Resolution**: Best-effort conversion of `peer`/`user_id`-like params via `client.get_input_entity` (singular and lists)
- **Response Policy**: Success returns JSON-safe dicts; errors use unified structured format with correct HTTP status (401/400/500)

### 7. Logging Architecture Pattern
- **Modular Design**: Dedicated `logging_utils.py` for logging functions, `error_handling.py` for error management, `logging.py` for configuration
- **Zero Redundancy**: Single source of truth for all logging operations with no code duplication between modules
- **Enhanced Capabilities**: Operation tracking with consistent parameter sanitization and metadata enhancement
- **Consistent Parameter Handling**: All logging uses consistent "params" key with automatic sanitization and metadata enhancement
- **Security-First**: Phone numbers masked, messages >100 chars truncated, large values >500 chars truncated
- **Performance-Aware**: Efficient parameter processing with no cross-module dependencies or circular imports
- **Standardized Structure**: All parameter dictionaries include helpful derived information (message_length, has_reply, etc.)

### Async Generators & RAM Optimizations (2025-09-17)
- Contacts: `search_contacts_native` now yields results; `find_chats_impl` merges via round-robin.
- Messages: Converted per-chat and global searches to async generators with round-robin executor.
- Limits: Early-stop once `limit` reached; batch sizes capped to avoid spikes.
- Impact: Lower peak RAM usage and fewer OOM crashes under load.
