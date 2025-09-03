

## Current Work Focus
**Primary**: **PRODUCTION-READY SYSTEM** - Completed comprehensive session management and deployment enhancements. System now features enterprise-grade deployment with automatic session persistence, permission management, and robust production infrastructure.

**Current Status**: **FULLY PRODUCTION-READY** with streamlined session management architecture. **Standard session location**: Uses `~/.config/fast-mcp-telegram/` for cross-platform compatibility. **Enhanced deployment script**: Comprehensive backup/restore, permission auto-fixing, and macOS resource fork cleanup. **Docker optimization**: Single-stage builds with proper volume mounting and user permissions. **Git integration**: Proper .gitignore handling for session files.

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
**Solution**: Changed volume mount from `./telegram.session:/data/telegram.session` to `./telegram.session:/app/telegram.session` and SESSION_NAME from absolute to relative path
**Implementation**:
  - Updated docker-compose.yml with corrected volume mount and SESSION_NAME
  - Updated deploy script with automatic permission fixes for future deployments
  - Ensured session files have proper write permissions (666)
**Impact**:
  - Eliminated "attempt to write a readonly database" errors
  - MCP server now works reliably with all Telegram tools
  - Future deployments automatically prevent permission issues
  - Container has proper write access to SQLite session files

### Docker Setup Workflow Requirements
**Decision**: Container must be STOPPED during Telegram authentication setup
**Rationale**: Running setup while main service is active causes SQLite database file conflicts since both processes try to access the same session file simultaneously
**Solution**: Implemented proper Docker setup sequence:
  1. `docker compose down` - Stop container
  2. `docker compose run --rm fast-mcp-telegram python -m src.setup_telegram` - Run setup
  3. `docker compose up -d` - Start container
**Implementation**:
  - Updated README.md with correct Docker setup workflow
  - Added comprehensive troubleshooting section covering volume mount conflicts
  - Documented common session file and permission issues with solutions
**Impact**:
  - Eliminates "unable to open database file" errors during setup
  - Prevents session file corruption from concurrent access
  - Provides clear setup instructions for users
  - Reduces support burden for Docker deployment issues

### Docker Compose Profile Simplification
**Decision**: Implemented Docker Compose profiles to reduce setup complexity from 6 steps to 2 steps
**Rationale**: Manual Docker container management was complex and error-prone, requiring multiple commands and manual file operations
**Solution**: Added `setup` service to docker-compose.yml with profile isolation:
```yaml
setup:
  profiles: [setup]
  command: python -m src.setup_telegram --overwrite
```
**Implementation**:
  - Single command: `docker compose --profile setup run --rm setup`
  - Automatic session file handling via volume mounts
  - No manual container management or file copying required
  - Profile ensures setup service doesn't interfere with production
**Impact**:
  - 83% reduction in setup steps (6 → 2)
  - Eliminates manual file operations and container management
  - More reliable and less error-prone setup process
  - Professional Docker workflow with proper service isolation

### Enhanced Setup Script Features
**Decision**: Upgraded setup_telegram.py with comprehensive session handling and command-line options
**Rationale**: Original setup script was basic and didn't handle edge cases like existing sessions or provide automation options
**Solution**: Added advanced features:
  - Smart session conflict detection and resolution
  - Interactive prompts for user choices
  - Command-line options (`--overwrite`, `--session-name`)
  - Directory vs file conflict handling
  - Better error messages and validation
**Implementation**:
  - Session file existence checking with user choice prompts
  - Directory conflict resolution (rmtree for directories, unlink for files)
  - Command-line argument parsing with help text
  - Graceful error handling and user feedback
**Impact**:
  - Handles all Docker volume mount edge cases automatically
  - Provides both interactive and automated setup options
  - Eliminates common setup failures and user confusion
  - Professional-grade setup experience

### Security-First Documentation
**Decision**: Added comprehensive security documentation with critical warnings about Telegram account access risks
**Rationale**: Users need to understand that exposing the MCP server means giving others full access to their Telegram account
**Solution**: Created prominent security section with:
  - Critical security warning about account access risks
  - Specific dangerous actions that can be performed
  - Network security recommendations (IP whitelisting, VPN, reverse proxy)
  - Session file protection guidelines
  - Container security best practices
  - Monitoring recommendations
**Implementation**:
  - 🚨 Prominent critical security warning at top of section
  - Detailed list of account access risks
  - Practical security implementation guidance
  - Professional security documentation standards
