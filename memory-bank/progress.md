### 2026-01-22
- **has_more Flag Logic Fix - COMPLETED ✅**: Fixed conservative has_more logic to prevent false negatives when more messages are available
- **Root Cause**: has_more was incorrectly set to false when exactly `limit` messages were found, even if more messages existed
- **Solution**: Modified logic to `has_more = len(collected) > len(window) or (len(collected) == limit and len(collected) > 0)` ensuring conservative behavior
- **Impact**: Users can always paginate to check for more messages, eliminating missed content scenarios
- **Zero Overhead**: Simple boolean logic with no additional API calls or processing
- **Testing**: All existing tests pass, maintains backward compatibility

### 2026-01-21
- **Voice Message Transcription Implementation - COMPLETED ✅**: Added automatic parallel voice message transcription for Telegram Premium accounts
- **Premium Status Check**: Direct verification using User.premium attribute before attempting transcription
- **Parallel Processing**: Uses asyncio.TaskGroup for concurrent transcription of multiple voice messages
- **Polling for Completion**: When transcription is pending, polls every second for up to 30 seconds until completion
- **Graceful Cancellation**: Cancels all concurrent transcriptions if any fails with "premium account required" error
- **Integration Points**: Added transcription to read_messages_by_ids (all messages) and search_messages_in_chat (browsing messages)
- **Media Enhancement**: Extended _build_media_placeholder to recognize voice messages and extract duration from document attributes
- **Error Resilience**: Continues operation without transcription if unexpected errors occur
- **PyProject.toml Consistency**: Updated Python version requirements and classifiers to match runtime environment (Python 3.11+ required)
- **Linting Fixes**: Resolved all linting issues including exception handling, import organization, and long line handling

### 2026-01-19
- **Web Setup Session Deletion Feature - COMPLETED ✅**: Added secure session file deletion via web interface
- **New Route Implementation**: Added `/setup/delete` POST route with bearer token authentication
- **Security Validation**: Validates token format, prevents reserved names, checks session existence
- **Active Session Cleanup**: Safely disconnects cached client connections before deletion
- **File System Operations**: Secure session file removal with proper error handling
- **UI Enhancement**: Added "Delete Session" button to web setup interface with warning message
- **Template Optimization**: Refactored setup.html with progressive enhancement, accessibility improvements, and responsive design
- **Form Switching Logic**: Unified JavaScript function for form management with data attributes
- **Error Handling**: Comprehensive error messages for invalid tokens and missing sessions
- **Documentation Update**: Updated Installation.md to reflect new session management options
- **Browser Testing**: Verified functionality works correctly with real browser interactions
- **Code Quality**: Maintained lint-free code with proper error handling and security measures

### 2026-01-17
- **Logging Configuration Optimization - COMPLETED ✅**: Comprehensive performance and correctness optimizations
- **Root WARNING + Application DEBUG Strategy**: Changed from root DEBUG to root WARNING with explicit application DEBUG
- **Secure by Default**: New loggers default to WARNING level instead of potentially noisy DEBUG
- **Explicit Application Verbosity**: Application modules must opt into DEBUG level, making logging intent clear
- **CustomFormatter Bug Fix**: Fixed formatTime() override to actually use millisecond formatting
- **AccessFilter Performance**: Optimized endpoint filtering with frozenset for O(1) lookups
- **Handler Level Configuration**: Fixed console handler to respect log_level parameter instead of hardcoded DEBUG
- **Config Caching**: Extracted static logger configurations to module-level constant for efficiency
- **Code Cleanup**: Removed dead code, improved exception handling, simplified startup logging
- **Testing Verified**: All 138 tests pass, logging behavior confirmed correct

### 2025-01-17
- **FastMCP Redis Logging Suppression - COMPLETED ✅**: Eliminated 90%+ of excessive DEBUG logging from FastMCP Redis operations, reducing log volume from ~15,000 to ~500-1,000 lines per 5 minutes while preserving operational visibility

