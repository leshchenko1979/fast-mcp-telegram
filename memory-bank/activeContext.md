

## Current Work Focus
**Primary**: Completed major code refactoring and quality improvements. System now has optimized code organization with functions moved to appropriate modules, simplified search logic, and enhanced maintainability.

**Current Status**: System has been comprehensively refactored for better code organization and maintainability. **Function reorganization**: Moved misplaced functions to appropriate modules (entity operations to `utils/entity.py`, media detection to `utils/message_format.py`, logging utilities to `config/logging.py`, generic helpers to `utils/helpers.py`). **Search simplification**: Removed unused `offset` parameter from search functions, eliminating confusion and API impedance mismatch. **Pre-commit removal**: Eliminated pre-commit hooks in favor of manual code formatting with Ruff. **Code quality**: Fixed all linter errors and improved overall code structure.

## Active Decisions and Considerations
### Logging Spam Reduction Implementation
**Decision**: Implemented module-level logging configuration to reduce Telethon network spam
**Rationale**: Telethon DEBUG logging was producing 9,000+ messages per session, making logs unreadable and causing 924KB log files in minutes
**Solution**: Set noisy Telethon submodules to INFO level while keeping important modules at DEBUG
**Impact**: Reduced log volume from 6,702 lines to ~16 lines, eliminated 5,534 spam phrases, preserved connection and error visibility

### LLM-Optimized Media Placeholders
**Decision**: Implemented lightweight media placeholders with mime_type, file_size, and filename instead of raw Telethon objects
**Rationale**: Raw Telethon media objects are large, contain binary data, and are not suitable for LLM consumption
**Impact**: Much more efficient for LLMs, cleaner JSON output, preserved essential metadata

### Multi-Query Search Implementation
**Decision**: Implemented comma-separated query support with parallel execution and deduplication
**Rationale**: User requested ability to search multiple terms and get unified, deduplicated results
**Impact**: Enhanced search efficiency and user experience; queries like "рынок, склады" now work seamlessly

### Query Format Simplification
**Decision**: Changed from JSON array format to comma-separated string for multiple queries
**Rationale**: LLM clients had difficulty formatting complex JSON arrays correctly
**Impact**: Simplified input format while maintaining full functionality

### Parallel Execution Strategy
**Decision**: Use `asyncio.gather()` for parallel query execution
**Rationale**: Improves performance when searching multiple terms simultaneously
**Impact**: Faster search results with better resource utilization

### Deduplication Logic
**Decision**: Implement deduplication based on `(chat.id, message.id)` tuples
**Rationale**: Ensure unique results when same message matches multiple search terms
**Impact**: Clean, unified result sets without duplicates

### HTTP Deployment & CORS
**Decision**: Serve FastMCP over streamable HTTP at `/mcp`, enable permissive CORS for Cursor compatibility
**Rationale**: Cursor enforces CORS-like policies and expects HTTP/SSE endpoint
**Impact**: Publicly reachable MCP with secure TLS via Traefik; Cursor connects via `mcp.json`

### Logging Bridge
**Decision**: Bridge `uvicorn`, `uvicorn.access`, and `telethon` loggers into Loguru with DEBUG
**Rationale**: Expand error visibility and trace RPC flow when debugging prod issues
**Impact**: Clear, centralized logs in container and rotating files

### DRY Connection Management
**Decision**: Created `get_connected_client()` function to eliminate repetitive connection check patterns
**Rationale**: All tools were using the same pattern of `get_client()` followed by `ensure_connection()` checks
**Impact**: Cleaner, more maintainable code with reduced duplication while maintaining the same reliability

### Logging Robustness Fix
**Decision**: Fixed `KeyError: 'emitter_logger'` and `ValueError: Sign not allowed in string format specifier` issues in Loguru handlers
**Rationale**: During shutdown with exceptions, logging system tried to format messages without required extra fields, and invalid format string syntax caused additional errors
**Solution**: Simplified logging format to use standard loguru fields, removed complex format string syntax that caused parsing errors and logging failures
**Impact**: Eliminated logging errors during shutdown and normal operation, restored logging functionality, improved system stability and log readability

### UV Migration and Optimization
**Decision**: Migrated from pip to uv for dependency management with multi-stage Docker builds
**Rationale**: uv provides faster installs, better caching, and reproducible builds compared to pip
**Solution**: Created pyproject.toml, generated uv.lock, implemented uv-based multi-stage Dockerfile with builder/runtime stages
**Impact**: Faster builds, smaller images, reproducible deployments, and better dependency management

