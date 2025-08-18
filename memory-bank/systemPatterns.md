# System Patterns: tg_mcp

## Architecture Overview
The tg_mcp system follows a modular MCP server architecture with clear separation of concerns:

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
- **Query Handling**: Different logic for empty vs non-empty queries
- **Entity Resolution**: Automatic chat ID resolution from various formats

### 2. Tool Registration Pattern
- **FastMCP Integration**: Uses FastMCP framework for MCP compliance
- **Async Operations**: All Telegram operations are async for performance
- **Error Handling**: Comprehensive error logging and propagation
- **Request Tracking**: Unique request IDs for debugging
- **Parameter Flexibility**: Tools support optional parameters with sensible defaults

### 3. Data Flow Patterns
```
User Request → MCP Tool → Search Function → Telegram API → Results → Response
```

## Critical Implementation Paths

### Search Flow
1. **Input Validation**: Check query and chat_id parameters
2. **Mode Selection**: Determine global vs per-chat search
3. **Entity Resolution**: Convert chat_id to Telegram entity
4. **API Call**: Execute appropriate search method
5. **Result Processing**: Format and return results

### Current Search Logic
```python
if chat_id:
    # Per-chat search: Search within specific chat
    entity = await get_entity_by_id(chat_id)
    results = await _search_in_single_chat(...)
else:
    # Global search: Search across all chats
    results = await _search_global(...)
```

## Component Relationships

### Core Modules
- **server.py**: MCP server entry point and tool registration
- **search.py**: Search functionality implementation
- **client/connection.py**: Telegram client management
- **utils/entity.py**: Entity resolution and formatting

### Tool Dependencies
- **search_messages**: Depends on search.py and entity resolution
- **send_telegram_message**: Depends on messages.py with formatting support
- **get_dialogs**: Depends on messages.py for chat listing
- **get_statistics**: Depends on statistics.py
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

## Critical Implementation Details

### Search Query Handling
- **Empty Query + chat_id**: Returns all messages from chat
- **Non-empty Query + chat_id**: Searches for query within specific chat
- **Non-empty Query + no chat_id**: Global search across all chats
- **Empty Query + no chat_id**: Invalid (throws error)

### Entity Resolution
- Supports username, numeric ID, and channel ID formats
- Automatic conversion between different ID formats
- Error handling for invalid entities

### Result Formatting
- Consistent JSON structure across all tools
- Optional fields for media, forwards, replies
- Link generation for direct message access

### Shared Utilities (DRY)
- `src/utils/message_format.py`: `build_message_result`, `get_sender_info`
- `src/utils/entity.py`: `compute_entity_identifier`
These are used by both `search.py` and `messages.py` to avoid duplication and ensure consistent output.