### 2025-11-27
- **Peer Resolution Enhancement**: Enhanced entity resolution with multi-type lookup strategy to handle channels/groups that require explicit type specification
- **Multi-Type Entity Lookup**: Modified `get_entity_by_id()` to try sequential resolution: raw ID → PeerChannel → PeerUser → PeerChat
- **Resolved Peer 2928607356**: Successfully identified Telegram group "Редевест - дела" that was previously failing resolution
- **Production Deployment**: Deployed peer resolution fixes to VDS with zero downtime and immediate resolution of entity lookup issues
- **Code Quality**: Fixed linting issues with import organization and exception chaining (raise ... from None)
- **DRY Error Handling Implementation**: Created comprehensive decorator-based error handling system to eliminate repetitive exception handling across all MCP tools
- **Custom Exception Class**: Added `SessionNotAuthorizedError` for specific session authentication failures
- **Error Handling Decorator**: Implemented `@handle_telegram_errors()` decorator that automatically provides clear, actionable error messages for:
  - Session authorization issues → "Session not authorized. Please authenticate your Telegram session first."
  - Database errors → Retry suggestions for temporary server issues
  - Network errors → Connection troubleshooting guidance
  - Peer resolution errors → Clear ID validation messages
- **Refactored All Tools**: Applied decorator to `get_chat_info`, `search_contacts`, `send_message`, `search_messages`, and `invoke_mtproto` functions
- **Parameter Extraction**: Flexible params extraction supporting both direct parameters and custom extraction functions
- **Error Classification**: Intelligent error message selection based on exception content and context
- **Code Reduction**: Eliminated ~50 lines of repetitive exception handling code across the codebase
- **Improved UX**: Users now receive clear, actionable error messages instead of confusing technical errors
- **Testing**: Verified improved error messages return proper authentication guidance instead of misleading peer resolution errors

### 2025-11-27
- **Todo List and Poll Support in read_messages**: Enhanced `read_messages` and `search_messages` to automatically detect and parse Telegram Todo lists (`MessageMediaToDo`) and Polls (`MessageMediaPoll`)
- **Todo List Parsing**: Added structured parsing of TodoList objects extracting title, items, completion status, timestamps, and user information
- **Poll Parsing**: Implemented comprehensive Poll object parsing including questions, options, vote counts, and poll metadata (closed, multiple choice, quiz mode)
- **Media Recognition**: Updated `_has_any_media()` to recognize `MessageMediaToDo` for proper content detection
- **Structured Output**: Returns LLM-friendly JSON structures instead of raw Telethon objects for both Todo lists and Polls
- **Backward Compatibility**: All existing media types continue to work unchanged
- **Testing**: Comprehensive unit tests verify both Todo list and Poll parsing functionality
- **Impact**: `read_messages` now provides rich, structured data for interactive Telegram content types

### 2025-10-17
- Successfully resolved critical connection storm that was consuming 1,300+ reconnections per minute and 44.70% CPU usage
- Identified root cause: "Wrong session ID" error from Telegram servers due to corrupted session file (656KB vs normal 28KB)
- Implemented comprehensive connection stability improvements with exponential backoff and circuit breaker patterns
- Added session health monitoring with failure tracking, auto-cleanup of failed sessions, and enhanced health statistics
- Enhanced error detection to identify "wrong session ID" errors with appropriate user guidance
- Successfully restored original bearer token `f9NdKOLR...` with fresh, clean session data while preserving user continuity
- Deployed fixes to production VDS with zero downtime and immediate resolution of connection storm
- Achieved complete elimination of connection storm (0 reconnections vs 1,300+/minute) and normal resource usage
- Added robust protection against future connection issues with intelligent backoff and circuit breaker mechanisms

### 2025-11-18
- **FastMCP Deprecation Warning Fix**: Resolved DeprecationWarning for `stateless_http` parameter by moving it from FastMCP constructor to `run()` method call, ensuring compatibility with latest FastMCP version while maintaining authentication functionality
- **Web Setup Reauthorization Enhancement**: Added secure token-based reauthorization to existing `/setup` endpoint, allowing users to reauthorize expired sessions through web interface while maintaining security
- **Unified Setup Interface**: Enhanced `/setup` page with both "Create New Session" and "Reauthorize Existing Session" options using JavaScript toggles for better UX
- **Token-Based Security**: Implemented reauthorization flow requiring existing bearer token possession, preventing unauthorized access or session enumeration
- **Reauthorization Flow**: Added `/setup/reauthorize` and `/setup/reauthorize/phone` routes with phone verification to complete reauthorization while preserving original bearer token
- **Session File Management**: Created `setup_complete_reauth()` function to safely replace original session files with reauthorized versions
- **Enhanced Error Handling**: Added `success.html` and `error.html` fragments with user-friendly messaging and navigation
- **Security Validation**: Implemented comprehensive validation including reserved name blocking, session existence checks, and authorization status verification
- **Backward Compatibility**: Maintained existing new session creation flow while adding reauthorization capability
- **Bearer Token Reserved Name Protection**: Added validation to prevent reserved session names like "telegram" from being used as bearer tokens, preventing session file conflicts and maintaining isolation between HTTP_AUTH and STDIO modes. Implemented case-insensitive validation with comprehensive test coverage and security logging.
- Extended `/health` endpoint with connection failure statistics and session health monitoring capabilities