### Phone Messaging Capability
**Decision**: Added `send_message_to_phone()` tool to enable messaging users by phone number
**Rationale**: User requested ability to send messages to phone numbers not in contacts
**Solution**: Implemented complete workflow using Telegram's ImportContactsRequest and DeleteContactsRequest, placed in `messages.py` for logical organization
**Impact**: Users can now send messages to any phone number registered on Telegram without manual contact management

### LLM Tool Description Optimization
**Decision**: Completely rewrote all tool descriptions to be concise yet comprehensive and LLM-optimized
**Rationale**: Original descriptions were verbose and not structured for efficient LLM consumption
**Solution**: Implemented structured format with clear sections (MODES, FEATURES, EXAMPLES, Args) and reduced length by ~75%
**Impact**: LLMs can now quickly understand tool functionality, see practical examples, and make informed decisions

### 'me' Identifier Support
**Decision**: Added special handling for 'me' identifier in entity resolution for Saved Messages access
**Rationale**: Numeric user IDs were inconsistent for Saved Messages access, 'me' is the standard Telegram identifier
**Solution**: Enhanced `get_entity_by_id()` function to recognize 'me' and use `client.get_me()`
**Impact**: More reliable Saved Messages access with consistent API usage across both reading and searching

### Enhanced Error Logging
**Decision**: Improved error logging for individual message access failures with detailed diagnostics
**Rationale**: Silent failures made debugging difficult, needed better traceability for troubleshooting
**Solution**: Added warning logs with request ID, message ID, chat ID, and diagnostic information
**Impact**: Better debugging capability and system monitoring with detailed error context

### Function Organization Refactoring
**Decision**: Moved misplaced functions to appropriate modules based on responsibility and usage patterns
**Rationale**: Code was scattered across modules with functions performing operations outside their logical scope
**Solution**: Systematic reorganization following single responsibility principle
**Impact**:
  - `_get_chat_message_count()` and `_matches_chat_type()` → `utils/entity.py`
  - `_has_any_media()` → `utils/message_format.py`
  - `log_operation_*()` functions → `config/logging.py`
  - `_append_dedup_until_limit()` → new `utils/helpers.py`
  - Cleaner module boundaries and improved maintainability

### Offset Parameter Removal
**Decision**: Removed unused `offset` parameter from search functions
**Rationale**: Parameter existed in signature but was ignored, creating API confusion and documentation mismatch
**Solution**: Simplified function signatures and removed pagination logic that wasn't supported by Telegram API
**Impact**: Cleaner API, eliminated confusion, reduced code complexity, better alignment with actual Telegram API capabilities

### Pre-commit Hooks Removal
**Decision**: Removed automated pre-commit hooks in favor of manual Ruff formatting
**Rationale**: Pre-commit hooks added complexity without significant benefit for current workflow
**Solution**: Keep Ruff available for manual formatting when needed
**Impact**: Simplified development workflow while maintaining code formatting capability

### Consistent Error Handling Pattern
**Decision**: Implemented unified structured error responses across all Telegram MCP tools
**Rationale**: Mixed error handling patterns (some raised exceptions, some returned None) created inconsistent API behavior for LLMs
**Solution**: All tools now return structured error responses with consistent format: `{"ok": false, "error": "message", "request_id": "id", "operation": "name"}`
**Implementation**:
  - `get_contact_details`: Already returned errors for non-existent contacts
  - `search_contacts`: Updated to return errors instead of empty lists for no results
  - `search_messages`: Updated to return errors instead of empty message arrays for no results
  - `read_messages`, `invoke_mtproto`: Already returned structured errors
**Impact**:
  - Predictable API responses for all operations
  - Better LLM compatibility with structured error handling
  - Improved debugging with request IDs and operation context
  - Consistent error detection pattern across server.py
  - No more None returns or exception propagation to MCP layer

### Docker Volume Permissions Fix
**Decision**: Fixed readonly database error by changing Docker volume mount from `/data` to `/app` directory
**Rationale**: SQLite session files needed write permissions, but `/data` directory had restrictive filesystem permissions that prevented the `appuser` from writing
**Solution**: Changed volume mount from `./mcp_telegram.session:/data/mcp_telegram.session` to `./mcp_telegram.session:/app/mcp_telegram.session` and SESSION_NAME from absolute to relative path
**Implementation**:
  - Updated docker-compose.yml with corrected volume mount and SESSION_NAME
  - Updated deploy script with automatic permission fixes for future deployments
  - Ensured session files have proper write permissions (666)
