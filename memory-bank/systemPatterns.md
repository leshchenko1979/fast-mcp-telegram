

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

### 1. Search Architecture
- **Dual Search Modes**: Global search vs per-chat search
- **Multi-Query Support**: Comma-separated terms with parallel execution
- **Query Handling**: Different logic for empty vs non-empty queries
- **Entity Resolution**: Automatic chat ID resolution from various formats
- **Deduplication**: Results merged and deduplicated based on message identity

### 2. Multi-Query Implementation
- **Input Format**: Single string with comma-separated terms (e.g., "deadline, due date")
- **Parallel Execution**: `asyncio.gather()` for simultaneous query processing
- **Deduplication Strategy**: `(chat.id, message.id)` tuple-based deduplication
- **Pagination**: Applied after all queries complete and results are merged

### 3. Tool Registration Pattern
- **FastMCP Integration**: Uses FastMCP framework for MCP compliance
- **Async Operations**: All Telegram operations are async for performance
- **Error Handling**: Comprehensive error logging and propagation
- **Request Tracking**: Unique request IDs for debugging
- **Parameter Flexibility**: Tools support optional parameters with sensible defaults

### 4. Data Flow Patterns
```
User Request → MCP Tool → Search Function → Telegram API → Results → Response
```

### 5. Multi-Query Search Flow
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

### 6. Deployment & Transport
- Transport: Streamable HTTP with SSE mounted at `/mcp`
- Ingress: Traefik `websecure` with Let's Encrypt, router `tg-mcp.redevest.ru`
- CORS: Permissive during development for Cursor compatibility
- Sessions: Telethon session bound into container at `/data/mcp_telegram`

### 7. Logging Strategy
- Loguru: File rotation + console
- Bridged Loggers: `uvicorn`, `uvicorn.access`, and `telethon` redirected into Loguru at DEBUG
- Traceability: Request IDs and detailed RPC traces enabled for prod diagnosis

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
- **server.py**: MCP server entry point and tool registration
- **search.py**: Search functionality implementation with multi-query support
- **client/connection.py**: Telegram client management
- **utils/entity.py**: Entity resolution and formatting

### Tool Dependencies
- **search_messages**: Depends on search.py and entity resolution
- **send_or_edit_message**: Depends on messages.py with formatting support and editing capabilities
- **search_contacts**: Depends on contacts.py for contact resolution

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
