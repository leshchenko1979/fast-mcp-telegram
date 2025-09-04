

## Architecture Overview
The fast-mcp-telegram system follows a modular MCP server architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   FastMCP       │    │   Telegram API  │
│   (AI Model)    │◄──►│   Server        │◄──►│   (Telethon)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                       ┌─────────────────┐
                       │   Tool Modules  │
                       │   (search, etc) │
                       └─────────────────┘
```

## Key Technical Decisions

### 1. Authentication Architecture
- **Token-Based Sessions**: Bearer tokens create isolated user sessions
- **Context Variables**: `_current_token` for request-scoped authentication
- **LRU Cache Management**: Configurable `MAX_ACTIVE_SESSIONS` with automatic eviction
- **Transport-Specific Auth**: Mandatory for HTTP, optional for stdio (legacy)
- **Session File Format**: `{token}.session` for multi-user isolation
- **Authentication Middleware**: `@with_auth_context` decorator on all MCP tools

### 2. Search Architecture
- **Dual Search Modes**: Global search vs per-chat search
- **Multi-Query Support**: Comma-separated terms with parallel execution
- **Query Handling**: Different logic for empty vs non-empty queries
- **Entity Resolution**: Automatic chat ID resolution from various formats
- **Deduplication**: Results merged and deduplicated based on message identity

### 3. Multi-Query Implementation
- **Input Format**: Single string with comma-separated terms (e.g., "deadline, due date")
- **Parallel Execution**: `asyncio.gather()` for simultaneous query processing
- **Deduplication Strategy**: `(chat.id, message.id)` tuple-based deduplication
- **Pagination**: Applied after all queries complete and results are merged

### 4. Tool Registration Pattern
- **FastMCP Integration**: Uses FastMCP framework for MCP compliance
- **Async Operations**: All Telegram operations are async for performance
- **Error Handling**: All tools return structured error responses instead of raising exceptions
- **Request Tracking**: Unique request IDs for debugging and correlation
- **Parameter Flexibility**: Tools support optional parameters with sensible defaults
- **Error Detection**: server.py checks for `{"ok": false, ...}` pattern in tool responses

### 5. Data Flow Patterns
```
User Request → MCP Tool → Search Function → Telegram API → Results → Response
```

### 6. Authentication Flow
```
HTTP Request → extract_bearer_token() → @with_auth_context → set_request_token() → _get_client_by_token() → Session Cache/New Session → Tool Execution
```

### 7. Multi-Query Search Flow
```
Input: "term1, term2, term3"
     ↓
Split into individual queries
     ↓
Create parallel search tasks
     ↓
Execute with asyncio.gather()
     ↓
Merge and deduplicate results
     ↓
Apply limit (no pagination)
     ↓
Return unified result set
```

### 8. Session Management Architecture
- **Token-Based Sessions**: Each Bearer token gets isolated session file `{token}.session`
- **LRU Cache Management**: In-memory cache with configurable `MAX_ACTIVE_SESSIONS` limit
- **Automatic Eviction**: Oldest sessions disconnected when cache reaches capacity
- **Session Location**: `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Auto-Cleanup on Auth Errors**: Invalid session files automatically deleted
- **Git Integration**: Proper .gitignore with .gitkeep for structure maintenance
- **Cross-Platform**: Automatic handling of macOS resource forks and permission differences
- **Permission Auto-Fix**: Automatic chown/chmod for container user access (1000:1000)
- **Backup/Restore**: Comprehensive session persistence across deployments

### 9. Deployment & Transport
- Transport: Streamable HTTP with SSE mounted at `/mcp`
- Ingress: Traefik `websecure` with Let's Encrypt, configurable router domain (defaults to `your-domain.com`)
- CORS: Permissive during development for Cursor compatibility
- Sessions: Standard `~/.config/fast-mcp-telegram/` directory with automatic permission management
- Volume Mounting: Standard user config directory mounts (`~/.config/fast-mcp-telegram:/home/appuser/.config/fast-mcp-telegram`)

### 10. Logging Strategy
- Loguru: File rotation + console
- Bridged Loggers: `uvicorn`, `uvicorn.access`, and `telethon` redirected into Loguru at DEBUG
- Traceability: Request IDs and detailed RPC traces enabled for prod diagnosis

### 11. Deployment Automation Patterns
- **Session Backup**: Automatic backup of `~/.config/fast-mcp-telegram/*` before deployment
- **Permission Management**: Auto-fix ownership (1000:1000) and permissions (664/775)
- **Cross-Platform Cleanup**: Automatic removal of macOS resource fork files (._*)
- **Git-Aware Transfer**: Exclude sessions directory from git transfers for security
- **Local-Remote Sync**: Bidirectional synchronization of session files
- **Error Recovery**: Robust error handling with detailed logging and counts