**Impact**:
  - Eliminated "attempt to write a readonly database" errors
  - MCP server now works reliably with all Telegram tools
  - Future deployments automatically prevent permission issues
  - Container has proper write access to SQLite session files

## Important Patterns and Preferences

### Logging Configuration Patterns
1. **Module-Level Filtering**: Set noisy Telethon submodules to INFO level (telethon.network.mtprotosender, telethon.extensions.messagepacker)
2. **Preserve Important Logs**: Keep connection, error, and RPC result messages at DEBUG level
3. **Structured Logging**: Use Loguru with stdlib bridge for consistent formatting and metadata
4. **Standard Fields**: Use loguru's built-in {name}, {function}, {line} fields for reliable logging
5. **Robust Error Handling**: Simple format strings prevent parsing errors and logging failures
6. **Graceful Degradation**: InterceptHandler includes fallback logging when standard logging fails

### Multi-Query Search Patterns
1. **Comma-Separated Format**: Use single string with comma-separated terms (e.g., "deadline, due date")
2. **Parallel Execution**: Multiple queries execute simultaneously for better performance
3. **Deduplication**: Results automatically deduplicated based on message identity
4. **Pagination After Merge**: Limit and offset applied after all queries complete and deduplication

### Connection Management Patterns
1. **Single Function Pattern**: Use `get_connected_client()` instead of separate `get_client()` + `ensure_connection()` calls
2. **Automatic Reconnection**: All tools now check connection state before operations
3. **Graceful Error Handling**: Clear error messages when connection cannot be established
4. **Consistent Implementation**: Connection checks added to all client-using functions

### Search Usage Patterns
1. **Contact-Specific Search**: Use `chat_id` parameter, `query` can be empty or specific
2. **Content Search**: Use global search with `query` parameter, no `chat_id`
3. **Hybrid Search**: Use both `chat_id` and `query` for targeted content search
4. **Multi-Term Search**: Use comma-separated terms in single query string
5. **Exact Message Retrieval**: Use `read_messages(chat_id, message_ids)` when IDs are known

### Message Formatting Patterns
1. **Plain Text**: Default behavior (`parse_mode=None`) for maximum compatibility
2. **Markdown**: Use `parse_mode='md'` or `'markdown'` for rich text formatting
3. **HTML**: Use `parse_mode='html'` for HTML-based formatting

### Media Handling Patterns
1. **LLM-Optimized Placeholders**: Media objects contain mime_type, file_size, and filename instead of raw Telethon objects
2. **Document Metadata**: Documents show mime_type, approx_size_bytes, and filename when available
3. **Photo/Video Metadata**: Photos and videos show mime_type and approx_size_bytes when available
4. **Clean Output**: No media field present when message has no media content

### Phone Messaging Patterns
1. **Contact Management**: Add contact → send message → optionally remove contact workflow
2. **Error Handling**: Graceful handling when phone number not registered on Telegram
3. **Optional Contact Retention**: `remove_if_new` parameter controls whether to remove newly created contacts (default: false)
4. **Consistent Interface**: Uses same logging, error handling, and result format as other message tools
5. **Formatting Support**: Supports `parse_mode` for Markdown/HTML formatting like other message tools
6. **Reply Support**: Supports `reply_to_msg_id` for replying to messages
7. **Clear Result Fields**: `contact_added` and `contact_removed` fields provide clear status information

### Error Handling Patterns
1. **Structured Error Responses**: All tools return `{"ok": false, "error": "message", ...}` instead of raising exceptions
2. **Consistent Error Format**: Include `request_id`, `operation`, and `params` in error responses
3. **Server Error Detection**: Check `isinstance(result, dict) and "ok" in result and not result["ok"]`
4. **Graceful Degradation**: Tools handle errors internally and return structured responses
5. **Request Tracking**: Each operation gets unique `request_id` for debugging
6. **Parameter Preservation**: Original parameters included in error responses for context

## Next Immediate Steps
1. **Monitor UV Performance**: Track build times and deployment efficiency with uv-based setup
2. **Test Phone Messaging**: Verify that `send_message_to_phone()` tool works correctly with various phone numbers
3. **Monitor Prod Logs**: Ensure Telethon connection stability and search performance with reduced spam
4. **Dependency Updates**: Keep uv.lock updated with latest compatible versions
5. **Documentation**: Update README with uv setup instructions and new deployment workflow
