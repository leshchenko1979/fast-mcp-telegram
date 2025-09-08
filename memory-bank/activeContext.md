
## Current Work Focus
**Primary**: Documentation and configuration system updates completed. Modernized pydantic-settings based configuration with three clear server modes, updated README with simplified project structure, and created comprehensive .env.example template.

**Current Status**: All documentation updated to reflect current codebase state. Configuration system fully modernized with ServerConfig and SetupConfig classes. Three server modes (stdio, http-no-auth, http-auth) provide clear transport and authentication behavior. CLI setup supports automatic .env loading and comprehensive options.

## Active Decisions and Considerations

### Configuration System Modernization (2025-09-08)
**Decision**: Implemented comprehensive pydantic-settings based configuration system with three clear server modes and automatic CLI parsing
**Rationale**: Previous configuration was scattered across multiple files and lacked clear server mode definitions, making deployment and development confusing
**Solution**: 
- **ServerConfig Class**: Centralized server configuration with automatic environment variable and CLI argument parsing
- **Three Server Modes**: Clear enum-based modes (stdio, http-no-auth, http-auth) with defined transport and authentication behavior
- **SetupConfig Class**: Dedicated setup configuration separate from server configuration
- **Automatic CLI Parsing**: Native pydantic-settings CLI parsing with kebab-case conversion and error handling
- **Smart Defaults**: Host binding automatically adjusts based on server mode (127.0.0.1 for stdio, 0.0.0.0 for HTTP)
**Impact**:
- Clear server mode definitions eliminate configuration confusion
- Automatic CLI parsing reduces setup complexity
- Smart defaults improve out-of-box experience
- Separation of concerns between setup and server configuration

### Documentation and Configuration Updates (2025-09-08)
**Decision**: Updated all documentation to reflect current codebase state and modernized configuration system
**Rationale**: Documentation was outdated and didn't reflect the new server modes, configuration system, and project structure
**Solution**: 
- **README Updates**: Added server modes section, updated CLI arguments (--phone to --phone-number), updated environment variables
- **Project Structure**: Simplified from overly detailed to concise, essential information only
- **Environment Template**: Created comprehensive .env.example with all configuration options
- **Docker Configuration**: Updated docker-compose.yml and deploy script to use new server modes
- **Memory Bank Updates**: Updated all memory bank files to reflect current state
**Impact**:
- Clear documentation for all three server modes
- Easy setup with .env.example template
- Consistent configuration across all deployment methods
- Better user experience with simplified, focused documentation

### Web Setup Interface (2025-09-08)
**Decision**: Add HTMX/Jinja2-based web flow to replace CLI for browser users
**Flow**: `/setup` (GET) → `/setup/phone` → `/setup/verify` (→ optional `/setup/2fa`) → config generation
**Implementation**:
- Templates under `src/templates/` with HTMX fragments
- Live endpoints in `src/server.py` with Starlette custom routes
- Skipped separate success page; verification proceeds directly to generation
- Config uses `DOMAIN` env at runtime and includes Bearer token
- Added TTL-based opportunistic cleanup for setup sessions (default 900s)
**Impact**:
- Usable demo over web
- Cleaner UX with fewer steps and auto-download

### Server Module Split (2025-09-08)
**Decision**: Move HTTP routes and MCP tools out of `src/server.py` into dedicated modules
**Implementation**:
- Routes: `src/server/routes_setup.py` with `register_routes(mcp)`
- Tools: `src/server/tools_register.py` with `register_tools(mcp)`
- Auth/Error decorators: `src/server/auth.py`, `src/server/errors.py`
- Startup hook in `src/server.py` calls both registrars
**Impact**:
- Slimmer entrypoint, clearer responsibilities
- Easier maintenance and testing of tools and routes

### Literal Parameter Implementation (2025-01-07)
**Decision**: Implemented `typing.Literal` parameter constraints to guide LLM choices and improve input validation
**Problem**: String parameters like `parse_mode` and `chat_type` allowed any string values, leading to potential LLM errors and invalid inputs
**Solution**: Applied Literal type constraints to limit parameter values to valid options:
- **`parse_mode`**: Constrained to `Literal["markdown", "html"] | None` in all messaging tools
- **`chat_type`**: Constrained to `Literal["private", "group", "channel"] | None` in search tools
**Impact**:
- **Enhanced LLM Guidance**: AI models now see only valid parameter options, reducing errors
- **Improved Input Validation**: FastMCP automatically validates parameter constraints
- **Better User Experience**: Clear parameter options prevent invalid input attempts

