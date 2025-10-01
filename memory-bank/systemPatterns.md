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

### 1. Configuration Architecture
- **ServerConfig Class**: Centralized server configuration with pydantic-settings
- **Three Server Modes**: Clear enum-based modes (stdio, http-no-auth, http-auth)
- **Automatic CLI Parsing**: Native pydantic-settings CLI parsing with kebab-case conversion
- **Smart Defaults**: Host binding and authentication behavior based on server mode
- **SetupConfig Class**: Dedicated setup configuration separate from server configuration
- **Backward Compatibility**: settings.py imports from server_config for legacy support

### 2. Authentication Architecture
- **Token-Based Sessions**: Bearer tokens create isolated user sessions
- **Context Variables**: `_current_token` for request-scoped authentication
- **LRU Cache Management**: Configurable `MAX_ACTIVE_SESSIONS` with automatic eviction
- **Transport-Specific Auth**: Mandatory for HTTP, optional for stdio (legacy)
- **Session File Format**: `{token}.session` for multi-user isolation
- **Authentication Middleware**: `@with_auth_context` decorator on all MCP tools

### 3. Server Mode Architecture
- **STDIO Mode**: Development with Cursor IDE (no auth, default session only)
- **HTTP_NO_AUTH Mode**: Development HTTP server (auth disabled)
- **HTTP_AUTH Mode**: Production HTTP server (auth required)
- **Transport Selection**: Automatic transport selection based on server mode
- **Host Binding**: Smart defaults (127.0.0.1 for stdio, 0.0.0.0 for HTTP)

### 4. Search Architecture
- **Dual Search Modes**: Global search vs per-chat search
- **Multi-Query Support**: Comma-separated terms with parallel execution
- **Query Handling**: Different logic for empty vs non-empty queries
- **Entity Resolution**: Automatic chat ID resolution from various formats
- **Deduplication**: Results merged and deduplicated based on message identity

### Uniform Entity Schema (2025-09-17)
- All tools format chat/user data via `utils.entity.build_entity_dict`
- Schema: `id`, `title`, `type` (private|group|channel), `username`, `first_name`, `last_name`
- Counts: `members_count` for groups, `subscribers_count` for channels (opportunistic in builder; guaranteed via async helper)
- `title` fallback: explicit title → full name → `@username`
- Quick lookup tools (e.g., `find_chats`) return lightweight schema; detailed info via `get_chat_info` uses async helper to enrich with counts and `about`/`bio`

### 5. Multi-Query Implementation
- **Input Format**: Single string with comma-separated terms (e.g., "deadline, due date")
- **Parallel Execution**: `asyncio.gather()` for simultaneous query processing
- **Deduplication Strategy**: `(chat.id, message.id)` tuple-based deduplication
- **Pagination**: Applied after all queries complete and results are merged

### 6. Tool Registration Pattern
- **FastMCP Integration**: Uses FastMCP framework for MCP compliance
- **Module Registration**: Tools registered via `src/server_components/tools_register.register_tools(mcp)`
- **Async Operations**: All Telegram operations are async for performance
- **Error Handling**: All tools return structured error responses instead of raising exceptions
- **Literal Parameter Constraints**: Uses `typing.Literal` to constrain parameter values and guide LLM choices

### 7. Data Flow Patterns
```
User Request → MCP Tool → Search Function → Telegram API → Results → Response
```

### 8. Authentication Flow
```
HTTP Request → extract_bearer_token() → @with_auth_context → set_request_token() → _get_client_by_token() → Session Cache/New Session → Tool Execution
```

### 9. Multi-Query Search Flow
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

### 10. Session Management Architecture
- **Token-Based Sessions**: Each Bearer token gets isolated session file `{token}.session`
- **LRU Cache Management**: In-memory cache with configurable `MAX_ACTIVE_SESSIONS` limit
- **Automatic Eviction**: Oldest sessions disconnected when cache reaches capacity
- **Session Location**: `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Auto-Cleanup on Auth Errors**: Invalid session files automatically deleted
- **Git Integration**: Proper .gitignore with .gitkeep for structure maintenance
- **Cross-Platform**: Automatic handling of macOS resource forks and permission differences
- **Permission Auto-Fix**: Automatic chown/chmod for container user access (1000:1000)
- **Backup/Restore**: Comprehensive session persistence across deployments

### 11. Professional Testing Infrastructure
- **Test Framework**: Modern pytest-based testing with comprehensive async support
- **Test Organization**: Scalable structure with logical separation of test modules by functionality
- **Shared Fixtures**: Centralized test setup and reusable fixtures for consistent testing
- **Coverage Analysis**: Automated coverage reporting with multiple output formats
- **Parallel Execution**: Support for concurrent test execution in CI/CD pipelines
- **Mock Infrastructure**: Comprehensive mocking for external dependencies and APIs
- **Async Testing**: Full async/await support for modern Python concurrency patterns

### 12. Deployment & Transport
- Transport: Streamable HTTP with SSE mounted at `/mcp`
- Ingress: Traefik `websecure` with Let's Encrypt, configurable router domain
- CORS: Permissive during development for Cursor compatibility
- Sessions: Standard `~/.config/fast-mcp-telegram/` directory with automatic permission management
- Volume Mounting: Standard user config directory mounts
- Web Setup: HTMX/Jinja2 templates under `src/templates`, routes: `/setup`, `/setup/phone`, `/setup/verify`, `/setup/2fa`, `/setup/generate`, `/download-config/{token}`
- Setup Session Cleanup: Opportunistic TTL-based cleanup (default 900s) for temporary `setup-*.session` files

### 13. Web Setup Interface Architecture
- **HTMX Integration**: Dynamic form updates with `hx-target="#step"` for seamless UX
- **Template Structure**: Base template with fragment-based form components
- **Visual Hierarchy**: Larger interactive elements (1.1rem inputs, 1rem buttons) with smaller instructional text (0.85rem)
- **Clean Layout**: Minimal text, no empty visual elements, progressive disclosure
- **Error Handling**: Context-specific error messages with retry capability
- **Session Management**: TTL-based setup session cleanup with automatic resource management

### 14. Logging Strategy
- Loguru: File rotation + console with structured logging
- Bridged Loggers: `uvicorn`, `uvicorn.access`, and `telethon` redirected into Loguru at DEBUG
- Modular Architecture: Dedicated `logging_utils.py` for logging functions, `error_handling.py` for error management
- Parameter Sanitization: Automatic phone masking, content truncation, and security enhancements
- Request ID Tracking: Enhanced logging with optional request ID support for operation correlation
- Traceability: Detailed RPC traces enabled for production diagnosis with flattened error structures

### 15. Deployment Automation Patterns
- **Session Backup**: Automatic backup of `~/.config/fast-mcp-telegram/*` before deployment
- **Permission Management**: Auto-fix ownership (1000:1000) and permissions (664/775)
- **Cross-Platform Cleanup**: Automatic removal of macOS resource fork files (._*)
- **Git-Aware Transfer**: Exclude sessions directory from git transfers for security
- **Local-Remote Sync**: Bidirectional synchronization of session files
- **Error Recovery**: Robust error handling with detailed logging and counts

### 16. VDS Testing and Diagnosis Methodology
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
- **config/settings.py**: Configuration management with dynamic version reading from pyproject.toml
- **config/logging.py**: Logging configuration and diagnostic formatting
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
