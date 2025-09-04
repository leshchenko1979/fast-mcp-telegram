

## Current Work Focus
**Primary**: **CONTRIBUTING.MD COMPREHENSIVE UPDATE COMPLETED** - Successfully updated CONTRIBUTING.md with comprehensive developer documentation aligned with current project state and memory bank information.

**Current Status**: **MEMORY BANK SYSTEM DOCUMENTATION COMPLETE** - Added comprehensive Memory Bank system documentation to CONTRIBUTING.md as recommended best practice for AI-assisted development, including Cursor IDE integration guidance. **Developer Documentation Complete**: Updated with current dependency management (setuptools), session management architecture, deployment patterns. **Tooling Standardized**: Returned to setuptools + pip for better compatibility. **Cursor IDE Optimized**: Clear instructions for AI agent memory bank integration with auto-apply rules.

## Active Decisions and Considerations

### CONTRIBUTING.md Memory Bank Documentation Update (2025-01-04)
**Decision**: Added comprehensive Memory Bank system documentation to CONTRIBUTING.md, positioned as recommended best practice for AI-assisted development rather than mandatory requirement, including Cursor IDE integration guidance
**Rationale**: Need to provide clear guidance for AI-assisted developers while maintaining flexibility for traditional development workflows, and ensure proper integration with Cursor IDE
**Solution**:
  - Removed reference to non-existent .env.example file and updated environment setup
  - Updated dependency management from uv back to setuptools with proper pip documentation
  - Removed pre-commit hooks section (no longer used) and updated development workflow
  - Added comprehensive Session Management Architecture section
  - **Added Memory Bank System section** with best practices for AI-assisted development
  - **Added Cursor IDE integration section** with auto-apply rules and fallback instructions
  - Enhanced Deployment section with current patterns and production features
  - Updated table of contents to reflect all changes
  - Positioned Memory Bank as beneficial tool rather than strict requirement
**Implementation**:
  - Fixed Quick Setup section to create .env file directly instead of copying non-existent .env.example
  - Updated Dependencies section to document setuptools and pip package management
  - Removed all pre-commit references and updated Development Workflow
  - **Added comprehensive Memory Bank System section** emphasizing benefits for AI-assisted development
  - **Added Cursor IDE section** explaining auto-applied rules and "use the memory bank" instructions
  - Included optional Memory Bank steps in development process
  - Made Memory Bank updates optional but recommended in PR requirements
  - Added Memory Bank reading as optional step in Quick Setup
  - Focused on benefits for AI collaboration rather than strict enforcement
  - Expanded Deployment section with development and production deployment options
  - Updated table of contents to include new Memory Bank System section
**Impact**:
  - **Cursor IDE optimized** with clear instructions for memory bank integration
  - **Flexible approach** allowing developers to choose Memory Bank usage based on workflow
  - **AI-focused benefits** clearly communicated for developers using Cursor, Claude, etc.
  - Accurate developer documentation aligned with current project architecture
  - Improved developer experience with optional but valuable documentation practices
  - Comprehensive coverage of session management for contributors
  - **Balanced approach** between encouraging best practices and maintaining flexibility
  - Enhanced contribution process with accurate technical information
  - **AI collaboration optimization** through recommended Memory Bank usage
  - **Clear integration path** for different IDEs and AI agents

### Tooling Standardization (2025-01-04)
**Decision**: Return to standard Python tooling (setuptools + pip) instead of uv and pre-commit
**Rationale**: While uv provides faster installations, the project has standardized on setuptools for better compatibility and simpler deployment across different environments
**Solution**:
  - Reverted from uv to setuptools build backend in pyproject.toml
  - Removed all uv.lock references and documentation
  - Removed pre-commit hooks configuration and documentation
  - Updated CONTRIBUTING.md to reflect current tooling
  - Updated Dockerfile to use standard pip installations
