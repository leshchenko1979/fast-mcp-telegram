## Current Work Focus
**Completed**: Web setup UX, consistency, and same-step errors (2026-03-27)

**Implementation**:
- Nested `#setup-flow` HTMX target; toolbar `showForm` reloads with `?branch=` when branch sections are missing after swaps
- Phone/reauthorize/delete token steps use inline `<div class="error">` on the matching fragment
- Reauthorize token step and delete branch no longer use `error.html` for validation or missing session
- Terminal `error.html` uses `.error` for the message and **Back to setup**
- Tests in `tests/test_web_setup.py` cover delete/reauthorize same-step responses

**Operational notes**: Setup sessions remain in-memory and process-local; single-replica assumptions still apply.

---

**Completed**: FastMCP 3 Bearer Token Fix (2026-03-15)
SessionFileTokenVerifier validates tokens via session file existence. `with_auth_context` uses `get_access_token()` bypassing upstream bug #596. All 250 tests pass.

---

## Active Decisions and Considerations

### Web Setup Interface Enhancement (2025-11-18)
Session management via `/setup` endpoint with Create, Reauthorize, Delete options. Token-based security with phone verification for reauth.

### Public Visibility Filtering (2025-11-19)
`public` parameter excludes private chats (DMs) from visibility filtering - they always appear. Groups/channels filtered normally.

### invoke_mtproto TL Construction (2025-11-25)
Automatic TL object construction from JSON dictionaries with `"_"` key. Recursive nested support for complex types.

### Multiple Chat Type Filtering (2025-11-20)
`chat_type` accepts comma-separated values (`"private,group"`). Case-insensitive, whitespace-tolerant validation.

### Connection Stability (2025-10-17)
Exponential backoff (2^failure_count, max 60s), circuit breaker (5 failures/5 min), session health monitoring.

### Unified Session Configuration (2025-10-11)
SessionConfig with session_name/session_path. HTTP_AUTH uses random tokens, STDIO/HTTP_NO_AUTH use configured names.

---

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
