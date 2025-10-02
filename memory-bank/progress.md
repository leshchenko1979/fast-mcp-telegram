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
- **Structured Logging**: Loguru integration with stdlib bridge and emitter tracking
- **Logging Spam Reduction**: Module-level filtering reduces Telethon noise by 99%
- **Consistent Error Handling**: All tools return structured error responses instead of raising exceptions
- **Token-Based Authentication**: Bearer token system with session isolation and LRU cache management
- **Multi-User Support**: HTTP transport with per-user session files and authentication
- **Session Management**: Token-specific sessions with automatic invalid session cleanup
- **Health Monitoring**: HTTP `/health` endpoint for session statistics and server monitoring
- **Web Setup (HTMX)**: Complete browser-based auth flow with improved styling and 2FA support
- **Config Generation**: Runtime `DOMAIN` with auto-download of `mcp.json`
- **Setup Session Cleanup**: TTL-based opportunistic cleanup for temporary setup sessions
- **Tool Splitting**: Ambiguous tools split into single-purpose tools to eliminate LLM agent errors
- **Literal Parameter Constraints**: Implemented `typing.Literal` for parameter validation and LLM guidance
- **Server Module Split**: Moved routes/tools out of `src/server.py` into dedicated modules

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
- **Logging System Refactoring**: Created dedicated `src/utils/logging_utils.py` module to eliminate redundancies between logging.py and error_handling.py (2025-12-19)
- **Logging System Optimization**: Comprehensive improvements including request ID removal, parameter sanitization, and structured error logging (2025-09-04)
- **Memory Bank Documentation**: Added comprehensive Memory Bank system documentation to CONTRIBUTING.md as recommended best practice for AI-assisted development, including Cursor IDE integration guidance
- **Setuptools Migration**: Return to setuptools for standard Python package management
- **Tool Descriptions**: Completely rewrote all tool descriptions to be concise yet comprehensive and LLM-optimized (2025-09-01)
- **'me' Identifier Support**: Added special handling for Saved Messages access using chat_id='me' (2025-09-01)
- **Error Logging**: Enhanced error logging for message access failures with detailed diagnostics (2025-09-01)
- **Function Organization**: Completed major refactoring - moved misplaced functions to appropriate modules (2025-09-01)
- **Offset Parameter**: Removed unused offset parameter from search functions, eliminating API confusion (2025-09-01)
- **Pre-commit Hooks**: Removed automated hooks, simplified to manual Ruff formatting (2025-09-01)
- **Code Quality**: Fixed all linter errors and improved overall code structure (2025-09-01)
- **Consistent Error Handling**: Implemented unified structured error responses across all tools (2025-09-01)
- **Readonly Database Issue**: Fixed Docker volume permissions causing "attempt to write a readonly database" error by changing mount from `/data` to `/app` directory (2025-09-01)
- **Deploy Script Enhancement**: Updated deployment script with automatic permission fixes to prevent future database issues (2025-09-01)
- **Docker Setup Workflow**: Updated to reflect that server shutdown is NOT required during Telegram authentication setup - new tokens and sessions are created by default (2025-01-04)
- **Volume Mount Conflicts**: Identified and resolved Docker volume mount issues causing directory vs file conflicts in session file handling (2025-09-01)
- **Simplified Docker Setup**: Implemented Docker Compose profiles to reduce authentication from 6 steps to 2 steps using `docker compose --profile setup run --rm setup` (2025-09-01)
- **Enhanced Setup Script**: Improved setup_telegram.py with better session conflict handling, command-line options, and interactive prompts (2025-09-01)
- **Security Documentation**: Added comprehensive security considerations section with critical warnings about Telegram account access risks (2025-09-01)
- **Streamlined Session Management**: Implemented streamlined session file architecture using `~/.config/fast-mcp-telegram/` for cross-platform compatibility (2025-09-01)
- **Enhanced Deployment Script**: Added comprehensive session file backup/restore, permission auto-fixing, and macOS resource fork cleanup (2025-09-01)
- **Git Integration**: Updated .gitignore to properly handle sessions directory while maintaining structure with .gitkeep (2025-09-01)
- **Dockerfile Enhancement**: Added sessions directory creation with proper ownership for container user access (2025-09-01)
- **Volume Mount Optimization**: Replaced file-specific mounts with directory mounts to eliminate permission conflicts (2025-09-01)
- **Production Session Management**: Implemented complete session persistence across deployments with automatic permission management (2025-09-01)
- **Dynamic Version Management**: Implemented automatic version reading from pyproject.toml in settings.py (2025-09-01)
- **.env File Auto-loading**: Enhanced setup_telegram.py to automatically load .env files for seamless authentication (2025-09-02)
- **Token-Based Authentication**: Implemented Bearer token authentication system with session isolation and LRU cache management (2025-01-04)
- **Multi-User Session Management**: Added support for multiple authenticated users with token-specific session files (2025-01-04)
- **Authentication Middleware**: Created `@with_auth_context` decorator and `extract_bearer_token()` for HTTP authentication (2025-01-04)
- **Setup Script Token Generation**: Modified setup_telegram.py to generate and display cryptographically secure Bearer tokens (2025-01-04)
- **Auto-Cleanup Removal**: Removed all automatic cleanup variables and background tasks for simplified architecture (2025-01-04)
- **Mandatory HTTP Authentication**: Eliminated fallback to default session for HTTP requests, making Bearer tokens mandatory (2025-01-04)
- **Literal Parameter Implementation**: Successfully implemented `typing.Literal` constraints for `parse_mode` and `chat_type` parameters to guide LLM choices and improve input validation. Updated all relevant tool signatures in server.py and verified FastMCP compatibility (2025-01-07)

