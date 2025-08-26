

## Current Work Focus
**Primary**: Added new `send_message_to_phone()` tool to enable sending messages to phone numbers not in contacts. Implemented complete workflow: add temporary contact → send message → optionally remove contact. Enhanced MCP server with direct phone messaging capability.

**Current Status**: System is production-ready and deployed to VDS behind Traefik. Public HTTP/SSE endpoint exposed at `https://tg-mcp.redevest.ru/mcp`. Cursor integration verified; server lists tools and executes searches remotely. Logging expanded (Loguru + stdlib bridge) for detailed Telethon/Uvicorn traces. LLM-optimized media placeholders implemented and tested successfully. **Logging spam reduction implemented**: Module-level filtering reduces Telethon network spam by 99% while preserving important connection and error information. **Logging robustness improved**: Fixed shutdown logging errors and cleaned up old log files. **New phone messaging capability**: Added `send_message_to_phone()` tool for contacting users by phone number. **Setup import error fixed**: Resolved ModuleNotFoundError in console script by moving setup_telegram.py into src package structure.

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
**Decision**: Fixed `KeyError: 'emitter_logger'` issues in Loguru handlers during server shutdown
**Rationale**: During shutdown with exceptions, logging system tried to format messages without required extra fields
**Solution**: Implemented safe format strings with fallback values and robust error handling in InterceptHandler
**Impact**: Eliminated logging errors during shutdown, improved system stability and log readability

### Phone Messaging Capability
**Decision**: Added `send_message_to_phone()` tool to enable messaging users by phone number
**Rationale**: User requested ability to send messages to phone numbers not in contacts
**Solution**: Implemented complete workflow using Telegram's ImportContactsRequest and DeleteContactsRequest, placed in `messages.py` for logical organization
**Impact**: Users can now send messages to any phone number registered on Telegram without manual contact management

## Important Patterns and Preferences

### Logging Configuration Patterns
1. **Module-Level Filtering**: Set noisy Telethon submodules to INFO level (telethon.network.mtprotosender, telethon.extensions.messagepacker)
2. **Preserve Important Logs**: Keep connection, error, and RPC result messages at DEBUG level
3. **Structured Logging**: Use Loguru with stdlib bridge for consistent formatting and metadata
4. **Emitter Tracking**: Include original logger/module/function/line in log output for better debugging
5. **Robust Error Handling**: Safe format strings with fallback values prevent KeyError during shutdown
6. **Graceful Degradation**: InterceptHandler includes fallback logging when binding fails

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

## Next Immediate Steps
1. **Test Phone Messaging**: Verify that `send_message_to_phone()` tool works correctly with various phone numbers
2. **Monitor Prod Logs**: Ensure Telethon connection stability and search performance with reduced spam
3. **Harden CORS**: Restrict origins when ready (currently permissive for development)
4. **Maintenance**: Keep dependencies updated and monitor for API changes
5. **Documentation**: Keep README and tool documentation updated with new phone messaging examples