**Implementation**:
  - Updated pyproject.toml to use setuptools.build_meta
  - Removed uv-specific configurations and lock files
  - Updated development workflow documentation to remove pre-commit
  - Updated dependency management documentation to reflect setuptools usage
  - Maintained all existing functionality while simplifying the toolchain
**Impact**:
  - Simplified development environment setup
  - Better compatibility across different platforms and environments
  - Reduced complexity in deployment and CI/CD pipelines
  - Standard Python tooling that's universally supported
  - Maintained performance and functionality while improving maintainability

### Logging System Optimization (2025-09-04)
**Decision**: Comprehensive logging pattern improvements with request ID removal and advanced parameter handling
**Rationale**: Request IDs created overhead without adding value, while parameter logging needed security enhancements and standardization
**Solution**:
  - Complete removal of request ID generation, variables, imports, and references from entire codebase
  - Standardized parameter logging keys to always use "params" instead of mixed keys like "search_params"
  - Simplified error logging structure from nested `{"diagnostic_info": {...}}` to flat `{"params": ..., "error_type": ..., "operation": ...}`
  - Implemented parameter sanitization with phone number masking (`+1234567890` → `+12***90`) and content truncation
  - Added automatic metadata enhancement with timestamps and parameter counts
  - Consistent parameter structure across all functions with derived information
**Implementation**:
  - Updated `log_and_build_error()` and `handle_tool_error()` to not require/use request IDs
  - Created `sanitize_params_for_logging()` for phone masking and size limits (messages >100 chars, values >500 chars truncated)
  - Created `add_logging_metadata()` for automatic timestamp and param count addition
  - Standardized parameter dictionaries with helpful derived info (message_length, has_reply, is_global_search, etc.)
  - Applied sanitization and metadata enhancement to all logging functions
**Impact**:
  - Cleaner, more secure logs with sensitive data automatically masked
  - Better performance with reduced parameter overhead and no request ID generation
  - Improved log querying with flattened error structure
  - Enhanced debugging context with automatic metadata and derived information
  - Simplified error responses without request ID clutter
  - Consistent logging patterns across all operations

### Professional Testing Infrastructure Implementation (2025-09-04)
**Decision**: Implemented comprehensive pytest-based testing framework with modern development practices
**Rationale**: Previous testing was limited to basic manual runner; needed professional-grade testing infrastructure for maintainability and CI/CD integration
**Solution**:
  - Created organized `tests/` directory structure with logical test file separation
  - Implemented shared fixtures in `conftest.py` for reusable test setup
  - Converted to pytest with async support and comprehensive test coverage
  - Added coverage reporting, parallel execution, and professional configuration
  - Created comprehensive test suite covering core functionality and edge cases
**Implementation**:
  - `tests/conftest.py`: Shared fixtures (mock_client, test_server, client_session)
  - `tests/test_basic_functionality.py`: MCP server basics and message operations
  - `tests/test_decorator_chain.py`: Decorator integration and authentication
  - `tests/test_error_handling.py`: Error handling and parameter introspection
  - Updated `pyproject.toml` with pytest configuration and coverage settings
  - Enhanced `.dockerignore` for comprehensive build optimization
**Impact**:
  - Comprehensive test suite with systematic coverage of core functionality
  - Professional pytest setup with fixtures, async support, and coverage reporting
  - CI/CD ready with parallel execution and comprehensive reporting
  - Improved development workflow with fast test execution and debugging
  - Enhanced code quality through systematic test coverage
  - Scalable testing infrastructure that grows with the codebase

### Logging System Refactoring (2025-12-19)
**Decision**: Created dedicated `src/utils/logging_utils.py` module to eliminate redundancies between `logging.py` and `error_handling.py`
**Rationale**: Significant code duplication existed between configuration and error handling modules, with both containing similar logging functions and parameter sanitization logic
**Solution**:
  - Created new `src/utils/logging_utils.py` module for all logging-specific functions
  - Moved `log_operation_start()`, `log_operation_success()`, `log_operation_error()` from `src/config/logging.py`
  - Moved `_log_at_level()` function from `error_handling.py` to `logging_utils.py`
  - Added comprehensive logging functions for operation tracking
  - Kept shared utilities (`sanitize_params_for_logging`, `add_logging_metadata`) in `error_handling.py`
  - Eliminated cross-dependencies and circular import issues
