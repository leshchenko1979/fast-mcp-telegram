# Tools Reference

## Overview

This MCP server provides comprehensive Telegram integration tools optimized for AI assistants. The design philosophy is to **save context space for LLMs** by keeping tools general-purpose: fewer tools with broader capabilities (e.g. `get_messages` covers 5 modes, `invoke_mtproto` covers raw API access) consume less context than many narrow-purpose tools. We accept more parameters per tool in exchange for fewer tools. Uniform schemas across tools (entity, message, error) enable automatic processing of responses when possible. All tools support consistent error handling and MCP ToolAnnotations for better AI agent decision-making.

**HTTP auth:** On a **multi-user server**, each MCP connection uses one Bearer token and one Telegram account — tool names below apply as documented; no prefix flag. For **one agent with multiple connections** (same server URL, different tokens), set `PREFIX_MCP_TOOLS_WITH_ACCOUNT=true` so `tools/list` returns prefixed names (`alice_send_message`, etc.) and `call_tool` must use the matching prefix. See [Installation — one agent, multiple accounts](Installation.md#multi-account-mcp-tool-prefix).

## Supported Chat ID Formats

All tools that accept a `chat_id` parameter support these formats:
- `'me'` - Saved Messages (your own messages)
- `@username` - Username (without @ symbol)
- `123456789` - Numeric user ID
- `-1001234567890` - Channel ID (always starts with -100)
- `https://t.me/username` — t.me URL (resolves to username; message IDs stripped)
- `https://t.me/c/1234567890` — t.me channel URL (resolves to `-1001234567890`)
- `https://t.me/+invitehash` — t.me invite link (passed through to Telethon)
- `tg://resolve?domain=username` — tg:// scheme URL (resolves to username)
- `tg://user?id=123456` — tg:// user URL (resolves to numeric ID)
- `tg://join?invite=invitehash` — tg:// join URL (converted to t.me invite link)
- `tg://openmessage?user_id=123456` — tg:// open message URL (resolves to numeric ID)
- `tg://privatepost?channel=123456` — tg:// private post URL (resolves to `-100123456`)

## 1. Discovery

### find_chats
**Find users, groups, and channels (uniform entity schema)**

```typescript
find_chats(
  query?: str,                  // Search term(s); required for global search (comma-separated for multi-term)
  limit?: number = 20,         // Max results to return
  chat_type?: string, // Optional filter ('private','group','channel','bot', comma-separated for multiple)
  folder?: string,             // Telegram folder name (case-insensitive exact match). In UI: "folder". Internally: "dialog filter". See Filters-vs-Folders.md.
  public?: boolean,            // Optional public filter (true=with username, false=without username). Never applies to private chats.
  min_date?: string,           // ISO last-activity window. include_peers: from GetPeerDialogs top message; flag folder: from dialog list date, or 1-message fallback when that date is missing. Early folder skips (flag path) can omit edge cases if `dialog.date` lags true activity.
  max_date?: string            // ISO last-activity upper bound; same sources as min_date.
) -> {
  chats: Chat[],               // Array of chat/user entities
  note?: string,               // Optional: only when chats is empty (see Empty search results)
}
```

**Three search modes:**

1. **GLOBAL SEARCH** (query provided, no folder or date params) — searches all of Telegram by name/username/phone. Can find any user/group/channel.

2. **FOLDER SEARCH** (folder used) — searches chats matching the Telegram folder (internally called a "dialog filter"). Folders with explicit peers use `GetPeerDialogsRequest`; flag-based folders iterate dialogs. Returns chats matching folder definition.

3. **DIALOG SEARCH** (min_date/max_date used, no folder) — searches your sidebar/dialog list only. Returns chats matching query AND active within the date range. Each result includes `last_activity_date`.

**Search capabilities:**
- **Saved contacts** - Your Telegram contacts
- **Global users** - Public Telegram users
- **Channels & groups** - Public channels and groups
- **Multi-term** - "term1, term2" runs parallel searches and merges/dedupes
- **Folder** - Filter by Telegram folder name (see Filters-vs-Folders.md)

**Query formats:**
- Name: `"John Doe"`
- Username: `"telegram"` (without @)
- Phone: `"+1234567890"`

**Folder:** Telegram folder name as string. Case-insensitive exact match after normalization (trim whitespace, collapse internal spaces, lowercase). Example: `"Без каналов"`, `"Work"`.

**Examples:**
```json
// Find by username (global search)
{"tool": "find_chats", "params": {"query": "telegram"}}

// Find by name
{"tool": "find_chats", "params": {"query": "John Smith"}}

// Find by phone
{"tool": "find_chats", "params": {"query": "+1234567890"}}

// Find only channels matching a term
{"tool": "find_chats", "params": {"query": "news", "chat_type": "channel"}}

// Find channels and groups
{"tool": "find_chats", "params": {"query": "news", "chat_type": "channel,group"}}

// Find only public chats (with usernames)
{"tool": "find_chats", "params": {"query": "project", "public": true}}

// Find private groups only
{"tool": "find_chats", "params": {"query": "team", "chat_type": "group", "public": false}}

// Find chats by folder name (Telegram UI calls these "folders", internally they are "dialog filters")
{"tool": "find_chats", "params": {"query": "work", "folder": "Work"}}

// Find bots
{"tool": "find_chats", "params": {"query": "assistant", "chat_type": "bot"}}

// Dialog search: your chats active since 2026-01-01
{"tool": "find_chats", "params": {"min_date": "2026-01-01"}}

// Dialog search: your chats active in date range
{"tool": "find_chats", "params": {"min_date": "2026-01-01", "max_date": "2026-06-30"}}

// Folder search: chats in "Work" folder
{"tool": "find_chats", "params": {"query": "project", "folder": "Work"}}

// Folder search: with date filter (flag-based folder; include_peers folders also respect min/max via GetPeerDialogs)
{"tool": "find_chats", "params": {"min_date": "2026-04-01", "folder": "Без каналов"}}
```

### get_chat_info
**Get user/chat profile information (enriched with member/subscriber counts)**

```typescript
get_chat_info(
  chat_id: str,                 // User/channel identifier (see Supported Chat ID Formats above)
  topics_limit?: number = 20   // Max number of forum topics to return (1–100, forum chats only)
  common_chats_limit?: number = 10  // Max common groups to list for user targets (1–100)
)
```

**Returns:** Bio, status, online state, profile photos, and more.

Also includes, when applicable:
- `members_count` for groups (regular groups and megagroups)
- `subscribers_count` for channels (broadcast)
- `is_forum: true` for forum-enabled supergroups
- `topics`: list of `{"topic_id": number, "title": string}` entries (forum chats only)
- `topics_has_more: true` when there are more topics than `topics_limit`
- `common_chats`: list of compact chat dicts (same shape as `find_chats` entries) shared between the current account and a user target
- `common_chats_has_more: true` when there are more common groups than `common_chats_limit`

Counts are fetched via Telethon full-info requests and reflect current values.

> **Large 64-bit ids are strings where precision would otherwise be lost.** To
> survive double-based JSON consumers (browsers, JS, Claude Web), where any integer
> above 2⁵³ loses its low digits (e.g. a custom-emoji `document_id`
> `5366182128746793135` would be read back as `5366182128746793000`), two id surfaces
> are serialized as JSON **strings**: `access_hash` in entity objects (it always
> exceeds 2⁵³ and must round-trip verbatim to rebuild `InputPeer`), and any
> out-of-range integer in `invoke_mtproto` results (including `document_id`) — small
> values like offsets, flags and lengths stay numeric. All other id fields (`id`,
> `message_id`, `reply_to_msg_id`, `topic_id`) remain numbers. ids are accepted as
> either strings or numbers on input.

**Examples:**
```json
// Get user details by ID
{"tool": "get_chat_info", "params": {"chat_id": "133526395"}}

// Get details by username
{"tool": "get_chat_info", "params": {"chat_id": "telegram"}}

// Get forum topics (returns up to 20 by default)
{"tool": "get_chat_info", "params": {"chat_id": "-1001234567890"}}

// Get more forum topics
{"tool": "get_chat_info", "params": {"chat_id": "-1001234567890", "topics_limit": 50}}

// Get common groups for a user target (returns up to 10 by default)
{"tool": "get_chat_info", "params": {"chat_id": "133526395"}}

// Get more common groups
{"tool": "get_chat_info", "params": {"chat_id": "133526395", "common_chats_limit": 50}}
```

### search_messages_globally
**Search messages across all Telegram chats**

```typescript
search_messages_globally(
  query: str,                    // Search terms (comma-separated, required)
  limit?: number = 50,          // Max results
  chat_type?: string, // Filter by chat type ('private','group','channel', comma-separated for multiple)
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

// Search in multiple chat types
{"tool": "search_messages_globally", "params": {
  "query": "urgent",
  "chat_type": "private,group"
}}
```

## 2. Read

### get_messages
**Unified message retrieval - search, browse, read by IDs, or get replies**

```typescript
get_messages(
  chat_id: str,                  // Target chat ID (required)
  query?: str,                   // Search terms (optional)
  message_ids?: number[],        // Specific message IDs to retrieve
  reply_to_id?: number,          // Thread anchor: post id, forum topic_id, or message id
  thread_scope?: "auto" | "full" | "direct" = "auto",  // Only with reply_to_id
  limit?: number = 50,           // Max results
  min_date?: string,             // ISO date filter (search, browse, and reply/forum-topic modes)
  max_date?: string,             // ISO date filter (search, browse, and reply/forum-topic modes)
  from_user?: string,            // Sender filter — @username, phone, user id (not display-name search; per-chat only)
  context?: number = 0,          // Neighbor messages per side (1–10); 0=disabled. Requires chat_id.
  include_replies?: boolean = false,  // Fetch up to 5 direct replies per result (opt-in)
  auto_expand_batches?: number = 2,  // Extra batches for filtered searches
  include_total_count?: boolean = false  // Include total count (chat search only)
)
```

**5 Modes (parameter combinations):**
1. **Search in chat**: `chat_id` + `query` - Search messages in a specific chat
2. **Browse chat**: `chat_id` only - Get latest messages
3. **Read by IDs**: `chat_id` + `message_ids` - Get specific messages *(date filters not supported)*
4. **Get replies**: `chat_id` + `reply_to_id` - Get replies to a message *(date filters not supported)*
5. **Search replies**: `chat_id` + `reply_to_id` + `query` - Search within replies

**`thread_scope` (with `reply_to_id` only):**

| `reply_to_id` points to | `auto` | `full` | `direct` |
|-------------------------|--------|--------|----------|
| **Forum topic id** (`get_chat_info` `topic_id`) | Whole topic via GetReplies (nested chains) | Same as `auto` | Direct replies to topic root only |
| **Message inside a forum topic** | Direct replies to that message | Nested replies in the **branch** under that message (BFS on search window) | Same as `auto` for in-topic |
| **Channel post** (with discussion) | Full comment thread | Same as `auto` | Direct comments to post only |
| **Supergroup thread** (non-forum) | Direct replies | Full thread via `SearchRequest(top_msg_id)` | Direct replies only |

- **`auto`** (default): Best default for “what replied to this?” — full topic/comment thread when `reply_to_id` is a topic or post id; otherwise direct replies only.
- **`full`**: Use on a **message id** when you need nested replies (e.g. replies-to-replies). For forum in-topic anchors this is **not** the entire topic — use the topic’s `topic_id` as `reply_to_id` for that.
- **`direct`**: Never includes nested replies.

**reply_to_id automatically handles:**
- 📢 **Channel post comments** — discussion group; `auto` loads the full comment thread
- 📋 **Forum topic** — `reply_to_id` = topic id → GetReplies (whole topic)
- 💬 **Forum in-topic message** — `reply_to_id` = message id → search near anchor (`offset_id ≈ anchor + 100`); use `full` for nested branch, topic id for whole topic

**Parameter Conflicts (will error):**
- `thread_scope` of `full` or `direct` without `reply_to_id`
- `message_ids` + `reply_to_id`: Cannot combine
- `message_ids` + `query`: Cannot combine (specific IDs don't need search)

**`message_ids` — missing or deleted IDs:** Each requested id appears in `messages` in request order. Found messages use the normal message shape (without `chat` when `chat_id` is set). Missing or deleted ids return a per-id stub: `{"id": <id>, "chat": {...}, "error": "Message not found or inaccessible"}`. Single-id and multi-id requests use the same envelope: `{"messages": [...], "has_more": false}`. Operational failures (chat not found, bad params) still return top-level `ok: false` errors. Search, browse, and reply/thread modes omit deleted id gaps silently (no stubs).

**`from_user` — not a name search:** Resolves the sender like `chat_id` via `get_entity` (username, phone, numeric id, `me`, t.me URL). Does **not** search contacts or match display names — a bare string such as `Adolfo` may resolve to an unrelated `@username`. Prefer `@username`, phone, or numeric user id.

**Response (unified format for all modes):**
```json
{
  "messages": [...],           // List of message dicts
  "has_more": false,           // Boolean (always false for message_ids mode)
  "note": "No messages found matching query 'launch'",  // Optional: only when messages is empty (see Empty search results)
  "total_count": 123,          // Optional: only if include_total_count=true
  "reply_to_id": 100,          // Optional: only for reply_to_id mode
  "discussion_chat_id": "...", // Optional: only for channel posts with discussion
  "discussion_total_count": 45 // Optional: only for channel posts with discussion
}
```

When `context > 0` or `include_replies=true`, each message gains a `context` envelope:
```json
{
  "id": 500,
  "text": "the matched message",
  "context": {
    "before": [{"id": 498, "date": "...", "text": "...", "sender_id": 42}],
    "after": [{"id": 502, "date": "...", "text": "...", "sender_id": 43}],
    "reply_to": {"id": 400, "date": "...", "text": "...", "sender_id": 44},
    "replies": [{"id": 501, "date": "...", "text": "...", "sender_id": 45}]
  }
}
```

Context messages use a lightweight format (id, date, text, sender_id) to save tokens. `replies` is only populated when `include_replies=true`. `reply_to` is `null` when the message has no reply target. The `context` key is absent entirely when no enrichment is requested.

**Features:**
- **Rich Media Parsing**: Automatically parses Todo lists, polls, photos, documents
- **Voice Transcription**: Automatic for Premium accounts with parallel processing
- **Universal Replies**: Single parameter for post comments, forum topics, and message replies
- **Auto-Detection**: Automatically detects channel posts and uses discussion group
- **Structured Data**: LLM-friendly JSON structures
- **Context Optimization**: When `chat_id` is provided (per-chat modes), the `chat` field is omitted from each message to save context. Global search includes `chat` since messages span different chats.
- **Context Enrichment**: `context` parameter adds surrounding messages (before/after) and reply chains. `include_replies` fetches direct replies. Lightweight format saves tokens. Forum topic-aware.

**💡 Tips:**
- **No query**: Returns latest messages from chat
- **Multi-term**: Use comma-separated words for broader results
- **Partial words**: Use shorter forms (e.g., "proj" finds "project", "projects")
- **reply_to_id**: Channel post id, forum **`topic_id`** from `get_chat_info`, or a **message id** inside a topic
- **Forum in-topic message** (e.g. `https://t.me/telemtrs/12799/13204` → `reply_to_id: 13204`): Replies are found via `messages.search` near the anchor, not from the latest topic messages. For the **whole topic** `12799`, use `reply_to_id: 12799`.
- **`thread_scope=full` on a message id**: Nested replies under that message only (wider id window + BFS). Not the full topic — use the topic id for that.
- **Search stubs**: Bodies may appear in `.message` instead of `.text`; the server reloads full messages when needed.
- **Forum General topic** (`topic_id` 1): Browse with `chat_id` only; do not use `thread_scope=full` with id `1`
- **Supergroup threads**: Use `thread_scope=full` with the thread starter message id

**Examples:**
```json
// 1. Search in chat
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "query": "launch"
}}

// 2. Browse latest messages (no query)
{"tool": "get_messages", "params": {
  "chat_id": "me",
  "limit": 10
}}

// 3. Read specific messages by ID
{"tool": "get_messages", "params": {
  "chat_id": "me",
  "message_ids": [680204, 680205]
}}

// 4. Get channel post comments (auto-detects discussion)
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "reply_to_id": 123
}}

// 5. Get forum topic messages (topic_id from get_chat_info)
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "reply_to_id": 52
}}

// 5b. Replies to a message inside a forum topic (direct)
{"tool": "get_messages", "params": {
  "chat_id": "telemtrs",
  "reply_to_id": 13204,
  "thread_scope": "auto"
}}

// 5c. Same anchor, nested branch (replies to replies)
{"tool": "get_messages", "params": {
  "chat_id": "telemtrs",
  "reply_to_id": 13204,
  "thread_scope": "full"
}}

// 6. Get replies to any message
{"tool": "get_messages", "params": {
  "chat_id": "me",
  "reply_to_id": 100
}}

// 7. Search within replies
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "reply_to_id": 123,
  "query": "bug"
}}

// Multi-term search
{"tool": "get_messages", "params": {
  "chat_id": "telegram",
  "query": "update, news"
}}

// 8. Search with context (3 messages before/after each result)
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "query": "deadline",
  "context": 3,
  "limit": 10
}}

// 9. Search with context + reply threads
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "query": "announcement",
  "context": 2,
  "include_replies": true,
  "limit": 10
}}

// 10. Reply threads only (no neighbor context)
{"tool": "get_messages", "params": {
  "chat_id": "-1001234567890",
  "query": "question",
  "include_replies": true,
  "limit": 5
}}
```

## 3. Write

### send_message
**Send new messages with formatting and optional files**

```typescript
send_message(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  message: str,                  // Message content (becomes caption when files sent)
  reply_to_id?: number,          // Reply target (message ID, forum topic root, or channel post for comments)
  parse_mode?: 'markdown'|'html'|'auto'|'rich' = 'auto', // Classic entities, or 'rich' for Rich Message document
  files?: string[]               // File paths, URLs, or data: URIs (base64). Use a one-element array for a single file. Incompatible with parse_mode='rich'
)
```

**parse_mode:**
- `markdown` / `html` / `auto` — classic flat text + entities (`auto` detects tags vs markdown patterns).
- `rich` — Telegram **Rich Message** (`InputRichMessage*`). Dialect is auto-detected: known HTML tags **outside** code fences/backticks → rich HTML; otherwise rich markdown (including plain text and docs that only mention tags inside code). Cannot be combined with `files`.
- Success for rich sends includes `rich: true` and `rich_format: "markdown"|"html"`, with `text` flattened from PageBlocks (same family as `get_messages`).

**reply_to_id automatically handles:**
- 📢 **Channel post comments** - Detects discussion group and posts comment there
- 📋 **Forum topic messages** - Posts into forum topic
- 💬 **Message replies** - Replies to any message

**File Sending:**
- `files`: Array of one or more files (paths, URLs, or data: URIs); for a single attachment use a one-element array
- **data: URIs**: Inline base64-encoded files, work in all transport modes. Format: `data:<mime>;base64,<data>`. Add `;filename=name.ext` to preserve original filename. MIME type auto-detected, images sent as photos, non-images as documents.
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
  "files": ["https://example.com/document.pdf"]
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
  "files": ["/path/to/report.pdf"]
}}

