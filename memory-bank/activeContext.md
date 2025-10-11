## Current Work Focus
**Primary**: Unified session configuration and MCP config generation (2025-10-11)

**Current Status**: Completed comprehensive unified session configuration with MCP config output:
- Added `session_name` field to ServerConfig with default "telegram" and `session_path` property
- Refactored SetupConfig to inherit from ServerConfig (eliminated code duplication)
- Updated settings.py to use session_name and session_path from unified config
- Refactored to check `server_mode` instead of `session_name` for proper security model
- HTTP_AUTH mode generates random bearer tokens; STDIO/HTTP_NO_AUTH use configured session names
- Created shared `utils/mcp_config.py` utility for MCP config generation (DRY principle)
- CLI setup now prints ready-to-use MCP config JSON (parity with web setup)
- Web setup refactored to use shared utility (eliminated code duplication)
- Added security warnings for HTTP_AUTH mode with clear credential handling
- Created comprehensive test suite with 26 passing tests (15 session config + 11 MCP generation)
- Updated Installation.md with multiple accounts documentation
- Supports SESSION_NAME via env vars, CLI options, and .env files
- Works consistently across all three server modes with mode-appropriate behavior
- Eliminated need for symlinks or manual session file management

## Active Decisions and Considerations

### Unified Session Configuration System (2025-10-11)
**Decision**: Unified configuration system for session files across cli_setup and server
**Problem**: Session file mismatch - cli_setup created random token sessions while server expected telegram.session
**Solution**:
- Added `session_name` field to ServerConfig (default: "telegram") and `session_path` property
- Made SetupConfig inherit from ServerConfig (eliminated duplication)
- Updated settings.py: `SESSION_NAME = config.session_name`, `SESSION_PATH = config.session_path`
- Refactored to check `server_mode` instead of `session_name` for security model:
  - HTTP_AUTH: Generates random bearer tokens (security-first for multi-user)
  - STDIO/HTTP_NO_AUTH: Uses configured session names (user control for dev)
- Created shared `utils/mcp_config.py` for MCP config generation (eliminated duplication)
- CLI setup now prints ready-to-use MCP config JSON (parity with web setup)
- Web setup refactored to use shared utility
- Added clear security warnings for HTTP_AUTH mode
- Configuration priority: CLI args → env vars → .env file → default
**Impact**: 
- Eliminates session file mismatch (no more symlinks needed)
- Supports multiple accounts via SESSION_NAME configuration
- Single source of truth for both session config and MCP config generation
- Consistent behavior between setup and server
- Proper security model per server mode
- Full test coverage (26 tests passing: 15 session config + 11 MCP generation)
- Better UX with copy-paste ready configs

### MTProto Module Refactoring (2025-10-02)
**Decision**: Unified MTProto implementation with single-function architecture
**Problem**: Code duplication across multiple files with unclear function boundaries
**Solution**: 
- Consolidated all MTProto logic into single `invoke_mtproto_impl()` function
- Eliminated duplicate constants (`DANGEROUS_METHODS`) and helper functions
- Removed artificial function boundaries between `invoke_mtproto_method` and `invoke_mtproto_impl`
- Created focused helper functions: `_resolve_method_class()`, `_sanitize_mtproto_params()`, `_json_safe()`
- Organized code with clear section headers and logical grouping
**Impact**: Cleaner architecture, easier maintenance, single source of truth for MTProto logic

### Interface Unification (2025-10-02)
**Decision**: Made MCP tool and HTTP bridge functionally identical
**Problem**: Different defaults and behaviors between interfaces caused confusion
**Solution**:
- Set `resolve=True` as default for both MCP tool and HTTP bridge
- Simplified HTTP bridge to use unified `invoke_mtproto_impl()` function
- Removed duplicate entity resolution logic from HTTP bridge
- Both interfaces now use identical parameter defaults and behavior
**Impact**: Consistent user experience, no functional differences between interfaces