### 2025-11-25
- **Enhanced invoke_mtproto with Automatic TL Object Construction**: Extended `invoke_mtproto` to automatically construct Telethon TL objects from JSON dictionaries, enabling generic MTProto method invocation
- **Recursive TL Construction**: Added `_construct_tl_object_from_dict()` function that recursively builds TL objects from dictionaries with `"_"` keys
- **Case-Insensitive Type Lookup**: Added automatic case-insensitive type name resolution (`inputmediatodo` → `InputMediaTodo`, `TEXTWITHENTITIES` → `TextWithEntities`)
- **Parameter Processing Pipeline**: Enhanced `_resolve_params()` to construct TL objects before entity resolution using `inspect.signature()` for constructor parameter matching
- **Generic MTProto Support**: `invoke_mtproto` now works with any Telegram API method regardless of parameter complexity (todo lists, polls, complex media, etc.)
- **Automatic Type Mapping**: Maps class names to Telethon TL types using `telethon.tl.types` introspection with validation, error handling, and case-insensitive resolution
- **Nested Object Support**: Handles deeply nested structures like `InputMediaTodo` → `TodoList` → `TodoItem[]` automatically
- **Production Testing**: Successfully created a todo list in saved messages using the enhanced `invoke_mtproto` with automatic TL object construction
- **No Codebase Modification Required**: Users can now pass complex JSON structures without requiring manual TL object creation in the codebase
- **Backward Compatibility**: Existing simple parameters continue to work unchanged while complex objects are now supported

### 2025-11-19
- **Public Visibility Filtering Implementation**: Added `public: bool | None` parameter to `search_messages_globally` and `find_chats` tools with architectural rule that private chats should never be filtered by visibility
- **Boolean Parameter Design**: `public=True` finds entities with usernames (publicly discoverable), `public=False` finds entities without usernames (invite-only), `public=None` disables filtering
- **Private Chat Protection**: Private chats (direct messages with users) are automatically excluded from public filtering - they always appear regardless of the `public` parameter value
- **Core Filtering Logic**: Updated `_matches_public_filter()` in `entity.py` to return `True` for all private chats regardless of username presence
- **Search Implementation**: Modified `search.py` to use boolean public filtering in all search generators and helper functions
- **Contact Implementation**: Updated `contacts.py` to apply public filtering to contact searches while protecting private chats
- **Tool Registration**: Added `public` parameter to both search tools with clear documentation and examples
- **Documentation Updates**: Updated TypeScript signatures, examples, and descriptions to reflect boolean parameter and private chat protection
- **Version Bump**: Incremented version from 0.8.4 to 0.9.0 to reflect the major architectural change
- **Testing Validation**: Verified that private chats are never filtered while groups/channels are filtered normally
- **Live Deployment**: Successfully deployed and tested the new functionality in production VDS environment

### 2025-10-11
- Implemented unified session configuration system to eliminate session file mismatch between cli_setup and server
- Added `session_name` field to ServerConfig with default "telegram" and `session_path` property
- Refactored SetupConfig to inherit from ServerConfig, eliminating code duplication
- Updated settings.py to use session_name and session_path from unified config
- Refactored session behavior to check `server_mode` instead of `session_name` for proper security model
- HTTP_AUTH mode now generates random bearer tokens; STDIO/HTTP_NO_AUTH use configured session names
- Created shared `utils/mcp_config.py` utility for MCP config generation (DRY principle applied)
- Eliminated duplicate MCP config generation code from cli_setup.py (47 lines) and web_setup.py (13 lines)
- CLI setup now prints ready-to-use MCP config JSON with mode-specific instructions (parity with web setup)
- Web setup refactored to use shared utility for consistent config generation
- Added security warnings for HTTP_AUTH mode with clear credential handling guidance
- Fixed security issue: bearer_token not printed for HTTP_NO_AUTH mode (was confusing)
- Created comprehensive test suite with 26 passing tests (15 session config + 11 MCP generation)
- Updated Installation.md documentation with multiple accounts support and SESSION_NAME examples
- Configuration now supports CLI args, env vars, and .env files with consistent priority
- Works consistently across all three server modes with mode-appropriate behavior
- Eliminated need for symlinks or manual session file management workarounds
- Supports multiple Telegram accounts via SESSION_NAME configuration