// Send inline data: URI with filename (all transport modes)
{"tool": "send_message", "params": {
  "chat_id": "@username",
  "message": "Report",
  "files": ["data:application/pdf;filename=report.pdf;base64,Khs="]
}}

// Reply with formatting
{"tool": "send_message", "params": {
  "chat_id": "@username",
  "message": "*Important:* Meeting at 3 PM",
  "parse_mode": "markdown",
  "reply_to_id": 67890
}}

// Rich Message document (headings, lists)
{"tool": "send_message", "params": {
  "chat_id": "me",
  "message": "## Status\n\n- item a\n- item b",
  "parse_mode": "rich"
}}

// Post into a forum topic (use topic_id from get_chat_info topics list as reply_to_id)
{"tool": "send_message", "params": {
  "chat_id": "-1001234567890",
  "message": "Hello forum thread!",
  "reply_to_id": 52
}}

// Post comment on channel post (auto-detects discussion group)
{"tool": "send_message", "params": {
  "chat_id": "-1001234567890",
  "message": "Great post!",
  "reply_to_id": 42
}}
```

### edit_message
**Edit existing messages with formatting**

```typescript
edit_message(
  chat_id: str,                  // Target chat ID (see Supported Chat ID Formats above)
  message_id: number,            // Message ID to edit (required)
  message: str,                  // New message content
  parse_mode?: 'markdown'|'html'|'auto'|'rich' = 'auto' // Classic entities, or 'rich' for Rich Message
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

// Edit to Rich Message
{"tool": "edit_message", "params": {
  "chat_id": "me",
  "message_id": 67890,
  "message": "## Updated\n\n- done",
  "parse_mode": "rich"
}}
```

### send_message_to_phone
**Message by phone number (auto-contact management) with optional files**

```typescript
send_message_to_phone(
  phone_number: str,           // Phone with country code (+1234567890)
  message: str,                // Message content (becomes caption when files sent)
  first_name?: str = "Contact", // For new contacts
  last_name?: str = "Name",    // For new contacts
  remove_if_new?: boolean = false, // Remove temp contact after send
  parse_mode?: 'markdown'|'html'|'auto'|'rich' = 'auto',  // Classic or 'rich' (no files with rich)
  files?: string | string[]    // File URL(s), data: URI(s), or local path(s)
)
```

**Features:**
- Auto-creates contact if phone not in contacts
- Optional contact cleanup after sending
- Full formatting support
- File sending support (URLs, data: URIs, or local paths)
- data: URIs work in all modes; local paths in stdio only
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

## 4. Advanced

### invoke_mtproto
**Direct Telegram API access with automatic TL object construction**

```typescript
invoke_mtproto(
  method_full_name: str,       // Full API method name (e.g., "messages.GetHistory")
  params_json: str,           // JSON string of method parameters (supports automatic TL object construction)
  allow_dangerous: bool,      // Allow dangerous methods (default: false)
  resolve: bool              // Automatically resolve entities (default: true)
)
```

**Features:**
- **Method name normalization**: Converts `users.getfulluser` → `users.GetFullUser`
- **Automatic TL object construction**: Builds complex Telegram objects from JSON dictionaries
- **Case-insensitive type lookup**: `inputmediatodo` → `InputMediaTodo` automatically
- **Recursive object construction**: Handles deeply nested structures automatically
- **Dangerous method protection**: Blocks delete operations by default
- **Entity resolution**: Automatically resolves usernames, chat IDs, etc.
- **Parameter sanitization**: Security validation and cleanup
- **Comprehensive error handling**: Structured error responses with machine-readable `error_code` for Telegram RPC errors (e.g., `USER_ALREADY_PARTICIPANT`, `INVITE_HASH_EXPIRED`)

**Parameter notes:**
- `hash` parameter accepts both **string** (e.g., invite hash for `messages.ImportChatInvite`) and **integer** (for state/difference methods like `messages.GetState`)
- **A bare message id needs a chat binding.** Some requests declare no peer field at all — `messages.GetMessages` takes only `id` — so Telegram resolves a bare id against whatever dialog the account can see, and a read can return an unrelated chat's message. Such a request is **refused** with an error naming the scoped alternatives. Use `channels.GetMessages` (`channel` + `id`) or `messages.GetHistory` (`peer`), both of which carry the binding in the request itself. Passing a plain integer is the same hazard as passing `{"_": "inputMessageID", "id": N}` and is refused the same way.

**Forum topic scoping (reading one topic):**
`messages.GetHistory` **cannot address a forum topic**. Its parameters are `peer, offset_id, offset_date, add_offset, limit, max_id, min_id, hash` — no `thread_id`, no `top_msg_id`. This is structural in the TL schema, not a limitation of this tool: across the whole API layer **zero** requests carry `thread_id`, and `GetHistory` is not among the dozen that carry `top_msg_id`. There is also no `channels.GetHistory` to route to, so no fix to `GetHistory` is possible.

Use `messages.Search` with `top_msg_id` instead — this is the route the server honours, and it is what the high-level tools already use internally:

```json
// Read one forum topic (top_msg_id = the topic's root message id)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "messages.Search",
  "params_json": "{\"peer\": -1001234567890, \"q\": \"\", \"filter\": {\"_\": \"InputMessagesFilterEmpty\"}, \"top_msg_id\": 42487, \"limit\": 50}"
}}
```

`messages.Search` declares many parameters, but only `peer`, `q`, `filter` and `top_msg_id` need spelling out: the remaining ones (`min_date`, `max_date`, `offset_id`, `add_offset`, `max_id`, `min_id`, `hash`) are integers that `invoke_mtproto` fills with `0` automatically. `peer` wants the raw `-100…` id — a dict peer raises `Cannot cast dict to any kind of Peer` before resolution runs.

The high-level `get_messages` tool exposes the same capability more directly: pass `reply_to_id` set to the topic's root message id.

**Use cases:** Advanced operations with complex parameters, raw Telegram API access, joining groups via invite links

**Automatic TL Object Construction:**
`invoke_mtproto` automatically constructs complex Telegram TL objects from JSON dictionaries. Simply use the `"_"` key to specify the object type:

```json
// Create a todo list (automatic object construction)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "messages.sendMedia",
  "params_json": {
    "peer": "me",
    "media": {
      "_": "InputMediaTodo",
      "todo": {
        "_": "TodoList",
        "title": {
          "_": "TextWithEntities",
          "text": "My Todo List",
          "entities": []
        },
        "list": [
          {
            "_": "TodoItem",
            "id": 1,
            "title": {
              "_": "TextWithEntities",
              "text": "Complete project documentation",
              "entities": []
            }
          },
          {
            "_": "TodoItem",
            "id": 2,
            "title": {
              "_": "TextWithEntities",
              "text": "Review code changes",
              "entities": []
            }
          }
        ],
        "others_can_append": true,
        "others_can_complete": false
      }
    },
    "message": "Check out my new todo list!",
    "random_id": 1234567890123456789
  }
}}

