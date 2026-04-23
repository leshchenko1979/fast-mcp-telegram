# Filters vs Folders

Telegram's UI refers to "folders" but the underlying MTProto API and our implementation use the term **dialog filters**.

## Why "filter" Instead of "folder"?

In the Telegram UI, users create "folders" to organize their chats. However, these are actually **dialog filters** — smart lists defined by rules (flags) and/or explicit peer lists.

### Dialog Filters vs Physical Sidebar Folders

| Concept | MTProto `folder_id` | UI Name |
|---------|---------------------|---------|
| Main (all chats) | `0` | Main sidebar |
| Archive | `1` | Archive folder |
| Custom filter | N/A (not supported) | User-created "folder" |

**Key limitation**: The MTProto API's `folder_id` parameter in `messages.getDialogs` only accepts physical sidebar folder IDs (`0` = Main, `1` = Archive). Custom dialog filter IDs cannot be used with `folder_id`.

## How Dialog Filters Work

Dialog filters have two components:

### 1. Flags (Rule-based)

Boolean flags that determine which chats match the filter:

- `contacts` — include contacts
- `non_contacts` — include non-contacts
- `groups` — include supergroups (megagroups)
- `broadcasts` — include channels
- `bots` — include bots
- `exclude_muted` — exclude muted chats
- `exclude_read` — exclude chats with no unread messages
- `exclude_archived` — exclude archived chats

When all flags are `False`, the filter matches nothing unless explicit peers are listed.

### 2. Include/Exclude Peers (Explicit List)

Filters can explicitly include or exclude specific chats by their peer (user, chat, or channel). These take priority over flags.

## Implementation Approach

Since MTProto doesn't support custom filter IDs with `iter_dialogs`, we use two workarounds:

### For Filters with `include_peers`

1. Get the filter definition to retrieve the list of explicitly included peers
2. Resolve each `InputPeer` to a real entity via `get_entity()`
3. Use `GetPeerDialogsRequest` in chunks to get last activity dates
4. Apply any additional flag-based filtering

### For Flag-based Filters (no `include_peers`)

1. Iterate all dialogs via `iter_dialogs()` without a folder parameter
2. For each dialog, check if it matches the filter's flags
3. Apply date filters if specified

## Date Filtering Limitation

When a filter has `include_peers`, date parameters (`min_date`, `max_date`) are **ignored**. This is because `GetPeerDialogsRequest` does not return dialog date information — only the last message date per peer. Use flag-based filters when date filtering is needed.