### 2025-10-02
- Implemented comprehensive logging optimization and performance improvements for better VDS log readability and server performance
- Reduced asyncio selector debug spam (70+ messages per session eliminated) by setting asyncio logger to WARNING level
- Prevented repeated server startup messages (14+ per session reduced to 1) with logging setup and config validation deduplication
- Enhanced Telethon noise reduction with additional module filtering (connection, telegramclient, tl layer)
- Added noise reduction for common HTTP libraries (urllib3, httpx, aiohttp) to eliminate debug spam
- Optimized InterceptHandler with level caching and reduced frame walking overhead for better performance
- Enhanced parameter sanitization with pre-compiled patterns, fast paths for simple types, and optimized string operations
- Implemented batch logger configuration for better startup performance
- Added fast path optimization for empty parameter logging to reduce overhead
- Implemented health endpoint access log filtering to eliminate monitoring noise
- Implemented functools.cache optimizations across the codebase for better performance and maintainability
- Replaced manual caching patterns with functools.cache in helpers.py and entity.py
- Optimized Telethon function mapping with automatic caching using @cache decorator
- Enhanced entity processing functions (get_normalized_chat_type, build_entity_dict) with intelligent caching
- Maintained manual caching for async operations in bot_restrictions.py (functools.cache limitations with async)
- Updated tests to work with new caching patterns while preserving existing functionality
- Achieved better performance, cleaner code, automatic memory management, dramatically reduced log noise, and optimized logging overhead

### 2025-10-01
- Completed comprehensive README restructuring and documentation organization
- Reduced README from 1000+ lines to 202 lines with concise, skimmable structure optimized for users landing on the repo
- Created comprehensive docs/ folder with 7 specialized documentation files (Installation, Deployment, MTProto-Bridge, Tools-Reference, Search-Guidelines, Operations, Project-Structure)
- Moved detailed sections from README to appropriate specialized guides to eliminate overwhelming content
- Created SECURITY.md with authentication model, risks, and best practices
- Eliminated duplication between README, CONTRIBUTING.md, and new documentation files
- Updated CONTRIBUTING.md to point to new documentation structure and removed redundant deployment sections
- Verified all documentation links resolve correctly and follow professional documentation best practices

### 2025-10-01
- Added MTProto API endpoint `/mtproto-api/{method}` with versioned alias; centralized HTTP bearer extraction; implemented case-insensitive method normalization with Telethon introspection cache; denylist for dangerous methods; structured error responses; README updated with curl examples.
- Added file sending capability to `send_message` and `send_message_to_phone` tools
- Implemented support for single or multiple files (URLs or local paths)
- URLs work in all server modes; local paths restricted to stdio mode for security
- Multiple files sent as albums when possible (via download/upload for URLs)
- Added helper functions: `_download_and_upload_files`, `_validate_file_paths`, `_send_files_to_entity`, `_send_message_or_files`
- Updated README with file sending examples and documentation
- Supports all file types: images, videos, documents, audio, etc.

### 2025-09-17
- Added optional `chat_type` filter to `find_chats` tool and implementation (users, groups, channels)
- Updated `README.md` examples for `find_chats` to document `chat_type`
### Voice Message Transcription Implementation (2026-01-21)
- **Direct Premium Status Check**: Checks user's premium status directly from User.premium attribute before attempting transcription
- **Parallel Processing**: Uses `asyncio.TaskGroup` to transcribe multiple voice messages concurrently for better performance
- **Polling for Completion**: When transcription is pending, polls every second for up to 30 seconds until transcription completes
- **Graceful Cancellation**: Cancels all concurrent transcription tasks when any fails with "premium account required" error
- **Integration Points**: Added transcription to `read_messages_by_ids` (all messages) and `search_messages_in_chat` (when no search query provided)
- **Media Metadata Enhancement**: Extended `_build_media_placeholder` to recognize voice messages and extract duration from document attributes
- **Error Resilience**: Continues operation without transcription if unexpected errors occur, rather than failing entire message retrieval

