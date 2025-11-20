# 🔧 Tools Reference

## Overview

This MCP server provides comprehensive Telegram integration tools optimized for AI assistants. All tools support uniform entity schemas, consistent error handling, and MCP ToolAnnotations for better AI agent decision-making.

## ToolAnnotations for AI Guidance

All tools include MCP ToolAnnotations to help AI agents make informed decisions:

- **`openWorldHint=True`**: All tools interact with external Telegram APIs
- **`readOnlyHint=True`**: Applied to search and informational tools (safe to retry)
- **`destructiveHint=True`**: Applied to messaging and state-changing tools (use cautiously)
- **`idempotentHint=True`**: Applied to safely repeatable operations (can retry safely)

## AI-Optimized Parameter Constraints

This MCP server uses `Literal` parameter types to guide AI model choices and ensure valid inputs:

- **`parse_mode`**: Constrained to `"markdown"`, `"html"`, or `"auto"` (default: `"auto"`)
- **`chat_type`**: Limited to `"private"`, `"group"`, or `"channel"` for search filters
- **Enhanced Validation**: FastMCP automatically validates these constraints
- **Better AI Guidance**: AI models see only valid options, reducing errors

## Supported Chat ID Formats

All tools that accept a `chat_id` parameter support these formats:
- `'me'` - Saved Messages (your own messages)
- `@username` - Username (without @ symbol)
- `123456789` - Numeric user ID
- `-1001234567890` - Channel ID (always starts with -100)

## Uniform Entity Schema

All tools return chat/user objects in the same schema via `build_entity_dict`:

```json
{
  "id": 133526395,
  "title": "John Doe",           // falls back to full name or @username
  "type": "private",            // one of: private | group | channel
  "username": "johndoe",        // if available
  "first_name": "John",         // users
  "last_name": "Doe",           // users
  "members_count": 1234,          // groups (when available)
  "subscribers_count": 56789      // channels (when available)
}
```

`find_chats` returns a list of these entities. Message search results include a `chat` field in the same format.

## Uniform Message Schema

All message-returning tools (search, read, send, edit) return messages in a consistent schema via `build_message_result`:

```json
{
  "id": 12345,                    // Message ID (unique within chat)
  "date": "2024-01-15T10:30:00",  // ISO format timestamp
  "chat": {                       // Chat entity (same uniform schema as above)
    "id": 133526395,
    "title": "John Doe",
    "type": "private",
    "username": "johndoe"
  },
  "text": "Hello world!",          // Message content (text/caption)
  "link": "https://t.me/johndoe/12345",  // Direct Telegram link (when available)
  "sender": {                     // Sender entity (same uniform schema, optional)
    "id": 133526395,
    "title": "John Doe",
    "type": "private",
    "username": "johndoe"
  },
  "reply_to_msg_id": 12344,       // ID of message being replied to (optional)
  "media": {                      // Media attachment info (optional, lightweight)
    "mime_type": "image/jpeg",    // File MIME type
    "filename": "photo.jpg",      // Original filename (if available)
    "approx_size_bytes": 2048576  // Approximate file size
  },
  "forwarded_from": {             // Forwarded message info (optional)
    "id": 999999999,
    "title": "Original Channel",
    "type": "channel",
    "username": "original_channel"
  }
}
```

**Message Content Priority:**
1. `text` - Primary message content
2. `message` - Alternative text field
3. `caption` - Media caption (if no text)

**Media Attachments:**
- Lightweight metadata only (not actual files)
- Includes MIME type, filename, and approximate size
- Covers: photos, documents, videos, audio, voice messages, etc.

**Forwarded Messages:**
- `forwarded_from` contains original sender info
- Uses same entity schema as chat/sender fields

## Tools Reference

### 🔍 search_messages_globally
**Search messages across all Telegram chats**

```typescript
search_messages_globally(
  query: str,                    // Search terms (comma-separated, required)
  limit?: number = 50,          // Max results
  chat_type?: 'private'|'group'|'channel', // Filter by chat type
  public?: boolean,             // Filter by public discoverability (true=with username, false=without username). Never applies to private chats.
  min_date?: string,            // ISO date format
  max_date?: string             // ISO date format
) -> {
  messages: Message[],          // Array of message objects
  has_more: boolean,            // Whether more results exist
  total_count?: number,         // Total matching messages (if requested)
}
```

