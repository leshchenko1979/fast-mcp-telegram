# 🔍 Search Guidelines

## Overview

Telegram search has specific limitations that AI models should understand to provide optimal search results.

## What Works ✅

- **Exact words**: `"deadline"`, `"meeting"`, `"project"`
- **Multiple terms**: `"deadline, meeting, project"` (comma-separated)
- **Partial words**: `"proj"` (finds "project", "projects", etc.)
- **Case insensitive**: `"DEADLINE"` finds "deadline", "Deadline", etc.

## What Doesn't Work ❌

- **Wildcards**: `"proj*"`, `"meet%"`, `"dead*line"`
- **Regex patterns**: `"^project"`, `"deadline$"`, `"proj.*"`
- **Boolean operators**: `"project AND deadline"`, `"meeting OR call"`
- **Quotes for exact phrases**: `"exact phrase"` (treated as separate words)

## Best Practices 💡

- Use simple, common words that are likely to appear in messages
- Try multiple related terms: `"deadline, due, urgent"`
- Use partial words for broader matches: `"proj"` instead of `"project*"`
- Start with specific terms and broaden if needed
- Use chat-specific search when possible for better results

## Search Examples

### Global Search Examples

```json
// ✅ Good: Simple, common words
{"tool": "search_messages_globally", "params": {"query": "deadline", "limit": 20}}

// ✅ Good: Multiple related terms
{"tool": "search_messages_globally", "params": {"query": "deadline, due, urgent", "limit": 30}}

// ✅ Good: Partial word for broader matches
{"tool": "search_messages_globally", "params": {"query": "proj", "limit": 20}}

// ❌ Bad: Wildcards don't work
{"tool": "search_messages_globally", "params": {"query": "proj*"}}

// ❌ Bad: Regex patterns don't work
{"tool": "search_messages_globally", "params": {"query": "^project"}}

// ❌ Bad: Boolean operators don't work
{"tool": "search_messages_globally", "params": {"query": "project AND deadline"}}
```

### Chat-Specific Search Examples

```json
// ✅ Good: Search in specific chat
{"tool": "search_messages_in_chat", "params": {"chat_id": "-1001234567890", "query": "launch"}}

// ✅ Good: Get latest messages (no query)
{"tool": "search_messages_in_chat", "params": {"chat_id": "me", "limit": 10}}

// ✅ Good: Multi-term search in chat
{"tool": "search_messages_in_chat", "params": {"chat_id": "telegram", "query": "update, news"}}

// ✅ Good: Partial word search
{"tool": "search_messages_in_chat", "params": {"chat_id": "me", "query": "proj"}}
```

### Filtered Search Examples

```json
// ✅ Good: Filter by chat type
{"tool": "search_messages_globally", "params": {
  "query": "meeting",
  "chat_type": "private",
  "limit": 20
}}

// ✅ Good: Filter by date range
{"tool": "search_messages_globally", "params": {
  "query": "project",
  "min_date": "2024-01-01",
  "max_date": "2024-12-31",
  "limit": 30
}}

// ✅ Good: Combined filters
{"tool": "search_messages_globally", "params": {
  "query": "deadline, urgent",
  "chat_type": "private",
  "min_date": "2024-01-01",
  "limit": 15
}}
```

## Search Strategy for AI Models

### 1. Start Specific, Then Broaden
```json
// Start with specific term
{"tool": "search_messages_globally", "params": {"query": "deadline", "limit": 10}}

// If no results, try related terms
{"tool": "search_messages_globally", "params": {"query": "deadline, due, urgent", "limit": 20}}

// If still no results, try partial words
{"tool": "search_messages_globally", "params": {"query": "dead", "limit": 20}}
```

### 2. Use Chat-Specific Search When Possible
```json
// If user mentions a specific person/channel, search there first
{"tool": "search_messages_in_chat", "params": {"chat_id": "@username", "query": "project"}}

// Then try global search if needed
{"tool": "search_messages_globally", "params": {"query": "project", "limit": 20}}
```

### 3. Apply Filters Strategically
```json
// Use date filters to narrow results
{"tool": "search_messages_globally", "params": {
  "query": "meeting",
  "min_date": "2024-01-01",
  "limit": 20
}}

// Use chat type filters for targeted results
{"tool": "search_messages_globally", "params": {
  "query": "announcement",
  "chat_type": "channel",
  "limit": 15
}}
```

## Common Search Patterns

### Finding Messages by Content
```json
// Look for specific topics
{"tool": "search_messages_globally", "params": {"query": "budget, finance, money", "limit": 20}}

// Look for time-related messages
{"tool": "search_messages_globally", "params": {"query": "tomorrow, next week, deadline", "limit": 20}}

// Look for action items
{"tool": "search_messages_globally", "params": {"query": "todo, task, action", "limit": 20}}
```

### Finding Messages by Context
```json
// Recent messages from a specific person
{"tool": "search_messages_in_chat", "params": {"chat_id": "@username", "limit": 10}}

// Messages in a specific time period
{"tool": "search_messages_globally", "params": {
  "query": "project",
  "min_date": "2024-01-01",
  "max_date": "2024-01-31",
  "limit": 30
}}

// Messages in specific chat types
{"tool": "search_messages_globally", "params": {
  "query": "announcement",
  "chat_type": "channel",
  "limit": 20
}}
```

## Performance Tips

### Limit Management
- Start with small limits (10-20) for initial exploration
- Increase limits only if needed and results are relevant
- Use filters to narrow results before increasing limits
- Avoid requesting more than 50 results in a single search

### Query Optimization
- Use common words that are likely to appear in messages
- Try multiple related terms with comma separation
- Use partial words for broader matches
- Avoid complex search patterns that don't work

### Result Processing
- Check if results are relevant before requesting more
- Use the most specific search that returns useful results
- Combine multiple searches if needed rather than one large search
- Consider chat-specific searches for better targeting

## Troubleshooting

### No Results Found
1. Try simpler, more common words
2. Use partial words for broader matches
3. Try related terms with comma separation
4. Check if the search should be chat-specific
5. Verify the search terms are likely to appear in messages

### Too Many Results
1. Add date filters to narrow the time range
2. Use chat type filters for more targeted results
3. Use more specific search terms
4. Reduce the limit parameter
5. Try chat-specific search instead of global search

### Irrelevant Results
1. Use more specific search terms
2. Add filters (date, chat type) to narrow results
3. Try chat-specific search for better targeting
4. Use multiple related terms with comma separation
5. Consider the context and use appropriate search strategy