### 2025-09-17
- Implemented uniform chat schema across tools using `build_entity_dict`
- Updated `find_chats` to support comma-separated multi-term queries with deduplication by `id`
- Simplified contacts results: removed nested `user_info`/`chat_info` in quick results
- Ensured `title` fallback (explicit → full name → @username) and type normalization
 - `get_chat_info` now enriches results with `members_count`/`subscribers_count` using Telethon full-info requests; base builder includes counts opportunistically when present on entities
 - Added `about` for groups/channels and `bio` for users via new `build_entity_dict_enriched`; `get_chat_info` now returns these when available
## What Works (Functional Status)

### Core Functionality ✅
- **MCP Server**: FastMCP-based server with full Telegram integration
- **Configuration System**: Modernized pydantic-settings based configuration with three clear server modes
- **Message Search**: Split into `search_messages_globally` and `search_messages_in_chat` for deterministic behavior
- **Message Operations**: Split into `send_message` and `edit_message` for clear intent separation
- **File Sending**: Send single or multiple files via URLs (all modes) or local paths (stdio mode only)
- **Contact Management**: Search and get contact details
- **Phone Messaging**: Send messages to phone numbers not in contacts (with file support)
- **MTProto Access**: Raw method invocation capability
- **Connection Management**: Automatic reconnection and error handling

### Advanced Features ✅
- **Multi-Query Search**: Comma-separated terms with parallel execution and deduplication
- **LLM-Optimized Media**: Lightweight placeholders instead of raw Telethon objects
- **Todo List Support**: Automatic parsing of Telegram Todo lists with structured completion data
- **Poll Support**: Comprehensive parsing of Telegram polls with vote counts and metadata
- **Structured Logging**: Stdlib logging migration - removed complex Loguru bridge
- **Logging Spam Reduction**: Module-level filtering reduces Telethon noise by 99%
- **Consistent Error Handling**: All tools return structured error responses instead of raising exceptions
- **Token-Based Authentication**: Bearer token system with session isolation and LRU cache management
- **Multi-User Support**: HTTP transport with per-user session files and authentication
- **Session Management**: Token-specific sessions with automatic invalid session cleanup
- **Health Monitoring**: HTTP `/health` endpoint for session statistics and server monitoring
- **Connection Stability**: Exponential backoff, circuit breaker, and session health monitoring to prevent connection storms
- **Web Setup (HTMX)**: Complete browser-based auth flow with improved styling and 2FA support
- **Config Generation**: Runtime `DOMAIN` with auto-download of `mcp.json`
- **Setup Session Cleanup**: TTL-based opportunistic cleanup for temporary setup sessions
- **Tool Splitting**: Ambiguous tools split into single-purpose tools to eliminate LLM agent errors
- **Literal Parameter Constraints**: Implemented `typing.Literal` for parameter validation and LLM guidance
- **Server Module Split**: Moved routes/tools out of `src/server.py` into dedicated modules
- **Voice Message Transcription**: Automatic parallel transcription of voice messages for Telegram Premium accounts with persistent non-premium detection

### Deployment & Integration ✅
- **HTTP Transport**: FastMCP over HTTP with CORS support
- **Cursor Integration**: Verified working with Cursor IDE
- **Production Deployment**: VDS deployment with Traefik and TLS
- **Environment Management**: Proper credential handling and session management
- **Dependency Management**: setuptools with pyproject.toml for package management
- **Session Persistence**: Zero-downtime deployments with automatic session backup/restore

### Documentation & User Experience ✅
- **Comprehensive Documentation**: Organized docs/ folder with 7 specialized guides covering all aspects of the project
- **User-Friendly README**: Concise 202-line README optimized for quick scanning and navigation
- **Security Documentation**: Dedicated SECURITY.md with authentication model and best practices
- **Developer Guidelines**: Updated CONTRIBUTING.md with clear development setup and contribution process
- **No Content Duplication**: Eliminated redundant information across documentation files
- **Professional Structure**: Follows documentation best practices with clear navigation and specialized content