**Implementation**:
  - Created comprehensive logging utilities module with proper separation of concerns
  - Updated `src/config/logging.py` to contain only configuration and `format_diagnostic_info()`
  - Updated `src/utils/error_handling.py` to import `_log_at_level` from new location
  - Updated all import statements across codebase (`messages.py`, `search.py`)
  - Fixed import sorting and eliminated circular dependencies
  - Maintained full backward compatibility and functionality
**Impact**:
  - Zero code duplication between logging modules
  - Clean architecture with proper module responsibilities
  - Enhanced logging capabilities with request ID tracking
  - Eliminated circular import issues
  - Improved maintainability and code organization
  - Single source of truth for all logging operations

### Unified Error Handling Standardization (2025-01-04) [SUPERSEDED by Logging Optimization 2025-09-04]
**Decision**: Implemented comprehensive error handling standardization across all tools and server components (later optimized to remove request ID overhead)
**Rationale**: Mixed error handling patterns (exceptions, None returns, different response formats) created inconsistent API behavior for LLMs and complicated debugging
**Solution**:
  - Standardized error response format: `{"ok": false, "error": "message", "operation": "name"}`
  - Removed exception propagation - all tools return structured responses
  - Updated server.py with streamlined error handling without request ID overhead
**Implementation**:
  - search.py: Consolidated parameter handling and improved error responses
  - contacts.py: Changed from list error responses to dict error responses for consistency
  - messages.py: Fixed read_messages_by_ids to return error responses instead of raising exceptions
  - mtproto.py: Removed inconsistent `{"ok": true, "result": ...}` wrapper for success responses
  - server.py: Streamlined error handling and operation tracking
**Impact**:
  - Predictable API responses for all operations with no exceptions
  - Better LLM compatibility with structured error handling
  - Improved debugging with consistent operation context
  - Unified error detection pattern in server.py using `handle_tool_error()`
  - Enhanced maintainability with DRY error handling patterns

### Token-Based Session Management Implementation (2025-01-04)
**Decision**: Implemented comprehensive multi-user authentication system with Bearer tokens and session isolation
**Rationale**: Enable multiple users to use the same MCP server instance while maintaining security and session separation
**Solution**: 
  - Generated 256-bit cryptographically secure Bearer tokens via `generate_bearer_token()`
  - Token-specific session files in format `{token}.session`
  - Context variable `_current_token` for request-scoped token tracking
  - LRU cache with configurable `MAX_ACTIVE_SESSIONS` limit
  - Auto-deletion of invalid session files on authentication errors
**Implementation**:
  - Authentication middleware `@with_auth_context` decorator on all MCP tools
  - `extract_bearer_token()` function for HTTP header parsing
  - `DISABLE_AUTH` environment variable for development mode
  - Modified setup script to generate and display Bearer tokens
  - Mandatory authentication for HTTP transport (no fallback to default session)
**Impact**: Enables secure multi-user deployments with proper session isolation and enterprise-grade authentication

### Auto-Cleanup Removal (2025-01-04)
**Decision**: Removed all automatic cleanup functionality and background tasks
**Rationale**: Simplified system architecture and eliminated potential runtime issues with asyncio event loops
**Removed Components**:
  - `SESSION_TIMEOUT_HOURS` and `MAX_SESSION_FILE_AGE_DAYS` constants
  - `cleanup_expired_sessions()` and `cleanup_old_session_files()` functions
  - Background cleanup task and related infrastructure
  - Session timeout tracking and automatic expiration