// Case-insensitive type names work too!
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "messages.sendMessage",
  "params_json": {
    "peer": "me",
    "message": "Hello!",
    "entities": [
      {
        "_": "messageentitybold",  // lowercase works!
        "offset": 0,
        "length": 5
      }
    ]
  }
}}
```

**Supported Features:**
- **Automatic Construction**: Objects with `"_"` key are automatically built
- **Case-Insensitive**: `inputmediatodo`, `INPUTMEDIATODO`, `inputMediaTodo` all work
- **Nested Objects**: Handles deeply nested structures recursively
- **List Processing**: Arrays of objects are processed automatically
- **Parameter Matching**: Uses constructor signatures to match JSON keys

**Common TL Object Types:**
- `InputMediaTodo` - Todo lists
- `InputMediaPoll` - Polls and quizzes
- `InputMediaPhoto` - Photo uploads
- `InputMediaDocument` - File uploads
- `TextWithEntities` - Rich text formatting
- `MessageEntityBold/Italic/Url/etc.` - Text formatting entities

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

**Examples:**
```json
// Get your own user information
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "users.GetFullUser",
  "params_json": "{\"id\": {\"_\": \"inputUserSelf\"}}"
}}

// Get account information (safe method)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "account.GetAccountTTL",
  "params_json": "{}"
}}

