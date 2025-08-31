

## Current Work Focus
**Primary**: Completed comprehensive LLM optimization of all tool descriptions and enhanced Saved Messages access. System now has concise, LLM-optimized tool descriptions with structured sections, special 'me' identifier support for Saved Messages, and improved error logging with detailed diagnostics.

**Current Status**: System is fully optimized for LLM consumption with enhanced Saved Messages functionality. **Tool descriptions rewritten**: All tool descriptions now use concise, structured format with clear sections (MODES, FEATURES, EXAMPLES, Args) optimized for LLM comprehension. **'me' identifier support**: Added special handling for Saved Messages access using chat_id='me' for more reliable and consistent API usage. **Error logging enhanced**: Improved error logging for message access failures with detailed diagnostics and request tracking. **README updated**: Documentation now reflects the new concise tool descriptions with practical examples. Production deployment stable with HTTP/SSE endpoint at `https://tg-mcp.redevest.ru/mcp`.

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

## Next Immediate Steps
1. **Test Phone Messaging**: Verify that `send_message_to_phone()` tool works correctly with various phone numbers
2. **Monitor Prod Logs**: Ensure Telethon connection stability and search performance with reduced spam
3. **Harden CORS**: Restrict origins when ready (currently permissive for development)
4. **Maintenance**: Keep dependencies updated and monitor for API changes
5. **Documentation**: Keep README and tool documentation updated with new phone messaging examples