**Examples:**
```json
// Global search across all chats
{"tool": "search_messages_globally", "params": {"query": "deadline", "limit": 20}}

// Multi-term global search (comma-separated)
{"tool": "search_messages_globally", "params": {"query": "project, launch", "limit": 30}}

// Partial word search (finds "project", "projects", etc.)
{"tool": "search_messages_globally", "params": {"query": "proj", "limit": 20}}

// Filtered by date and type
{"tool": "search_messages_globally", "params": {
  "query": "meeting",
  "chat_type": "private",
  "min_date": "2024-01-01"
}}

// Search only in public groups and channels
{"tool": "search_messages_globally", "params": {
  "query": "announcement",
  "public": true
}}

// Search private groups only
{"tool": "search_messages_globally", "params": {
  "query": "team",
  "chat_type": "group",
  "public": false
}}
```

### 📍 search_messages_in_chat
**Search messages within a specific Telegram chat**

```typescript
search_messages_in_chat(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  query?: str,                   // Search terms (optional, returns latest if omitted)
  limit?: number = 50,          // Max results
  min_date?: string,            // ISO date format
  max_date?: string             // ISO date format
)
```

**Examples:**
```json
// Search in specific chat
{"tool": "search_messages_in_chat", "params": {"chat_id": "-1001234567890", "query": "launch"}}

// Get latest messages from Saved Messages (no query = latest messages)
{"tool": "search_messages_in_chat", "params": {"chat_id": "me", "limit": 10}}

// Multi-term search in chat (comma-separated)
{"tool": "search_messages_in_chat", "params": {"chat_id": "telegram", "query": "update, news"}}

// Partial word search in chat
{"tool": "search_messages_in_chat", "params": {"chat_id": "me", "query": "proj"}}
```

**💡 Search Tips:**
- **No query**: Returns latest messages from the chat
- **Simple terms**: Use common words that appear in messages
- **Multiple terms**: Use comma-separated words for broader results
- **Partial words**: Use shorter forms to catch variations (e.g., "proj" finds "project", "projects")

### 💬 send_message
**Send new messages with formatting and optional files**

```typescript
send_message(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  message: str,                  // Message content (becomes caption when files sent)
  reply_to_msg_id?: number,      // Reply to specific message
  parse_mode?: 'markdown'|'html'|'auto' = 'auto', // Text formatting (auto-detect by default)
  files?: string | string[]      // File URL(s) or local path(s)
)
```

**File Sending:**
- `files`: Single file or array of files (URLs or local paths)
- **URLs**: Public HTTP/HTTPS URLs are supported. SSRF protections block localhost, private IP ranges, and cloud metadata endpoints by default.
- **Local paths**: Only in stdio mode (blocked in HTTP modes)
- **Size limits**: Download size capped (configurable)
- Supports: images, videos, documents, audio, and other file types
- Multiple files are sent as an album when possible
- Message becomes the file caption when files are provided

**Examples:**
```json
// Send text message
{"tool": "send_message", "params": {
  "chat_id": "me",
  "message": "Hello from AI! 🚀"
}}

// Send file from URL
{"tool": "send_message", "params": {
  "chat_id": "me",
  "message": "Check this document",
  "files": "https://example.com/document.pdf"
}}

// Send multiple images as album
{"tool": "send_message", "params": {
  "chat_id": "@channel",
  "message": "Project screenshots",
  "files": ["https://example.com/img1.png", "https://example.com/img2.png"]
}}

// Send local file (stdio mode only)
{"tool": "send_message", "params": {
  "chat_id": "me",
  "message": "Report attached",
  "files": "/path/to/report.pdf"
}}

// Reply with formatting
{"tool": "send_message", "params": {
  "chat_id": "@username",
  "message": "*Important:* Meeting at 3 PM",
  "parse_mode": "markdown",
  "reply_to_msg_id": 67890
}}
```

### ✏️ edit_message
**Edit existing messages with formatting**

```typescript
edit_message(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  message_id: number,            // Message ID to edit (required)
  message: str,                  // New message content
  parse_mode?: 'markdown'|'html'|'auto' = 'auto' // Text formatting (auto-detect by default)
)
```