### Tool Splitting Implementation (2025-01-07)
**Decision**: Implemented Item 1 from GitHub issue #1 to split ambiguous tools into single-purpose tools to eliminate LLM agent errors
**Problem**: Original tools had conditional behavior that confused LLMs:
- `search_messages`: Required `query` for global search, optional for per-chat search
- `send_or_edit_message`: Used `message_id` parameter to determine send vs edit mode
**Solution**: Split each ambiguous tool into two deterministic tools:
- `search_messages` → `search_messages_globally` + `search_messages_in_chat`
- `send_or_edit_message` → `send_message` + `edit_message`
**Impact**:
- **Eliminates Tool Overloading**: Each tool now has single, clear purpose
- **Deterministic Behavior**: LLMs can choose correct tool based on intent
- **Better Error Prevention**: Can't accidentally use wrong parameters for wrong operation

### Bearer Token Authentication System Resolution (2025-01-04)
**Decision**: Successfully identified and resolved the core bearer token authentication issue that was causing incorrect fallback to default sessions
**Root Cause**: The `stateless_http=True` parameter was required for FastMCP to properly execute the `@with_auth_context` decorator in HTTP transport mode
**Solution**: 
- **Critical Discovery**: `stateless_http=True` parameter is essential for authentication decorator execution in FastMCP HTTP mode
- Fixed decorator order for all tool functions to place `@with_auth_context` as the innermost decorator
- Built comprehensive test suite with 55 passing tests covering all authentication scenarios
- **Production Testing**: Established VDS deployment and testing methodology for authentication validation
**Impact**:
- Bearer token authentication now works correctly in production with proper token extraction and session creation
- No more incorrect fallback to default sessions when valid tokens are provided
- **Production logs confirm**: "Bearer token extracted for request" and "Created new session for token"
- Comprehensive test coverage ensures the issue won't regress

## Important Patterns and Preferences

### Logging Configuration Patterns
1. **Module-Level Filtering**: Set noisy Telethon submodules to INFO level (telethon.network.mtprotosender, telethon.extensions.messagepacker)
2. **Preserve Important Logs**: Keep connection, error, and RPC result messages at DEBUG level
3. **Structured Logging**: Use Loguru with stdlib bridge for consistent formatting and metadata
4. **Standard Fields**: Use loguru's built-in {name}, {function}, {line} fields for reliable logging
5. **Robust Error Handling**: Simple format strings prevent parsing errors and logging failures

### Multi-Query Search Patterns
1. **Comma-Separated Format**: Use single string with comma-separated terms (e.g., "deadline, due date")
2. **Parallel Execution**: Multiple queries execute simultaneously for better performance
3. **Deduplication**: Results automatically deduplicated based on message identity
4. **Pagination After Merge**: Limit and offset applied after all queries complete and deduplication

### Connection Management Patterns
1. **Single Function Pattern**: Use `get_connected_client()` instead of separate `get_client()` + `ensure_connection()` calls
2. **Automatic Reconnection**: All tools now check connection state before operations
3. **Graceful Error Handling**: Clear error messages when connection cannot be established

### Search Usage Patterns
1. **Contact-Specific Search**: Use `chat_id` parameter, `query` can be empty or specific
2. **Content Search**: Use global search with `query` parameter, no `chat_id`
3. **Hybrid Search**: Use both `chat_id` and `query` for targeted content search
4. **Multi-Term Search**: Use comma-separated terms in single query string

### VDS Testing and Diagnosis Methodology
1. **Environment Access**: Use SSH with credentials from `.env` file (`VDS_USER`, `VDS_HOST`, `VDS_PROJECT_PATH`)
2. **Deployment Process**: Use `./scripts/deploy-mcp.sh` for automated deployment with session management
3. **Container Management**: Use `docker compose` commands for container status, logs, and health checks
4. **Authentication Testing**: Use `curl` with proper MCP protocol headers and bearer tokens
5. **Log Analysis**: Monitor server logs for authentication flow and error patterns
6. **Session File Management**: Check `~/.config/fast-mcp-telegram/` for token-specific session files
7. **Traefik Integration**: Verify domain routing and SSL certificate management
8. **Health Monitoring**: Use `/health` endpoint and container health checks for system status
9. **Production Validation**: Test with real Telegram API calls to confirm end-to-end functionality