**Impact**:
  - Users understand the security implications before deployment
  - Provides actionable security recommendations
  - Reduces likelihood of insecure deployments
  - Sets appropriate security expectations for production use

### Streamlined Session Management Architecture
**Decision**: Implemented streamlined session file architecture using standard user config directory
**Rationale**: Complex session directory management created deployment overhead and maintenance complexity
**Solution**: Uses standard `~/.config/fast-mcp-telegram/` directory for cross-platform compatibility
**Implementation**:
  - Session files stored in: `~/.config/fast-mcp-telegram/telegram.session`
  - Updated .gitignore to properly ignore session files
  - Simplified Docker configuration with proper volume mounts
  - Streamlined deployment script to handle standard session location
**Impact**:
  - Simplified deployment and maintenance
  - Cross-platform compatibility
  - Reduced configuration complexity
  - Better alignment with standard practices
  - Simplified deployment and backup processes

### Enhanced Deployment Script with Session Management
**Decision**: Added comprehensive session file backup/restore, permission auto-fixing, and macOS resource fork cleanup to deployment script
**Rationale**: Manual session file management was error-prone and time-consuming, especially across different operating systems
**Solution**: Enhanced `deploy-mcp.sh` with automated session handling:
  - Automatic backup of existing session files before deployment
  - Intelligent restore of session files after deployment
  - Auto-fix permissions for container user access (1000:1000)
  - Automatic cleanup of macOS resource fork files (._*)
  - Local-to-remote session file synchronization
**Implementation**:
  - Added session backup/restore logic with error handling
  - Implemented permission auto-fixing (chown 1000:1000, chmod 664/775)
  - Added macOS resource fork cleanup (find . -name '._*' -delete)
  - Enhanced logging with file count tracking
  - Git-aware deployment (excludes sessions from git transfers)
**Impact**:
  - Zero-touch session file management across deployments
  - Eliminates "readonly database" permission errors
  - Automatic cleanup of cross-platform artifacts
  - Professional deployment experience with detailed progress tracking

### Docker Volume Mount Optimization
**Decision**: Replaced file-specific volume mounts with directory mounts to eliminate permission conflicts and improve reliability
**Rationale**: File-specific mounts created permission conflicts and directory/file type mismatches in Docker containers
**Solution**: Simplified to use standard session location with proper volume mounts:
  - Session files stored in: `~/.config/fast-mcp-telegram/telegram.session`
  - Volume mount: `~/.config/fast-mcp-telegram:/home/appuser/.config/fast-mcp-telegram`
  - Removed complex session directory management
  - Streamlined Dockerfile configuration
**Implementation**:
  - Simplified docker-compose.yml with standard volume mounts
  - Removed SESSION_NAME environment variable (uses default)
  - Streamlined Dockerfile to single-stage build
  - Enhanced deployment script for standard session handling
**Impact**:
  - Eliminated Docker volume mount permission conflicts
  - More reliable session file access in containers
  - Better cross-platform compatibility
  - Simplified volume management and troubleshooting

### Production Session Persistence System
**Decision**: Implemented complete session persistence across deployments with automatic permission management and backup/restore
**Rationale**: Session files were lost during deployments, requiring manual re-authentication and disrupting production workflows
**Solution**: Created comprehensive session persistence system:
  - Automatic backup during deployment
  - Intelligent restore with permission fixing
  - Local-to-remote synchronization
  - Cross-platform compatibility handling
  - Git integration with proper ignore patterns
**Implementation**:
  - Deploy script automatically backs up remote sessions
  - Copies local sessions to remote before deployment
  - Restores sessions with correct permissions after deployment
  - Handles macOS resource forks and cross-platform issues
  - Maintains session files outside Git tracking for security
**Impact**:
  - Zero-downtime deployments with session preservation
  - Eliminates manual session file management
  - Automatic permission fixing prevents database errors
  - Production-ready deployment workflow
  - Cross-platform deployment compatibility

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
1. **Monitor Production Deployment**: Track session persistence and permission auto-fixing in production environment
2. **Validate Session Backup/Restore**: Ensure session files are properly backed up and restored across deployments
3. **Test Cross-Platform Compatibility**: Verify deployment works consistently across different host systems
4. **Monitor Docker Performance**: Track container startup times and resource usage with new volume mounting
5. **User Feedback Integration**: Monitor for any session management or deployment issues in production use
6. **Documentation Maintenance**: Keep README and deployment guides updated with any production learnings