## What's Left to Build (Remaining Work)

### Potential Enhancements
- **Rate Limiting**: Implement intelligent rate limiting for API calls
- **Caching**: Add message and contact caching for performance
- **Advanced Filtering**: More sophisticated search filters and operators
- **Batch Operations**: Bulk message operations and batch processing
- **Webhook Support**: Real-time message notifications via webhooks
- **UX Polish**: Additional hints and retry mechanics in setup UI

### Infrastructure Improvements
- **Monitoring**: Enhanced metrics and health checks
- **Security**: Additional authentication and authorization layers
- **Documentation**: API documentation and usage examples
- **Testing**: Comprehensive test suite and integration tests

## Known Issues and Status

### Resolved Issues ✅
- **Critical Connection Storm Resolution**: Successfully resolved connection storm consuming 1,300+ reconnections per minute and 44.70% CPU usage. Implemented exponential backoff, circuit breaker pattern, session health monitoring, and enhanced error detection. Restored original bearer token with fresh session data while preserving user continuity. Achieved complete elimination of connection storm and normal resource usage (2025-10-17)
- **Web Setup Interface Improvements**: Enhanced styling with larger input/button text (1.1rem/1rem) and smaller hint text (0.85rem), removed excessive instructional text, cleaned up empty card styling for better visual hierarchy (2025-09-09)
- **2FA Authentication Route Fix**: Added missing `/setup/2fa` route handler with proper password validation, error handling, and integration with session management and config generation flow (2025-09-09)
- **Documentation and Configuration Updates**: Updated all documentation to reflect current codebase state, created comprehensive .env.example template, updated README with three server modes, simplified project structure, and updated docker-compose.yml and deploy script to use new configuration system (2025-09-08)
- **Configuration System Modernization**: Implemented comprehensive pydantic-settings based configuration system with three clear server modes (stdio, http-no-auth, http-auth) and automatic CLI parsing. Created ServerConfig and SetupConfig classes with smart defaults and validation (2025-09-08)
- **Server Entrypoint Slimming**: `src/server.py` now registers routes (`register_routes`) and tools (`register_tools`) on startup; tool and route logic moved to dedicated modules (2025-09-08)
- **Tool Splitting Implementation**: Successfully implemented Item 1 from GitHub issue #1 by splitting ambiguous tools into single-purpose tools to eliminate LLM agent errors. Split `search_messages` into `search_messages_globally` and `search_messages_in_chat`, and `send_or_edit_message` into `send_message` and `edit_message`. Updated documentation and memory bank accordingly (2025-01-07)
- **Bearer Token Authentication System**: Successfully identified and resolved the core authentication issue where bearer tokens were not being properly extracted and processed, causing incorrect fallback to default sessions (2025-01-04)
- **Critical FastMCP Parameter Discovery**: Discovered that `stateless_http=True` parameter is essential for FastMCP to properly execute the `@with_auth_context` decorator in HTTP transport mode (2025-01-04)
- **Decorator Order Fix**: Fixed incorrect decorator order in FastMCP tool functions - `@with_auth_context` is now the innermost decorator, ensuring proper authentication middleware execution (2025-01-04)
- **Comprehensive Test Suite**: Built extensive test coverage with 55 passing tests covering bearer token determination, decorator order, FastMCP integration, and authentication scenarios (2025-01-04)
- **Production Authentication Verification**: Bearer token authentication confirmed working in production with proper token extraction, session creation, and no fallback to default sessions (2025-01-04)
- **VDS Testing Methodology**: Established comprehensive approach for production authentication testing and debugging using VDS deployment (2025-01-04)
- **Professional Testing Infrastructure**: Implemented comprehensive pytest-based testing framework with organized test structure and modern development practices (2025-09-04)
- **Infrastructure & Tooling**: Session management, authentication, configuration, deployment, and testing infrastructure (2025)
- **Feature Development**: Message search, file sending, contact management, and advanced content support (2025)

### Current Limitations
- **Rate Limits**: Subject to Telegram API rate limiting
- **Search Scope**: Global search has different capabilities than per-chat search
- **Session Management**: Requires proper session handling and authentication

### 2025-09-17
- Adopted async generators for message and contact searches to reduce RAM
- Added round-robin consumption and early-stop on limits
- Capped batch sizes and removed large intermediate lists
