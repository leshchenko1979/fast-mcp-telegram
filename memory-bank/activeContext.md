## Current Work Focus
**Primary**: File sending capability for messaging tools (2025-10-01)

**Current Status**: Implemented file sending for `send_message` and `send_message_to_phone`. Supports single/multiple files via URLs (all modes) or local paths (stdio only). Multiple URLs sent as albums via download/upload pattern. Documentation updated in README.

## Active Decisions and Considerations

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