// Delete messages (requires explicit dangerous flag).
// Note the channel: messages.DeleteMessages takes a bare id with no peer field,
// so it is refused. channels.DeleteMessages carries the binding in the request.
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "channels.DeleteMessages",
  "params_json": "{\"channel\": -1001234567890, \"id\": [123, 456, 789]}",
  "allow_dangerous": true
}}

// Get nearest data center (method normalization works)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "help.getnearestdc",
  "params_json": "{}"
}}

// Join a group via invite link - hash must be string (from t.me/+... link)
{"tool": "invoke_mtproto", "params": {
  "method_full_name": "messages.ImportChatInvite",
  "params_json": "{\"hash\": \"ABC123xyz\"}"
}}
```

## Appendix

### Empty search results

When a search or discovery query runs successfully but matches nothing, tools return a **success response with an empty collection**, not `ok: false`. Real failures (auth, network, invalid parameters) still use the error format below.

| Tool | Empty success shape | `note` field |
| --- | --- | --- |
| `get_messages` (search/browse) | `{"messages": [], "has_more": false}` | Optional string explaining why (query, date range, filters) |
| `get_messages` (replies) | `{"messages": [], "has_more": false, "reply_to_id": N}` | Optional string (e.g. no replies for that message) |
| `find_chats` | `{"chats": []}` | Optional string (query/date context) |
| `search_contacts` | `[]` | No `note` — raw list return |

The optional **`note`** key is a human-readable diagnostic in `structured_content`. Check `messages` / `chats` length first; read `note` when you need to distinguish "nothing matched" from a silent empty browse. **`note` is absent on non-empty responses.**

Parameter validation errors (e.g. empty query with no `chat_id` on `get_messages`) remain errors, not empty collections. See [ADR 0012](adr/0012-empty-result-consistency.md).

### Error Handling

This MCP server implements comprehensive error handling with clear, actionable error messages. Do not treat `ok: false` as "zero results" — use empty collections and optional `note` instead (see above).

**Session Authentication Errors:**
When a Telegram session is not authorized (e.g., session file missing or expired), tools return:
```json
{
  "ok": false,
  "error": "Session not authorized. Please authenticate your Telegram session first.",
  "action": "authenticate_session",
  "operation": "tool_name"
}
```

**Telegram Transport Errors:**
When the session file has credentials but Telegram cannot be reached (network, firewall, or **MTPROTO_PROXY** misconfigured or down), tools return a **TelegramTransportError**-derived message and `action: "retry"`:
```json
{
  "ok": false,
  "error": "Cannot reach Telegram; check network connectivity and MTProto proxy if MTPROTO_PROXY is set.",
  "action": "retry",
  "operation": "tool_name"
}
```
The exact `error` text may include RPC class names or proxy diagnostics from the server.

**Common Error Types:**
- **Authentication Issues**: Clear guidance to authenticate sessions (`authenticate_session`)
- **Transport / proxy**: Retry after fixing network or `MTPROTO_PROXY` (`retry`)
- **Network/Connection Problems**: Other connectivity patterns may still map to generic connection messages
- **Database Errors**: Retry guidance for temporary server issues
- **Invalid Chat IDs**: Clear validation messages for incorrect identifiers

**Error Response Format:**
All error responses follow this consistent structure:
```json
{
  "ok": false,
  "error": "Human-readable error message",
  "operation": "tool_name",
  "error_code": "USER_ALREADY_PARTICIPANT",  // optional: Telegram RPC code (invoke_mtproto)
  "action": "suggested_action",  // optional: what to do next
  "exception": {                 // optional: technical details
    "type": "ExceptionType",
    "message": "Technical details"
  }
}
```

**Common Error Types (tool-level):**
- `AuthenticationError`: Invalid or missing Bearer token
- `EntityNotFound`: Chat/user not found
- `InvalidParameter`: Invalid input parameters
- `TelegramError`: Telegram API errors
- `FileError`: File sending/download errors

### ToolAnnotations for AI Guidance

All tools include MCP ToolAnnotations to help AI agents make informed decisions:

- **`openWorldHint=True`**: All tools interact with external Telegram APIs
- **`readOnlyHint=True`**: Applied to search and informational tools (safe to retry)
- **`destructiveHint=True`**: Applied to messaging and state-changing tools (use cautiously)
- **`idempotentHint=True`**: Applied to safely repeatable operations (can retry safely)

### AI-Optimized Parameter Constraints

This MCP server uses `Literal` parameter types to guide AI model choices and ensure valid inputs:

- **`parse_mode`**: Constrained to `"markdown"`, `"html"`, `"auto"`, or `"rich"` (default: `"auto"`). `"rich"` sends/edits a Rich Message document (not classic entities).
- **`chat_type`**: Limited to `"private"`, `"group"`, `"channel"`, or `"bot"` for search filters (bots return `type: "bot"` instead of `type: "private"`)
- **Enhanced Validation**: FastMCP automatically validates these constraints
- **Better AI Guidance**: AI models see only valid options, reducing errors

### Uniform Entity Schema

All tools return chat/user objects in the same schema via `build_entity_dict`:

```json
{
  "id": 133526395,
  "title": "John Doe",           // falls back to full name or @username
  "type": "private",            // one of: private | group | channel | bot
  "username": "johndoe",        // if available
  "first_name": "John",         // users
  "last_name": "Doe",           // users
  "members_count": 1234,          // groups (when available)
  "subscribers_count": 56789,     // channels (when available)
  "is_forum": true               // present and true for forum-enabled supergroups only
}
```

`find_chats` returns a list of these entities. Message search results include a `chat` field in the same format, except when `chat_id` is explicitly provided (per-chat modes) — then `chat` is omitted to save context.

### Uniform Message Schema

Read/search tools use `build_message_result`. Send/edit/phone success payloads use `build_send_edit_result` (fields `message_id`, `status`, etc.) but share the same text/`rich` conventions for Rich Messages.

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
  "text": "Hello world!",          // Message content (text/caption; rich messages use flattened PageBlock text)
  "rich": true,                    // Optional. True when content came from Telegram RichMessage (Bot API 10.1+)
  "link": "https://t.me/johndoe/12345",  // Direct Telegram link (when available)
  "sender": {                     // Sender entity (same uniform schema, optional)
    "id": 133526395,
    "title": "John Doe",
    "type": "private",
    "username": "johndoe"
  },
  "reply_to_msg_id": 12344,       // ID of message being replied to (optional)
  "topic_id": 52,                 // Forum topic ID (forum chats only)
  "media": {                      // Media attachment info (optional, lightweight)
    "type": "voice",              // Media type (voice, photo, video, etc.)
    "mime_type": "image/jpeg",    // File MIME type
    "filename": "photo.jpg",      // Original filename (if available)
    "approx_size_bytes": 2048576, // Approximate file size
    "duration_seconds": 45,       // Duration for audio/video (optional)
    "attachment_download_url": "https://your-mcp-host.example/v1/attachments/<uuid>/<filename>"  // HTTP mode + real DOMAIN only; see README — secret URL, no Authorization on GET
  },
  "transcription": "Hello, this is a voice message transcription...",  // Voice transcription (Premium accounts only)
  "forwarded_from": {             // Forwarded message info (optional)
    "id": 999999999,
    "title": "Original Channel",
    "type": "channel",
    "username": "original_channel"
  },
  "reply_markup": {               // Interactive elements (optional)
    "type": "inline",             // "keyboard", "inline", "force_reply", "hide"
    "rows": [                     // Button rows (for keyboard/inline types)
      [
        {
          "text": "Click me!",    // Button text
          "type": "url",          // Button type: "url", "callback_data", etc.
          "url": "https://example.com"  // Button data (varies by type)
        }
      ]
    ]
  }
}
```