### Performance Optimization with functools.cache (2025-10-02)
**Decision**: Implemented functools.cache across the codebase for better performance and maintainability
**Implementation**:
- **helpers.py**: Replaced manual `_TELETHON_FUNCS_CACHE` with `@cache` decorator on `_get_functions_map_for_module()`
- **entity.py**: Added `@cache` to `get_normalized_chat_type()` and `build_entity_dict()` for entity processing optimization
- **bot_restrictions.py**: Maintained manual caching for async operations (functools.cache doesn't work well with async)
- **Automatic Memory Management**: functools.cache provides thread-safe, automatic cache management
- **Simplified Code**: Eliminated manual cache key management and size tracking
**Impact**: Better performance, cleaner code, automatic memory management, thread safety

### Logging Optimization and Chatty Log Reduction (2025-10-02)
**Decision**: Comprehensive reduction of verbose logging to improve log readability and reduce noise
**Problem**: VDS logs contained excessive chatty messages making it difficult to identify real issues
**Analysis**: Identified main sources of noise:
- asyncio selector debug spam (70+ messages per session)
- Repeated server startup messages (14+ per session)
- Telethon network and connection noise
- HTTP library debug messages
**Solution**:
- **asyncio Noise Reduction**: Set asyncio logger to WARNING level to eliminate selector spam
- **Startup Message Deduplication**: Added `_configured` flag to prevent repeated logging setup calls
- **Config Validation Deduplication**: Added `_config_logged` flag to prevent repeated server config logging
- **Enhanced Telethon Filtering**: Added additional noisy modules (connection, telegramclient, tl layer)
- **HTTP Library Noise Reduction**: Set urllib3, httpx, and aiohttp to WARNING level
- **Preserved Diagnostic Value**: Maintained DEBUG level for useful diagnostic information
**Impact**: Dramatically reduced log noise while preserving essential debugging information

### Logging Performance Optimization (2025-10-02)
**Decision**: Comprehensive performance optimization of the logging system to reduce overhead
**Problem**: Logging system had performance bottlenecks in hot paths affecting overall server performance
**Analysis**: Identified key performance issues:
- InterceptHandler doing expensive operations on every log call
- Parameter sanitization with redundant string operations
- Logger configuration with individual getLogger calls
- Frame walking overhead for every log message
**Solution**:
- **InterceptHandler Optimization**: Added level caching, reduced frame walking to only when needed, optimized message formatting
- **Parameter Sanitization Enhancement**: Pre-compiled pattern sets, fast paths for simple types, optimized string operations
- **Logger Configuration Batching**: Batch configuration of logger levels for better startup performance
- **Fast Path Optimization**: Skip parameter processing for empty parameter dictionaries
- **String Operation Optimization**: Reduced f-string usage and optimized string concatenation
**Impact**: Significant reduction in logging overhead while maintaining full functionality and diagnostic capabilities

### Health Endpoint Access Log Filtering (2025-10-02)
**Decision**: Disable access logging for `/health` endpoint to reduce monitoring noise
**Problem**: Health check requests were generating frequent access log entries that cluttered logs
**Analysis**: Health endpoint is called frequently by monitoring systems and Docker health checks, creating noise
**Solution**:
- **Access Log Filtering**: Added filtering in InterceptHandler to skip uvicorn.access logs for `/health` endpoint
- **Extensible Design**: Filter supports multiple monitoring endpoints (`/health`, `/metrics`, `/status`)
- **Performance Optimized**: Early return prevents unnecessary log processing for filtered requests
**Impact**: Eliminated health check noise from logs while preserving all other access logging for debugging

### Documentation Updates (2025-10-02)
**Decision**: Updated all documentation to reflect new unified architecture
**Implementation**:
- Updated Project-Structure.md with refactored MTProto module details
- Enhanced Tools-Reference.md with improved invoke_mtproto documentation
- Updated MTProto-Bridge.md to show identical behavior between interfaces
- Created comprehensive Code-Quality.md documentation
- Updated README.md with new documentation references
**Impact**: Accurate documentation, clear interface comparisons, development guidelines

### Web Setup Interface Improvements (2025-09-09)
**Decision**: Enhanced web setup interface styling and user experience
**Changes Made**:
- **Input Text Size**: Increased to 1.1rem for better readability
- **Button Text Size**: Increased to 1rem for better prominence  
- **Hint Text Size**: Reduced to 0.85rem for more subtle appearance
- **Removed Excessive Text**: Eliminated redundant "Enter your phone to receive a code" instruction
- **Cleaner Layout**: Removed empty card styling from step div for cleaner appearance
**Impact**: Better visual hierarchy with larger interactive elements and smaller instructional text

### 2FA Authentication Route Fix (2025-09-09)
**Decision**: Added missing `/setup/2fa` route to complete the authentication flow
**Problem**: 2FA form was submitting to non-existent endpoint, causing 404 errors
**Solution**: 
- Added `@mcp_app.custom_route("/setup/2fa", methods=["POST"])` handler
- Implemented proper 2FA password validation with `client.sign_in(password=password)`
- Added error handling for invalid passwords and authentication failures
- Integrated with existing session management and config generation flow
**Impact**: Complete authentication flow now works for users with 2FA enabled

### Uniform Entity Formatting (2025-09-17)
**Decision**: Standardize chat/user objects via `build_entity_dict` across all tools
**Impact**: Consistent schemas, simpler client code, reduced duplication

### Entity Counts in Detailed Info (2025-09-17)
**Decision**: Added optional member/subscriber counts. `build_entity_dict` includes counts when present on entities. Introduced async `build_entity_dict_with_counts` used by `get_chat_info` to fetch counts via Telethon full-info requests.
**Impact**: `get_chat_info` now returns `members_count` for groups and `subscribers_count` for channels when available.

### Entity Enrichment (2025-09-17)
**Decision**: Renamed async helper to `build_entity_dict_enriched` and expanded enrichment:
- Groups/Channels: `about` (description)
- Private users: `bio`
**Impact**: `get_chat_info` returns richer profile data while lightweight tools still use compact schema.

### Multi-term Contact Search (2025-09-17)
**Decision**: `find_chats` accepts comma-separated terms; searches concurrently
**Impact**: Better discovery with merged, deduped results and uniform payloads

### File Sending Implementation (2025-10-01)
**Decision**: Unified `files` parameter accepting string or list, with auto-detection of URLs vs local paths
**Implementation**:
- Helper functions for modular design: `_validate_file_paths`, `_download_and_upload_files`, `_send_files_to_entity`, `_send_message_or_files`
- URLs supported in all server modes (http://, https://)
- Local paths restricted to stdio mode for security
- Multiple URLs downloaded and uploaded first to enable album sending
- Message becomes caption when files are sent
**Impact**: Enables AI to send images, documents, videos, and other files with messages

### Security Fixes for File Handling (2025-10-01)
**Decision**: Implemented comprehensive security measures to prevent SSRF attacks and local file access vulnerabilities
**Implementation**:
- **URL Security Validation**: `_validate_url_security()` function blocks localhost, private IPs, and suspicious domains
- **Enhanced HTTP Client**: Disabled redirects, added connection limits, security headers, and timeouts
- **File Size Limits**: Configurable maximum file size (default 50MB) with both header and content validation
- **Configuration Options**: `allow_http_urls`, `max_file_size_mb`, `block_private_ips` settings
- **Comprehensive Testing**: All security test cases passing (16/16)
**Impact**: Prevents attackers from accessing local services, internal networks, or metadata endpoints via file URLs

### Documentation Restructuring (2025-10-01)
**Decision**: Restructured README and created comprehensive documentation system for better user experience and maintainability
**Implementation**:
- **README Optimization**: Reduced from 1000+ lines to 202 lines with concise, skimmable structure
- **Documentation Organization**: Created docs/ folder with 7 specialized guides (Installation, Deployment, MTProto-Bridge, Tools-Reference, Search-Guidelines, Operations, Project-Structure)
- **Content Migration**: Moved detailed sections from README to appropriate specialized documentation
- **Deduplication**: Eliminated redundant content between README, CONTRIBUTING.md, and new docs
- **Security Documentation**: Created SECURITY.md with authentication model, risks, and best practices
- **Link Verification**: All documentation links verified and working correctly
**Impact**: Improved user experience with clear navigation, reduced maintenance overhead, and professional documentation structure

## Important Patterns and Preferences

### Web Interface Styling Patterns
1. **Visual Hierarchy**: Larger interactive elements (inputs, buttons) with smaller instructional text
2. **Clean Layout**: Minimal text, clear form structure, no empty visual elements
3. **Responsive Design**: Mobile-friendly interface with proper spacing and sizing
4. **Error Handling**: Clear error messages with context-specific guidance

### Authentication Flow Patterns
1. **Progressive Disclosure**: Show only necessary information at each step
2. **Session Persistence**: Maintain setup sessions throughout the flow
3. **Error Recovery**: Allow retry with clear error messages
4. **Automatic Cleanup**: TTL-based session cleanup prevents resource leaks

### VDS Testing and Diagnosis Methodology
1. **Environment Access**: SSH with credentials from `.env` file (`VDS_USER`, `VDS_HOST`, `VDS_PROJECT_PATH`)
2. **Deployment Process**: Use `./scripts/deploy-mcp.sh` for automated deployment with session management
3. **Container Management**: Use `docker compose` commands for container status, logs, and health checks
4. **Authentication Testing**: Use `curl` with proper MCP protocol headers and bearer tokens
5. **Log Analysis**: Monitor server logs for authentication flow and error patterns
6. **Session File Management**: Check `~/.config/fast-mcp-telegram/` for token-specific session files
7. **Traefik Integration**: Domain routing, SSL certificate management
8. **Health Monitoring**: Container health checks and endpoint monitoring
9. **Debugging Approach**: Systematic issue elimination through targeted testing