**Impact**: Cleaner, more predictable system behavior with manual session management control through existing cleanup functions
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
**Solution**: All tools now return structured error responses with consistent format: `{"ok": false, "error": "message", "operation": "name"}`
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
  - **Automatic .env file loading**: Script now automatically loads .env files from the project directory
**Implementation**:
  - Session file existence checking with user choice prompts
  - Directory conflict resolution (rmtree for directories, unlink for files)
  - Command-line argument parsing with help text
  - Graceful error handling and user feedback
  - Added dotenv loading with proper path resolution and user feedback
**Impact**:
  - Handles all Docker volume mount edge cases automatically
  - Provides both interactive and automated setup options
  - Eliminates common setup failures and user confusion
  - Professional-grade setup experience
  - **Seamless authentication**: Users can create .env files and run setup without manual credential entry

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

### Production-First Docker Optimization (2025-01-04)
**Decision**: Removed editable install (`-e .`) and volume mounting for cleaner production deployment
**Rationale**: Editable installs were causing dependency reinstallation issues and volume mounting added development complexity
**Solution**: Simplified to production-focused Docker build:
  - Layer 1: Install dependencies directly from hardcoded list (cached when pyproject.toml unchanged)
  - Layer 2: Copy source code directly (rebuilds only when code changes)
  - Removed volume mounting of source code from docker-compose.yml
  - Eliminated all editable install complexity
**Implementation**:
  - Create minimal package structure: `mkdir -p src && touch src/__init__.py`
  - Install from pyproject.toml: `pip install --no-cache-dir .` (gets all dependencies from single source of truth)
  - Copy real source: `COPY src/ ./src/` (overwrites minimal structure)
  - Removed `- ./src:/app/src` volume mounts from both services
**Impact**: 
  - No dependency reinstallation on code changes
  - Faster, more predictable builds
  - Production-optimized container without development artifacts
  - Clean separation between dependencies and application code

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

### Dynamic Version Management System
**Decision**: Implemented dynamic version reading from pyproject.toml in settings.py
**Rationale**: Previously had hardcoded version in settings.py that required manual synchronization with pyproject.toml
**Solution**: Modified settings.py to automatically read version from pyproject.toml at runtime using tomllib/tomli
**Implementation**:
  - Added `get_version_from_pyproject()` function with Python version compatibility
  - Added tomli dependency for Python < 3.11
  - Updated `SERVER_VERSION` to use dynamic reading
  - Removed manual version bumping script as it's no longer needed
**Impact**:
  - Single source of truth for version information
  - Automatic synchronization between package and server versions
  - Simplified maintenance - only update pyproject.toml
  - GitHub Actions automatically uses correct version for publishing

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
2. **Consistent Error Format**: Include `operation` and `params` in error responses
3. **Server Error Detection**: Check `isinstance(result, dict) and "ok" in result and not result["ok"]`
4. **Graceful Degradation**: Tools handle errors internally and return structured responses
5. **Parameter Sanitization**: Automatic phone masking and content truncation for security
6. **Parameter Preservation**: Original parameters included in error responses for context

## Next Immediate Steps
1. **Monitor Production Deployment**: Track session persistence and permission auto-fixing in production environment
2. **Validate Session Backup/Restore**: Ensure session files are properly backed up and restored across deployments
3. **Test Cross-Platform Compatibility**: Verify deployment works consistently across different host systems
4. **Monitor Docker Performance**: Track container startup times and resource usage with new volume mounting
5. **User Feedback Integration**: Monitor for any session management or deployment issues in production use
6. **Documentation Maintenance**: Keep README and deployment guides updated with any production learnings
7. **Version Management Validation**: Test that the dynamic version reading works correctly in production environment
8. **GitHub Actions Integration**: Verify that version bumping triggers automatic PyPI publishing correctly
9. **Logging System Validation**: Test the new logging architecture in production to ensure all logging functions work correctly
10. **Performance Monitoring**: Monitor for any performance improvements or regressions with the refactored logging system