**Message Content Priority:**
1. When `rich_message` is present and flattening yields text, that flattened string is used (with `rich: true`).
2. `text` - Primary plain message content
3. `message` - Alternative text field
4. `caption` - Media caption (if no text)

**Rich messages (Bot API 10.1+ / MTProto `Message.rich_message`):**
- Send/edit/phone with `parse_mode="rich"` create or update Rich Messages (see Write tools above).
- Rich-only posts often have an empty plain `message` field; content lives in a `PageBlock` tree.
- The server flattens blocks to markdown-ish `text` and sets `rich: true` on read and on send/edit success.
- Send/edit success also includes `rich_format: "markdown"|"html"` indicating which InputRichMessage dialect was used.
- Embedded photos/videos/audio referenced from blocks appear in `attachments` (tree order, deduplicated by media id).
- `media` duplicates the first `attachments` entry for backward compatibility.
- Rich attachment tickets use `rich_kind` + `rich_media_id` (Telegram object id, not array index).

**Media Attachments:**
- Lightweight metadata only (not actual files)
- Includes MIME type, filename, approximate size, and media type
- Voice messages include duration and automatic transcription (Premium accounts)
- Covers: photos, documents, videos, audio, voice messages, polls, todo lists, etc.
- **`attachment_download_url`** (optional): When the server runs **HTTP transport** and **`DOMAIN`** is a real public host (not a placeholder), photos, documents, voice messages, and round videos may include this URL. The URL format is `/v1/attachments/<uuid>/<filename>` — photos get a synthetic `photo_<msg_id>.jpg`. **`GET` does not require a Bearer token**; anyone with the URL can download until the ticket expires (`ATTACHMENT_TICKET_TTL_SECONDS`). Treat links as confidential. Tickets are stored in memory (single-process; restart invalidates them).

