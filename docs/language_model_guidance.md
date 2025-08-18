# Language Model Guidance for Telegram MCP Server

## Overview
This document provides comprehensive guidance for language models on how to correctly use the Telegram MCP server tools, with special focus on avoiding the common search interpretation mistake.

## The Core Problem
**Language models often incorrectly use contact names as search queries in global search**, which leads to:
- Finding the contact name mentioned in other chats instead of targeting the specific contact
- Irrelevant search results
- Missed target conversations
- Inefficient search operations

## Correct Usage Patterns

### 1. Contact-Specific Searches
**When user asks**: "Find messages from John about the project"

**❌ WRONG Approach**:
```python
search_messages(query="John", chat_id=None)  # This searches for "John" in all chats
```

**✅ CORRECT Approach**:
```python
# Step 1: Find John's chat ID using Telegram's native search
contacts = search_contacts(query="John")
john_chat_id = contacts[0]['chat_id']

# Step 2: Search in John's chat for project-related messages
search_messages(chat_id=john_chat_id, query="project")
```

### 2. Content-Specific Searches
**When user asks**: "Find all messages about project X"

**✅ CORRECT Approach**:
```python
search_messages(query="project X", chat_id=None)  # Global search for content
```

### 3. Hybrid Searches
**When user asks**: "Find messages about the meeting from Alice"

**✅ CORRECT Approach**:
```python
# Step 1: Find Alice's chat ID using Telegram's native search
contacts = search_contacts(query="Alice")
alice_chat_id = contacts[0]['chat_id']

# Step 2: Search in Alice's chat for meeting-related messages
search_messages(chat_id=alice_chat_id, query="meeting")
```

## Tool Usage Workflows

### Workflow 1: Contact-Specific Search
```
User Request → Find Contact → Get Chat ID → Search in Chat
```

**Example**:
1. User: "Show me messages from Sarah"
2. `search_contacts(query="Sarah")`
3. Extract chat_id from result
4. `search_messages(chat_id=sarah_chat_id, query="")`

### Workflow 2: Content Search
```
User Request → Global Search for Content
```

**Example**:
1. User: "Find all messages about deadlines"
2. `search_messages(query="deadlines", chat_id=None)`

### Workflow 3: Contact + Content Search
```
User Request → Find Contact → Get Chat ID → Search in Chat for Content
```

**Example**:
1. User: "Find messages from Mike about the budget"
2. `search_contacts(query="Mike")`
3. Extract chat_id from result
4. `search_messages(chat_id=mike_chat_id, query="budget")`

### Workflow 4: Read message(s) by ID
```
User Request → Provide chat and message IDs → Read directly
```

**Example**:
```python
# Read a single message by link components
read_messages(chat_id="@flipping_invest", message_ids=[993])

# Read several messages in a private or public chat
read_messages(chat_id="-1001234567890", message_ids=[101, 205, 309])
```

## Common Scenarios and Solutions

### Scenario 1: "Find messages from [Contact Name]"
**Solution**: Use `search_contacts()` + `search_messages()` with chat_id
```python
# Find the contact using Telegram's native search
contacts = search_contacts(query="[Contact Name]")
if contacts:
    chat_id = contacts[0]['chat_id']
    # Get all messages from this contact
    search_messages(chat_id=chat_id, query="")
```

### Scenario 2: "Find messages about [Topic]"
**Solution**: Use global search
```python
search_messages(query="[Topic]", chat_id=None)
```

### Scenario 3: "Find messages from [Contact] about [Topic]"
**Solution**: Use `search_contacts()` + `search_messages()` with both chat_id and query
```python
# Find the contact using Telegram's native search
contacts = search_contacts(query="[Contact]")
if contacts:
    chat_id = contacts[0]['chat_id']
    # Search for topic in this contact's chat
    search_messages(chat_id=chat_id, query="[Topic]")
```

## Error Prevention Checklist

### Before Using search_messages(), Ask:
1. **Is the user asking about a specific contact?**
   - If YES: Use `search_contacts()` first, then use chat_id
   - If NO: Use global search

2. **Is the user asking about specific content?**
   - If YES: Use query parameter
   - If NO: Use empty query with chat_id

3. **Am I using a contact name as a search query?**
   - If YES: STOP! Use `search_contacts()` instead
   - If NO: Proceed with search

### Common Mistakes to Avoid:
- ❌ `search_messages(query="John", chat_id=None)` - Don't search for contact names globally
- ❌ Using contact names as search terms without finding their chat_id first
- ❌ Mixing global search with contact-specific intent
- ❌ Using old `find_contact()` instead of new `search_contacts()`
- ❌ Trying to use `search_messages` to fetch exact IDs — use `read_messages` instead

## Best Practices

### 1. Always Resolve Contacts First
When a user mentions a contact name, always use `search_contacts()` to get the chat_id before searching.

### 2. Use Clear Intent
- **Contact intent**: Use chat_id parameter
- **Content intent**: Use query parameter
- **Both**: Use both parameters

### 3. Handle Multiple Matches
When `search_contacts()` returns multiple results:
```python
contacts = search_contacts(query="John")
if len(contacts) > 1:
    # Ask user to clarify or use the first match
    # You can also refine the search query for more precise matching
```

### 4. Provide Context
When returning results, always include context about which chat the messages came from.

## Tool Reference

### search_contacts(query, limit=20)
- **Purpose**: Resolve contact names to chat IDs using Telegram's native search
- **Use when**: User mentions a contact name, username, or phone number
- **Returns**: List of matching contacts with chat_ids, usernames, and phone numbers

### search_messages(query, chat_id=None, ...)
- **Purpose**: Search for messages
- **Use chat_id**: For contact-specific searches
- **Use query**: For content-specific searches
- **Use both**: For contact + content searches

### read_messages(chat_id, message_ids)
- **Purpose**: Read specific messages by their IDs in a given chat
- **Use when**: You know exact message IDs (e.g., from a link like `https://t.me/<username>/<id>`) or need precise retrieval



## Testing Your Understanding

**Test Case 1**: User asks "Find messages from Alex"
- ✅ Correct: `search_contacts("Alex")` → `search_messages(chat_id=alex_chat_id, query="")`
- ❌ Wrong: `search_messages(query="Alex", chat_id=None)`

**Test Case 2**: User asks "Find all messages about meetings"
- ✅ Correct: `search_messages(query="meetings", chat_id=None)`
- ❌ Wrong: `search_contacts("meetings")` → `search_messages(chat_id=meetings_chat_id, query="")`

**Test Case 3**: User asks "Find messages from Bob about the deadline"
- ✅ Correct: `search_contacts("Bob")` → `search_messages(chat_id=bob_chat_id, query="deadline")`
- ❌ Wrong: `search_messages(query="Bob deadline", chat_id=None)`

Remember: **Contact names go in `search_contacts()`, content goes in `search_messages(query=)`; exact message IDs go in `read_messages()`.**