**Examples:**
```json
// Edit existing message
{"tool": "edit_message", "params": {
  "chat_id": "-1001234567890",
  "message_id": 12345,
  "message": "Updated: Project deadline extended"
}}

// Edit with formatting (auto-detected)
{"tool": "edit_message", "params": {
  "chat_id": "me",
  "message_id": 67890,
  "message": "*Updated:* Meeting rescheduled to 4 PM"
}}

// Edit with explicit formatting
{"tool": "edit_message", "params": {
  "chat_id": "me",
  "message_id": 67890,
  "message": "<b>Updated:</b> Meeting rescheduled to 4 PM",
  "parse_mode": "html"
}}
```

### 📖 read_messages
**Read specific messages by ID**

```typescript
read_messages(
  chat_id: str,                  // Chat identifier (see Supported Chat ID Formats above)
  message_ids: number[]          // Array of message IDs to retrieve
)
```

**Examples:**
```json
// Read multiple messages from Saved Messages
{"tool": "read_messages", "params": {
  "chat_id": "me",
  "message_ids": [680204, 680205, 680206]
}}

// Read from a channel
{"tool": "read_messages", "params": {
  "chat_id": "-1001234567890",
  "message_ids": [123, 124, 125]
}}
```

### 👥 find_chats
**Find users, groups, and channels (uniform entity schema)**

```typescript
find_chats(
  query: str,                  // Search term(s); comma-separated for multi-term
  limit?: number = 20,         // Max results to return
  chat_type?: 'private'|'group'|'channel', // Optional filter
  public?: boolean             // Optional public filter (true=with username, false=without username). Never applies to private chats.
) -> {
  chats: Chat[],               // Array of chat/user entities
}
```

**Search capabilities:**
- **Saved contacts** - Your Telegram contacts
- **Global users** - Public Telegram users
- **Channels & groups** - Public channels and groups
- **Multi-term** - "term1, term2" runs parallel searches and merges/dedupes

**Query formats:**
- Name: `"John Doe"`
- Username: `"telegram"` (without @)
- Phone: `"+1234567890"`

**Examples:**
```json
// Find by username
{"tool": "find_chats", "params": {"query": "telegram"}}

// Find by name
{"tool": "find_chats", "params": {"query": "John Smith"}}

// Find by phone
{"tool": "find_chats", "params": {"query": "+1234567890"}}

// Find only channels matching a term
{"tool": "find_chats", "params": {"query": "news", "chat_type": "channel"}}

// Find only public chats (with usernames)
{"tool": "find_chats", "params": {"query": "project", "public": true}}

// Find private groups only
{"tool": "find_chats", "params": {"query": "team", "chat_type": "group", "public": false}}
```

### ℹ️ get_chat_info
**Get user/chat profile information (enriched with member/subscriber counts)**

```typescript
get_chat_info(
  chat_id: str                  // User/channel identifier (see Supported Chat ID Formats above)
)
```

**Returns:** Bio, status, online state, profile photos, and more.

Also includes, when applicable:
- `members_count` for groups (regular groups and megagroups)
- `subscribers_count` for channels (broadcast)

Counts are fetched via Telethon full-info requests and reflect current values.

**Examples:**
```json
// Get user details by ID
{"tool": "get_chat_info", "params": {"chat_id": "133526395"}}

// Get details by username
{"tool": "get_chat_info", "params": {"chat_id": "telegram"}}

// Get channel information
{"tool": "get_chat_info", "params": {"chat_id": "-1001234567890"}}
```

### 📱 send_message_to_phone
**Message by phone number (auto-contact management) with optional files**

```typescript
send_message_to_phone(
  phone_number: str,           // Phone with country code (+1234567890)
  message: str,                // Message content (becomes caption when files sent)
  first_name?: str = "Contact", // For new contacts
  last_name?: str = "Name",    // For new contacts
  remove_if_new?: boolean = false, // Remove temp contact after send
  parse_mode?: 'markdown'|'html'|'auto' = 'auto',  // Text formatting (auto-detect by default)
  files?: string | string[]    // File URL(s) or local path(s)
)
```