### Current Limitations
- **Rate Limits**: Subject to Telegram API rate limiting
- **Search Scope**: Global search has different capabilities than per-chat search
- **Session Management**: Requires proper session handling and authentication

## Evolution of Project Decisions

### Web Setup Interface Evolution
1. **Initial**: Basic HTMX forms with standard styling
2. **Styling Issues**: Text sizes not optimized for readability
3. **Visual Hierarchy**: Implemented larger interactive elements with smaller instructional text
4. **Clean Layout**: Removed excessive text and empty visual elements
5. **Complete Flow**: Added missing 2FA route for full authentication support

### Authentication Flow Evolution
1. **CLI Only**: Initial setup required command-line interface
2. **Web Interface**: Added HTMX-based browser setup flow
3. **Missing 2FA**: 2FA route was missing, causing 404 errors
4. **Complete Flow**: Added proper 2FA handling with error recovery
5. **Enhanced UX**: Improved styling and user experience

### Logging Strategy Evolution
1. **Initial**: Basic logging with standard library
2. **Enhanced**: Added Loguru with stdlib bridge for better formatting
3. **Spam Issue**: Telethon DEBUG logging produced excessive noise (9,000+ messages)
4. **String Filtering**: Attempted message-based filtering (complex and fragile)
5. **Module Filtering**: Implemented module-level log level control (clean and effective)

### Search Implementation Evolution
1. **Basic**: Single query search only
2. **Multi-Query**: Added JSON array support for multiple terms
3. **Simplified**: Changed to comma-separated string format for better LLM compatibility
4. **Optimized**: Added parallel execution and deduplication

### Dependency Management Evolution
1. **pip + requirements.txt**: Initial setup with pip and requirements file
2. **UV Migration**: Migrated to uv for faster installs and better caching
3. **Multi-stage Docker**: Implemented uv-based multi-stage builds for optimized images
4. **Locked Dependencies**: uv.lock provides reproducible builds and faster deployments
5. **Setuptools Return**: Returned to setuptools for standard Python package management

### Media Handling Evolution
1. **Raw Objects**: Initially returned raw Telethon media objects
2. **Serialization Issues**: Discovered LLM incompatibility with binary data
3. **Placeholders**: Implemented lightweight metadata-only placeholders
4. **Optimized**: Preserved essential information while eliminating bloat

### Error Handling Evolution
1. **Initial**: Mixed error handling - some tools raised exceptions, others returned None
2. **Inconsistent**: get_contact_details returned None, search_messages raised exceptions
3. **Partial Fix**: get_contact_details updated to return structured errors
4. **Unified Pattern**: All tools now return structured error responses with consistent format
5. **Server Integration**: server.py detects and handles error responses appropriately

### Version Management Evolution
1. **Initial**: Hardcoded version in settings.py requiring manual synchronization
2. **Manual Sync**: Had to update both pyproject.toml and settings.py manually
3. **Version Bump Script**: Created script to update both files simultaneously
4. **Dynamic Reading**: Implemented automatic reading from pyproject.toml using tomllib/tomli
5. **Single Source**: Now only pyproject.toml needs updating, settings.py reads dynamically
6. **Direct Import**: Simplified to direct import from `src/_version.py` for better maintainability
### 2025-09-17
- Adopted async generators for message and contact searches to reduce RAM.
- Added round-robin consumption and early-stop on limits.
- Capped batch sizes and removed large intermediate lists.