## Critical Implementation Paths

### Search Flow
1. **Input Validation**: Check query and chat_id parameters
2. **Query Normalization**: Split comma-separated terms into individual queries
3. **Mode Selection**: Determine global vs per-chat search
4. **Entity Resolution**: Convert chat_id to Telegram entity
5. **Parallel Execution**: Create and execute search tasks for each query
6. **Result Processing**: Merge, deduplicate, and format results

### Current Search Logic
```python
# Query normalization
queries: List[str] = [q.strip() for q in query.split(',') if q.strip()] if query else []

if chat_id:
    # Per-chat search: Search within specific chat
    entity = await get_entity_by_id(chat_id)
    search_tasks = [
        _search_chat_messages(client, entity, (q or ""), limit, chat_type, auto_expand_batches)
        for q in queries
    ]
    all_partial_results = await asyncio.gather(*search_tasks)
    # Merge and deduplicate results
else:
    # Global search: Search across all chats
    search_tasks = [
        _search_global_messages(client, q, limit, min_datetime, max_datetime, chat_type, auto_expand_batches)
        for q in queries if q and str(q).strip()
    ]
    all_partial_results = await asyncio.gather(*search_tasks)
    # Merge and deduplicate results
```

## Component Relationships

### Core Modules
- **server.py**: MCP server entry point, tool registration, and `/health` endpoint for session monitoring
- **search.py**: Search functionality implementation with multi-query support
- **client/connection.py**: Telegram client management with token-based sessions and LRU cache
- **utils/entity.py**: Entity resolution and formatting
- **config/settings.py**: Configuration management with dynamic version reading from pyproject.toml
- **~/.config/fast-mcp-telegram/**: Standard location for Telegram session files
- **scripts/deploy-mcp.sh**: Enhanced deployment script with session management

### Tool Dependencies
- **search_messages**: Depends on search.py and entity resolution
- **send_or_edit_message**: Depends on messages.py with formatting support and editing capabilities
- **search_contacts**: Depends on contacts.py for contact resolution

### Infrastructure Components
- **Dockerfile**: Multi-stage UV build with sessions directory creation
- **docker-compose.yml**: Production configuration with optimized volume mounts
- **.gitignore**: Git integration with sessions directory handling

## Design Patterns in Use

### 1. Factory Pattern
- Entity resolution from various ID formats
- Client connection management

### 2. Strategy Pattern
- Different search strategies for global vs per-chat
- Different result formatting strategies

### 3. Builder Pattern
- Result object construction with optional fields
- Link generation for messages

### 4. Parallel Processing Pattern
- Multiple query execution using asyncio.gather()
- Result aggregation and deduplication

### 5. Error Handling Pattern
- **Structured Error Responses**: All tools return `{"ok": false, "error": "message", ...}` instead of raising exceptions or empty results
- **Consistent Error Format**: Includes `request_id`, `operation`, `params` fields in all error responses
- **Server Error Detection**: server.py checks `isinstance(result, dict) and "ok" in result and not result["ok"]`
- **Graceful Degradation**: Tools handle errors internally rather than propagating exceptions to MCP layer
- **Request Tracking**: Each operation gets unique request_id for debugging and correlation
- **No Empty Results**: Tools like `search_messages` and `search_contacts` return errors instead of empty arrays when no results found

## Critical Implementation Details

### Search Query Handling
- **Empty Query + chat_id**: Returns all messages from chat
- **Non-empty Query + chat_id**: Searches for query within specific chat
- **Non-empty Query + no chat_id**: Global search across all chats
- **Empty Query + no chat_id**: Invalid (throws error)
- **Multi-term Query**: Comma-separated terms processed in parallel

### Multi-Query Processing
- **Input Parsing**: Split comma-separated string into individual terms
- **Parallel Execution**: Use asyncio.gather() for simultaneous searches
- **Deduplication**: Use set of (chat.id, message.id) tuples
- **Result Merging**: Collect results from all queries before pagination

### Entity Resolution
- Supports username, numeric ID, and channel ID formats
- Automatic conversion between different ID formats
- Error handling for invalid entities

### Result Formatting
- Consistent JSON structure across all tools
- Optional fields for media, forwards, replies
- Link generation for direct message access

### Shared Utilities (DRY)
- `src/utils/message_format.py`: `build_message_result`, `get_sender_info`, `build_send_edit_result`, `generate_request_id`, `log_operation_start`, `log_operation_success`, `log_operation_error`
- `src/utils/entity.py`: `compute_entity_identifier`
These are used by both `search.py` and `messages.py` to avoid duplication and ensure consistent output. The message formatting utilities now include comprehensive logging and error handling patterns.
