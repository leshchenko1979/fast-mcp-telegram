## Current Work Focus
**Completed**: MTProto Fake TLS Integration (2026-03-31)

**Implementation**:
- Added `TelethonFakeTLS` as dependency in `pyproject.toml`
- Updated `src/utils/proxy.py` with fake TLS detection and secret processing:
  - Base64 secrets with `7` prefix: strip leading `7` (e.g., `7i/UefJk...` → `i/UefJk...`)
  - Hex secrets with `ee` prefix: strip leading `ee` (e.g., `ee2fd479...` → `2fd479...`)
- Integrated `ConnectionTcpMTProxyFakeTLS` into all client creation paths:
  - `src/client/connection.py` (main client)
  - `src/server_components/web_setup.py` (web setup)
  - `src/cli_setup.py` (CLI setup)
- Graceful fallback with warning if `TelethonFakeTLS` not installed

**Verified Working**: CLI setup authenticated successfully via MTG proxy `144.31.188.163:443`

---

**Completed**: MTProto Proxy Support (2026-03-31)

**Implementation**:
- Added `mtproto_proxy` config field to `ServerConfig` via `MTPROTO_PROXY` env var
- Created `src/utils/proxy.py` with `MTProtoProxy` NamedTuple and URL parsing
- Supports `tg://proxy?server=...&port=...&secret=...` and `host:port:secret` formats
- Integrated `ConnectionTcpMTProxyRandomizedIntermediate` into:
  - `src/client/connection.py` (main client)
  - `src/server_components/web_setup.py` (setup flow)
  - `src/cli_setup.py` (CLI setup)


---

**Completed**: CI/CD pipeline migration to GitHub Actions + GHCR (2026-03-30)

**Implementation**:
- Migrated from manual `deploy-mcp.sh` to GitHub Actions workflow matching pdf-extract pattern
- Created `.github/workflows/deploy.yml` with build-push and deploy jobs
- Updated `docker-compose.yml` to use GHCR image + named volume for sessions
- Created `scripts/sync-remote-config.sh` for manual sync
- Updated `.vscode/tasks.json` with new tasks
- Updated README.md, docs/Deployment.md, docs/Installation.md
- Marked `scripts/deploy-mcp.sh` as legacy

**Operational notes**: Deployment is automatic on push to main. Sessions persist in Docker named volume.

---

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
1. **Environment Access**: SSH with credentials from `.env` file (`SSH_USER`, `SSH_HOST`)
2. **Deployment Process**: GitHub Actions auto-deploys on push to main. Manual sync via `./scripts/sync-remote-config.sh`
3. **Container Management**: Use `docker compose` commands for container status, logs, and health checks
4. **Authentication Testing**: Use `curl` with proper MCP protocol headers and bearer tokens
5. **Log Analysis**: Monitor server logs for authentication flow and error patterns
6. **Session Management**: Sessions stored in Docker named volume `telegram-sessions`
7. **Health Monitoring**: Container health checks and endpoint monitoring
8. **Debugging Approach**: Systematic issue elimination through targeted testing