**Features:**
- Auto-creates contact if phone not in contacts
- Optional contact cleanup after sending
- Full formatting support
- File sending support (URLs or local paths)
- Multiple files sent as album when possible

**Examples:**
```json
// Basic message to new contact
{"tool": "send_message_to_phone", "params": {
  "phone_number": "+1234567890",
  "message": "Hello from AI! 🤖"
}}

// Message with file
{"tool": "send_message_to_phone", "params": {
  "phone_number": "+1234567890",
  "message": "Check this document",
  "files": "https://example.com/document.pdf"
}}

// Message with formatting and cleanup
{"tool": "send_message_to_phone", "params": {
  "phone_number": "+1234567890",
  "message": "*Urgent:* Meeting rescheduled to 4 PM",
  "parse_mode": "markdown",
  "remove_if_new": true
}}
```

### 🔧 invoke_mtproto
**Direct Telegram API access with enhanced features**

```typescript
invoke_mtproto(
  method_full_name: str,       // Full API method name (e.g., "messages.GetHistory")
  params_json: str,           // JSON string of method parameters
  allow_dangerous: bool,      // Allow dangerous methods (default: false)
  resolve: bool              // Automatically resolve entities (default: true)
)
```

**Features:**
- **Method name normalization**: Converts `users.getfulluser` → `users.GetFullUser`
- **Dangerous method protection**: Blocks delete operations by default
- **Entity resolution**: Automatically resolves usernames, chat IDs, etc.
- **Parameter sanitization**: Security validation and cleanup
- **Comprehensive error handling**: Structured error responses

**Use cases:** Advanced operations not covered by standard tools

**Examples:**
```json
// Get your own user information (with entity resolution)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "users.GetFullUser",
  "params_json": "{\"id\": {\"_\": \"inputUserSelf\"}}",
  "resolve": true
}}

// Get account information (safe method)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "account.GetAccountTTL",
  "params_json": "{}"
}}

// Delete messages (requires explicit dangerous flag)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "messages.DeleteMessages",
  "params_json": "{\"id\": [123, 456, 789]}",
  "allow_dangerous": true
}}

// Get nearest data center (method normalization works)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "help.getnearestdc",
  "params_json": "{}"
}}
```

**Dangerous Methods (blocked by default):**
- `account.DeleteAccount`
- `messages.DeleteMessages`
- `messages.DeleteHistory`
- `messages.DeleteUserHistory`
- `messages.DeleteChatUser`
- `channels.DeleteHistory`
- `channels.DeleteMessages`

**Entity Resolution:**
When `resolve=true` (default for both MCP tool and HTTP bridge), these parameters are automatically resolved:
- `peer`, `from_peer`, `to_peer`
- `user`, `user_id`, `channel`, `chat`, `chat_id`
- `users`, `chats`, `peers`

## Error Handling

All tools return structured error responses instead of raising exceptions:

```json
{
  "ok": false,
  "error": "Error description",
  "error_type": "ErrorType",
  "operation": "tool_name"
}
```

Common error types:
- `AuthenticationError`: Invalid or missing Bearer token
- `EntityNotFound`: Chat/user not found
- `InvalidParameter`: Invalid input parameters
- `TelegramError`: Telegram API errors
- `FileError`: File sending/download errors

## Performance Considerations

### Search Limits
- **Default limit**: 50 results to prevent LLM context window overflow
- **Result limiting**: Use `limit` parameter to control the number of results returned
- **Auto-expansion**: Limited to 2 additional batches by default to balance completeness with performance
- **Parallel Execution**: Multi-query searches execute simultaneously for better performance
- **Deduplication**: Results automatically deduplicated to prevent duplicates across queries

### LLM Usage Guidelines
- **Start Small**: Begin searches with limit=10-20 for initial exploration
- **Use Filters**: Apply date ranges and chat type filters before increasing limits
- **Avoid Large Limits**: Never request more than 50 results in a single search
- **Result Strategy**: Use limit parameter to control result set size for optimal performance
- **Contact Searches**: Keep contact search limits at 20 or lower (contact results are typically smaller)
- **Performance Impact**: Large result sets can cause context overflow and incomplete processing
- **Multi-Query Efficiency**: Use comma-separated terms for related searches to get unified results