**Voice Message Transcription:**
- Automatic transcription for Premium Telegram accounts
- Parallel processing of multiple voice messages
- Polling for completion (up to 30 seconds)
- Graceful cancellation if Premium requirement fails
- Added to `transcription` field in message results

**Forwarded Messages:**
- `forwarded_from` contains original sender info
- Uses same entity schema as chat/sender fields

**Reply Markup:**
- `reply_markup` contains interactive keyboard and inline button elements
- Automatically extracted from messages with keyboard markup
- Includes button text, types (URL, callback, etc.), and associated data
- Supports all Telegram markup types: keyboards, inline buttons, force reply, hide keyboard

### Performance Considerations

**Search Limits:**
- **Default limit**: 50 results to prevent LLM context window overflow
- **Result limiting**: Use `limit` parameter to control the number of results returned
- **Auto-expansion**: Limited to 2 additional batches by default to balance completeness with performance
- **Parallel Execution**: Multi-query searches execute simultaneously for better performance
- **Deduplication**: Results automatically deduplicated to prevent duplicates across queries

**LLM Usage Guidelines:**
- **Start Small**: Begin searches with limit=10-20 for initial exploration
- **Use Filters**: Apply date ranges and chat type filters before increasing limits
- **Avoid Large Limits**: Never request more than 50 results in a single search
- **Result Strategy**: Use limit parameter to control result set size for optimal performance
- **Contact Searches**: Keep contact search limits at 20 or lower (contact results are typically smaller)
- **Performance Impact**: Large result sets can cause context overflow and incomplete processing
- **Multi-Query Efficiency**: Use comma-separated terms for related searches to get unified results