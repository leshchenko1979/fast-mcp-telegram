"""
Reusable Annotated parameter types for MCP tool JSON schemas.

Field descriptions are surfaced to MCP clients for LLM tool selection and argument filling.
Narrative tool documentation: https://github.com/leshchenko1979/fast-mcp-telegram/blob/main/docs/Tools-Reference.md

Optional parameters: use a plain type (e.g. ``str``, ``int``) with ``= None`` at the tool
signature — do not annotate ``T | None`` so MCP clients get simpler JSON Schema without
``anyOf`` null branches.
"""

from typing import Annotated, Literal

from pydantic import Field

# --- Shared across tools ---

ChatId = Annotated[
    str,
    Field(
        description=(
            "Target chat: numeric id (e.g. -100…), username without @, or 'me' for Saved Messages."
        )
    ),
]

MinDate = Annotated[
    str,
    Field(
        description=(
            "Inclusive minimum date filter (ISO 8601 date or datetime). "
            "Omit for no lower bound."
        )
    ),
]

MaxDate = Annotated[
    str,
    Field(
        description=(
            "Inclusive maximum date filter (ISO 8601 date or datetime). "
            "Omit for no upper bound."
        )
    ),
]

ChatTypeComma = Annotated[
    str,
    Field(
        description=(
            "Comma-separated chat kinds: private, bot, group, channel. "
            "Case-insensitive; extra spaces allowed."
        )
    ),
]

PublicFilter = Annotated[
    bool,
    Field(
        description=(
            "If true, prefer chats with a public username; if false, without. "
            "Does not apply to private DMs. Omit to skip this filter."
        )
    ),
]

# Same recommendation text; distinct Annotated names preserve schema clarity at call sites.
_RECOMMENDED_LIMIT_SUFFIX = " (recommended 50 or less)."

LimitMessages = Annotated[
    int,
    Field(description=f"Maximum messages to return{_RECOMMENDED_LIMIT_SUFFIX}"),
]

LimitChats = Annotated[
    int,
    Field(description=f"Maximum chats to return{_RECOMMENDED_LIMIT_SUFFIX}"),
]

AutoExpandBatches = Annotated[
    int,
    Field(
        description=(
            "Extra search batches to run when filters narrow results. "
            "Higher values may return more matches at the cost of latency."
        )
    ),
]

IncludeTotalCount = Annotated[
    bool,
    Field(
        description=(
            "If true, response may include total_count where supported "
            "(per-chat search; ignored for global search)."
        )
    ),
]

MessageBody = Annotated[
    str,
    Field(description="Message text. When sending files, used as caption."),
]

ParseMode = Annotated[
    Literal["markdown", "html", "auto"],
    Field(
        description=(
            "'markdown', 'html', or 'auto' (detect from content). Default is 'auto'."
        )
    ),
]

FilesParam = Annotated[
    str | list[str],
    Field(
        description=(
            "Attachment(s): HTTPS URL string, local path string, or list of those. "
            "Local paths work in stdio mode only."
        )
    ),
]

ReplyToId = Annotated[
    int,
    Field(
        description=(
            "Telegram message id to reply to. For forums, topic root id; "
            "for channel posts, post id (may create a comment). Omit for a new top-level message."
        )
    ),
]

MessageIdInChat = Annotated[
    int,
    Field(
        description="Message id in this chat to edit (from get_messages or Telegram)."
    ),
]

MessageIds = Annotated[
    list[int],
    Field(
        description=(
            "Exact message ids to fetch. Mutually exclusive with query and reply_to_id."
        )
    ),
]

# --- Query / search parameters ---

QueryGlobal = Annotated[
    str,
    Field(
        description=(
            "Search terms, comma-separated for multiple terms (OR-style global search). Required."
        )
    ),
]

QueryInChat = Annotated[
    str,
    Field(
        description=(
            "Search within this chat only; comma-separated terms. "
            "Omit to browse latest or use message_ids / reply_to_id modes."
        )
    ),
]

ReplyToForThread = Annotated[
    int,
    Field(
        description=(
            "Get replies in the thread for this message id (comments, forum topic, or replies). "
            "Optional query filters within that thread."
        )
    ),
]

QueryFindChats = Annotated[
    str,
    Field(
        description=(
            "Name, username (no @), phone (+country…), or comma-separated multi-queries. "
            "Required for global search unless you use min_date/max_date or folder alone."
        )
    ),
]

FolderFilter = Annotated[
    int | str,
    Field(
        description=(
            "Dialog folder: integer id or exact folder name (case-insensitive). "
            "Triggers sidebar-only search with other filters."
        )
    ),
]

# --- get_chat_info ---

TopicsLimit = Annotated[
    int,
    Field(description="Max forum topics to list when the chat is a forum."),
]

# --- send_message_to_phone ---

PhoneE164 = Annotated[
    str,
    Field(
        description="E.164 phone number with country code, e.g. +1234567890 (must be on Telegram)."
    ),
]

ContactFirstName = Annotated[
    str,
    Field(description="First name when creating a temporary contact."),
]

ContactLastName = Annotated[
    str,
    Field(description="Last name when creating a temporary contact."),
]

RemoveIfNew = Annotated[
    bool,
    Field(
        description="If true, delete the contact after send when it was created only for this send."
    ),
]

ReplyToMsgId = Annotated[
    int,
    Field(description="Reply to this message id in the target chat after resolve."),
]

# --- invoke_mtproto ---

MethodFullName = Annotated[
    str,
    Field(
        description=(
            'Telegram API method, e.g. "messages.GetHistory" or "users.GetFullUser" '
            "(normalization applied)."
        )
    ),
]

ParamsJson = Annotated[
    str,
    Field(
        description=(
            "JSON object string of TL parameters as in Telegram API docs; "
            'nested TL uses "_": "typeName" discriminator.'
        )
    ),
]

AllowDangerous = Annotated[
    bool,
    Field(
        description=(
            "If false, destructive methods (e.g. deletes) are blocked. Set true only when intended."
        )
    ),
]

ResolveEntities = Annotated[
    bool,
    Field(
        description=(
            "If true, resolve string/int peer-like fields to TL Input* entities before invoke."
        )
    ),
]
