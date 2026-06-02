### 2026-06-02
- **PR #103 — Data URI file uploads:** Added `data:` URI (base64) support in `send_message` `files` parameter. Clients can now attach inline files without filesystem access or hosting. `_parse_data_uri()` parses MIME types, validates base64, infers filenames via `_MIME_TO_EXT` mapping. `_validate_file_paths()` accepts data: URIs in all transport modes. 18 TDD tests, 628 total passed. Sourcery rate-limited, CodeQL green.

- **PR #102 — Forum topic date filtering:** Removed `"min_date and max_date are not supported for replies mode"` error in `core.py`. `reply_to_id` (forum topics) now supports `min_date`/`max_date` filters. Changes in 4 files: `topic_search.py` (added `min_date` param), `forum_replies.py` (threaded date params through topic search chain), `replies.py` (threaded dates through direct replies + thread search), `core.py` (removed date filter error for replies mode, kept for `message_ids`). `MESSAGE_IDS` mode still blocks date filters (reads by ID, dates make no sense). 87 tests pass (27 existing + 3 new: `test_replies_accepts_min_date`, `test_replies_accepts_max_date`, `test_replies_accepts_date_range`). CI green, merged. Sourcery GH App rate-limited (5/7 weekly budget used).

### 2026-06-01
- **0.26.0 — Parallel search concurrency:** `search_global` configurable semaphore + timeout for multi-term parallel gather; `_run_with_limits` extracted from nested closure for testability; `_round_robin_merge_iters` extracted for Sourcery quality; `find_chats` `max_concurrent` semaphore for multi-term search; 4 unit tests for search_mode concurrency; Sourcery CLI fixes applied. PRs #83, #91, #92, #93 merged. GitHub release + CI green.
- **0.27.0 — Inactivity-based session cleanup:** Replaced `cleanup_failed_sessions()` (10 errors → delete) with `_cleanup_inactive_sessions()` — deletes `.session` files with mtime >30 days old. mtime-only, no tracking file. Periodic cleanup (startup + every 24h). Default session protection. TOCTOU guard. GitHub release + CI green; Telegram RU posted, EN failed (bot not invited to `5131784155`).
- **Post-release fixes:** `TELEGRAM_INACTIVE_SESSION_DAYS` env var (0=disable), documented in `docs/Installation.md` Configuration Reference. PRs #95, #96, #97, #98 merged.
- **PR #99 — Config-driven session retention:** Moved `TELEGRAM_INACTIVE_SESSION_DAYS` from `os.environ.get()` in `connection.py` to pydantic `ServerConfig.inactive_session_days` field with `validation_alias=AliasChoices(...)`. Removed `import os` (was only for this env var). Patched all threshold-based tests to mock `get_config()` so they aren't brittle to env var changes. CI green, merged.
- **Qwen3.7 review process:** Subagent spawned for skeptical review of session cleanup changes; 31 findings for tracking-file version, fixed 2 real bugs (mtime touch on connection, default session protection). Sourcery GH App rate-limited for the remainder of the week.
- **Release process extracted:** `RELEASE-PROCESS.md` extracted from `.cursor/skills/release-notes/SKILL.md`, `alexey-coding-process.md` updated with Qwen3.7 review requirement.

### 2026-05-28
- **Session ACL Phase 2 (PR #58 merged):** `allow_mtproto` per listed token (default false); `allow_global_search: false` blocks raw MTProto; unified `_mtproto_denial_for_rule` for tool + HTTP bridge; `ACL_DENY_UNLISTED_TOKENS` for strict multi-tenant; config load warnings; plain-language operator docs.
- **Bot Token Runtime Auth (PR #62):** Added `BOT_API_TOKEN` env var to `ServerConfig`. When `BOT_API_TOKEN` is set and no session file exists, `connection.py` auto-authenticates via `client.start(bot_api_token=...)` before `verify_authorized_connection()`. No interactive setup needed — enables Glama "Try in Browser" and simplifies bot account onboarding. Docs updated (README, Installation.md, .env.example, glama.json).

### 2026-05-27
- **0.21.0 — Session ACL Phase 1.5:** PR #57 merged; optional operator `blocked_peers` YAML list, dual pre/post enforcement (id + username), MTProto param gate; PyPI + GHCR. GitHub release `0.21.0`.
- **Phase 1.5 — Session ACL blocked_peers:** Operator-configured deployment denylist; dual pre/post enforcement (id + username post-check); MTProto shallow scan before lane gate; SECURITY.md shared-host checklist; tests in `test_session_acl.py`.
- **Phase 1 closeout (`master`):** Post-release fixes — CI voice-transcription test client pass-through (`4f76129`), Sourcery follow-ups (PR #56), release CI gate in skill docs, test mock `sender_id`/`forward` defaults (~141s → ~1s local full suite).
- **0.20.0 — Session ACL Phase 1:** GitHub release `0.20.0`; opt-in `ACL_ENABLED` / `ACL_CONFIG_PATH` on http-auth, per-token chat lanes, `read_only`, empty-lane hard deny, listed-token MTProto block, fail-closed startup, SECURITY.md + Installation docs.
- **Session ACL Phase 1 closed (`master`, PR #56):** Empty-lane hard deny (pre-check + post-filter), listed-token MTProto block, startup validation (`read_only` requires `chats`, malformed token entries), SECURITY.md operator runbook, integration tests.
- **Roadmap lanes (`master`):** Trust / Telemetry / QA-Gategrid — telemetry informs QA triage, GG benchmark validates, GG gating enforces on PR.
- **Session ACL MVP on `master`:** opt-in `ACL_ENABLED`, static `acl.yaml`, MCP + MTProto enforcement. Direction: agent guardrails — [ADR 0001](../docs/adr/0001-agent-scoped-session-acl.md); Phase 2 next.

### 2026-05-25
- **0.19.1 — bearer token path traversal fix:** PR #53 merged. Reject non–URL-safe bearer tokens; resolve session files under `session_directory` only (`session_token_validation.py`). GitHub release `0.19.1`; PyPI via publish workflow. Reporter credit: [DavidCarliez](https://github.com/DavidCarliez). 514 tests pass.

### 2026-05-24
- **0.19.0 — account-prefixed MCP tools:** PR #52 merged. Optional `PREFIX_MCP_TOOLS_WITH_ACCOUNT` prefixes tools per Bearer session (`username_` or `{user_id}_`). GitHub release `0.19.0`; PyPI publish on release; GHCR rebuild on `master` push. 499 tests pass on `master`.

### 2026-05-19
- **0.18.1 / FastMCP 3.3 slim**: Production dependency `fastmcp-slim[server]>=3.3` replaces `fastmcp` metapackage (3.2.4). Lock upgraded with `uv lock --upgrade`. 482 tests pass. GitHub release `0.18.1` published. GHCR compressed image (linux/amd64): ~39.31 MiB → ~39.28 MiB (−40 KB, −0.10%).

### 2026-05-18
- **Forum in-topic replies (2026-05-18):** Offset jump + widen + legacy scan; enrich/id-window fallbacks; `_message_has_displayable_content` (search stubs use `.message` not `.text`). Docs: `Tools-Reference.md`, [forum-in-topic-replies.md](forum-in-topic-replies.md). Tests: `tests/test_thread_scope_replies_fetch.py`. Live: `67599`, `telemtrs/13204`.
- **get_messages thread_scope (#49)**: `thread_scope` (`auto`/`full`/`direct`) on `get_messages`. Forum **topic ids** → GetReplies; in-topic message ids → topic search + filter; supergroup `full` → `SearchRequest(top_msg_id=...)`. Channel posts → discussion group. Docs: `Tools-Reference.md`, `mcp_tool_types.py`.

### 2026-05-04
- **README Features audit**: `README.md` Features table aligned with code and docs — Multi-User Authentication → `docs/Installation.md#remote-setup-http-auth`, Dual Transport → `#overview` with stdio / `http-auth` / optional `http-no-auth`, MTProto Proxy → `#mtproto-proxy`, Secure File Handling uses `:paperclip:` (distinct from Folder Filtering), Bot Chat Detection → `docs/Tools-Reference.md#uniform-entity-schema`, High Performance drops unsubstantiated connection pooling, Production Reliability uses “configurable logging”. Summary in `activeContext.md`.

### 2026-04-24
- **find_chats filter+date performance and correctness** (`src/tools/chat_discovery/`): `include_peers` path now keeps `pid → Telethon entity` for date fallbacks, sync last-activity window when `GetPeerDialogs` returns message dates, bounded parallel `get_entity` (semaphore 8, optional debug timing), `GetPeerDialogs` warning + `min(len)` pairing when `dialogs`/`messages` lengths differ, early `dialog.date` reject in `_find_chats_by_filter_flags` before flag matching. Doc updates: `find_chats_impl`, `docs/Tools-Reference.md`, `_DESC_FIND_CHATS`. `GET_PEER_DIALOGS_CHUNK_SIZE` left at 50 (conservative; raising needs layer limit confirmation). New tests for per-peer `iter_messages` and GPD length mismatch.

### 2026-04-14
- **Todo list MCP serialization**: `get_messages` / `build_message_result` — `MessageMediaToDo` completion `completed_by` can be a Telethon `Peer` (e.g. `PeerUser`); was assigned raw and failed FastMCP structured output. Normalized to integer Telegram id using `_forward_peer_id_and_type_label`; legacy `int` unchanged; non-int peer ids omitted. Regression tests in `tests/test_todo_media_placeholder.py`.

### 2026-04-13
- **Agent-friendly MCP tools**: `tools_register.py` — `description=` and `ToolAnnotations(title=...)` on all eight tools; concise docstrings; `mcp_tool_types.py` with `Annotated` + Pydantic `Field` for parameter-level schema text; `find_chats` / `find_chats_impl` return type `dict[str, Any]`. Full examples remain in `docs/Tools-Reference.md`. All 409 tests pass.
- **Connection error handling DRY**: `find_connection_exception` and `log_connection_error_response` in `error_handling.py`; `with_error_handling` handles `SessionNotAuthorizedError` and `TelegramTransportError` (including `__cause__` unwrap); tools return error dicts caught and re-raised as `ToolError` for proper `isError=True`. `search/search_mode.py` `_handle_query_mode` and `invoke_mtproto` use the helper directly.

### 2026-04-01
- **Bot Chat Type Split**: Added "bot" as separate chat type from "private". Bots detected via `getattr(entity, 'bot', False)`. Bots not filtered by public parameter and get bio enrichment same as private users.
- **Folder Filtering**: Added `folder` parameter to `find_chats` tool supporting int ID or str name. Folder list fetched via `GetDialogFiltersRequest` with 5-minute caching. Folder 0 (default) shows as `folder_id: null` on Dialog objects. Title is a `TextWithEntities` object - extract via `folder.title.text`.
- **New Tests**: Added 31 tests in `tests/test_contacts_bot_folder.py` covering bot detection, folder resolution, caching, and integration. Updated 4 existing tests in `test_contacts_date_filtering.py` for folder parameter.

### 2026-03-31
- **MTProto Fake TLS Integration Complete**: Added `TelethonFakeTLS` package for fake TLS (EE prefix) proxy support. Secret processing strips markers: base64 `7` prefix and hex `ee` prefix. CLI setup verified working via MTG proxy.
- **MTProto Fake TLS Investigation**: Discovered Telethon does NOT natively support Fake TLS (EE prefix) proxies. Verified via Context7 docs and web search.
- **Solution Found**: `TelethonFakeTLS` package provides fake TLS support - available on PyPI
- **Secret Format Discovery**: MTG fake TLS secrets are base64 encoded, must remove leading "7" for TelethonFakeTLS (e.g., `7i/UefJk...` → `i/UefJk...`). Hex secrets strip `ee` prefix.
- **Connection Verified**: Successfully connected to MTG proxy `144.31.188.163:443` using `TelethonFakeTLS.ConnectionTcpMTProxyFakeTLS`
- **MTProto Proxy Support**: Added `MTPROTO_PROXY` environment variable for Telegram connection via standard MTProto proxy
- **New File**: `src/utils/proxy.py` with `MTProtoProxy` NamedTuple and URL parsing (supports `tg://proxy?...` and `host:port:secret` formats)
- **Proxy Integration**: Uses `ConnectionTcpMTProxyRandomizedIntermediate` for obfuscated MTProto connection
- **Refactored Helper**: Added `build_mtproto_client_args()` in proxy.py for centralized proxy kwargs building and stricter fake TLS detection
- **Files Modified**: `src/config/server_config.py`, `src/config/settings.py`, `src/client/connection.py`, `src/server_components/web_setup.py`, `src/cli_setup.py`, `pyproject.toml`, `src/utils/proxy.py`

### 2026-03-27
- **Web setup UX consistency**: Moved setup interactions to a nested HTMX target (`#setup-flow`) so the top-level mode buttons remain visible and users can restart flows predictably.
- **Flood-error path fix**: `PhoneNumberFloodError` on `/setup/phone` now returns the phone-entry fragment with an error message and cleans temporary session artifacts instead of showing a broken code-entry step.
- **Setup error rendering unification**: HTMX-facing setup failures now render `fragments/error.html` instead of JSON payloads, preventing raw JSON from being injected into the UI.
- **Fragment polish**: Added reauthorize-phone error display, moved 2FA hint above password field, normalized headings, added return-to-setup actions on success/config, and hardened config copy interaction feedback.
- **Same-step error UX**: Delete and reauthorize token failures (and reauth phone step expiry) return `delete_session_form` / `reauthorize_token_form` with inline errors; `error.html` reserved for unavoidable wizard failures; shared **Back to setup** and `.error` styling on terminal errors.
- **Coverage**: Extended `tests/test_web_setup.py` for same-step templates, fragment visibility, and invalid setup-session HTML error behavior.

### 2026-03-15
- **FastMCP 3 Bearer Token Fix**: Switched to FastMCP's auth=TokenVerifier to fix token extraction failure (upstream bug PrefectHQ/fastmcp#596). Created SessionFileTokenVerifier validating tokens via session file existence. `with_auth_context` now uses `get_access_token()` instead of `get_http_headers()`. Auth only enabled in http-auth mode. All 250 tests pass.
- **2FA Password Hint Display**: Fixed display of 2FA password hint in web setup flow. Template had conditional hint display but backend never passed it. Now fetches hint from Telegram API via GetPasswordRequest when SessionPasswordNeededError is raised, stores in setup session state, and passes to 2fa_form template in all three render paths (initial 2FA prompt, PasswordHashInvalidError retry, generic exception retry). Added _2fa_form_context helper for DRY template context building.

### 2026-02-28
- **Unified get_messages API (PR #960)**: Consolidated search_messages_in_chat and read_messages into a single get_messages tool
- **Universal Replies Support**: Added reply_to_id parameter for unified handling of channel post comments, forum topic messages, and message replies
- **Auto-Detection**: Automatically detects channel posts with discussion groups and uses appropriate chat
- **5 Operating Modes**: Search in chat, browse chat, read by IDs, get replies, search in replies
- **Parameter Conflict Validation**: Automatic rejection of invalid parameter combinations (message_ids+reply_to_id, message_ids+query)
- **Discussion Metadata**: Returns discussion_chat_id and discussion_total_count for channel posts with discussions
- **Code Cleanup**: Removed deprecated tool aliases and unused internal functions
- **Mode Resolution**: Extracted clean orchestration with MessageRetrievalMode enum and dedicated handlers
- **Comprehensive Testing**: 215 tests pass with full coverage of all modes
- **Documentation**: Updated all docs to use new get_messages API with reply_to_id

### 2026-02-19
- **invoke_mtproto Hash Sanitization Fix (Issue 11)**: Type-preserving hash handling - strings kept for messages.ImportChatInvite, integers for state methods; invalid types removed instead of coercing to 0
- **RPC Error Normalization (Issue 11)**: Machine-readable error_code in invoke_mtproto responses using Telethon rpc_errors_dict/rpc_errors_re reverse mapping; supports USER_ALREADY_PARTICIPANT, INVITE_HASH_EXPIRED, etc.
- **Error Response Schema**: Added optional error_code parameter to build_error_response and log_and_build_error
- **Tests**: New tests/test_mtproto.py with 11 tests for hash sanitization and error normalization
- **Documentation**: Tools-Reference.md updated with hash parameter behavior and error_code field

### 2026-01-28
- **Reply Markup Support**: Added automatic extraction and serialization of reply markup (keyboard buttons and inline buttons) from received messages
- **Comprehensive Markup Types**: Supports ReplyKeyboardMarkup (keyboard buttons), ReplyInlineMarkup (inline buttons), ReplyKeyboardForceReply, and ReplyKeyboardHide
- **Button Structure Serialization**: Extracts button text, types, URLs, callback data, and other interactive elements in LLM-friendly format
- **Integration Points**: Added to both `build_message_result` (for read/search operations) and `build_send_edit_result` (for send/edit operations)
- **Zero Overhead**: Only adds `reply_markup` field when markup is present, no performance impact on messages without markup
- **Comprehensive Testing**: Added 19 new tests covering all markup types, button types, edge cases, and error handling scenarios
- **Testing Verified**: All 159 tests pass (140 existing + 19 new), comprehensive coverage of reply markup functionality

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

## What Works (Functional Status)

### Core Functionality ✅
- **MCP Server**: FastMCP-based server with full Telegram integration
- **Configuration System**: Modernized pydantic-settings based configuration with three clear server modes
- **Unified Message API**: `get_messages` consolidates search, browse, read by IDs, and post comments into single tool
- **Post Comments Support**: Fetch and search channel post discussion threads with discussion metadata
- **Message Search**: `search_messages_globally` for global search, `get_messages` for per-chat operations
- **Message Operations**: Split into `send_message` and `edit_message` for clear intent separation
- **File Sending**: Send single or multiple files via URLs (all modes) or local paths (stdio mode only)
- **Contact Management**: Search and get contact details with last_activity_date filtering
- **Phone Messaging**: Send messages to phone numbers not in contacts (with file support)
- **MTProto Access**: Raw method invocation capability
- **Connection Management**: Automatic reconnection and error handling

### Advanced Features ✅
- **Bot Chat Type**: Separate "bot" type from "private". Bots get bio enrichment and are never filtered by public parameter.
- **Folder Filtering**: Filter dialogs by folder ID or name. Folder list cached for 5 minutes via `GetDialogFiltersRequest`.
- **Multi-Query Search**: Comma-separated terms with parallel execution and deduplication
- **LLM-Optimized Media**: Lightweight placeholders instead of raw Telethon objects
- **Todo List Support**: Automatic parsing of Telegram Todo lists with structured completion data
- **Poll Support**: Comprehensive parsing of Telegram polls with vote counts and metadata
- **Structured Logging**: Stdlib logging migration - removed complex Loguru bridge
- **Logging Spam Reduction**: Module-level filtering reduces Telethon noise by 99%
- **Consistent Error Handling**: All tools return structured error responses; `@with_error_handling` raises `ToolError` for proper MCP `isError=True` signaling
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
- **Reply Markup Support**: Automatic extraction and serialization of interactive elements (keyboard buttons, inline buttons, force reply, hide keyboard) from received messages

### Deployment & Integration ✅
- **HTTP Transport**: FastMCP over HTTP with CORS support
- **Cursor Integration**: Verified working with Cursor IDE
- **GitHub Actions CI/CD**: Automatic build and deploy to VDS on push to main
- **GHCR Integration**: Docker images hosted on GitHub Container Registry
- **Environment Management**: Proper credential handling and session management
- **Dependency Management**: setuptools with pyproject.toml for package management
- **Session Persistence**: Docker named volume for sessions (telegram-sessions)

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
- **2FA Password Hint Display**: Implemented display of 2FA password hint in web setup flow by fetching from `account.GetPasswordRequest`, storing in setup state, and passing to 2fa_form template via _2fa_form_context helper (2026-03-15)
- **2FA Authentication Route Fix**: Added missing `/setup/2fa` route handler with proper password validation, error handling, and integration with session management and config generation flow (2025-09-09)
- **Documentation and Configuration Updates**: Updated all documentation to reflect current codebase state, created comprehensive .env.example template, updated README with three server modes, simplified project structure, and updated docker-compose.yml and deploy script to use new configuration system (2025-09-08)
- **Configuration System Modernization**: Implemented comprehensive pydantic-settings based configuration system with three clear server modes (stdio, http-no-auth, http-auth) and automatic CLI parsing. Created ServerConfig and SetupConfig classes with smart defaults and validation (2025-09-08)
- **Server Entrypoint Slimming**: `src/server.py` now registers routes (`register_routes`) and tools (`register_tools`) on startup; tool and route logic moved to dedicated modules (2025-09-08)
- **Tool Splitting Implementation**: Successfully implemented Item 1 from GitHub issue #1 by splitting ambiguous tools into single-purpose tools to eliminate LLM agent errors. Split `search_messages` into `search_messages_globally` and `search_messages_in_chat`, and `send_or_edit_message` into `send_message` and `edit_message`. Updated documentation and memory bank accordingly (2025-01-07)
- **FastMCP 3 Bearer Token Fix**: Fixed token extraction failure in FastMCP 3 by switching to auth=SessionFileTokenVerifier. get_http_headers() returns wrong/empty for Streamable HTTP (bug #596). Auth middleware extracts token before Mount; tools use get_access_token() dependency. All 250 tests pass (2026-03-15)
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