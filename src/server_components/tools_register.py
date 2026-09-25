from __future__ import annotations

import functools
import inspect
import time
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.server_components import auth as server_auth
from src.server_components import bot_restrictions
from src.server_components import errors as server_errors
from src.server_components.mcp_tool_types import (
    AllowDangerous,
    AutoExpandBatches,
    ChatId,
    ChatTypeComma,
    CommonChatsLimit,
    ContactFirstName,
    ContactLastName,
    ContextWindow,
    FilesListParam,
    FilterParam,
    FromUser,
    IncludeReplies,
    IncludeSensitive,
    IncludeTotalCount,
    LimitChats,
    LimitMessages,
    MaxDate,
    MessageBody,
    MessageIdInChat,
    MessageIds,
    MethodFullName,
    MinDate,
    ParamsJson,
    ParseMode,
    PhoneE164,
    PublicFilter,
    QueryFindChats,
    QueryGlobal,
    QueryInChat,
    RemoveIfNew,
    ReplyToForThread,
    ReplyToId,
    ReplyToMsgId,
    ResolveEntities,
    ThreadScope,
    TopicsLimit,
)
from src.server_components.session_acl import enforce_session_acl
from src.telemetry import metrics, sanitize_error_trace
from src.tools.chat_discovery.chat_info import get_chat_info_impl
from src.tools.chat_discovery.find_chats import find_chats_impl
from src.tools.messages import (
    edit_message_impl,
    send_message_impl,
    send_message_to_phone_impl,
)
from src.tools.mtproto import invoke_mtproto_impl
from src.tools.return_types import (
    ChatInfoResult,
    FindChatsResult,
    MtprotoResult,
    SearchResult,
    SendEditResult,
    SendToPhoneResult,
)
from src.tools.search import search_messages_impl

# Canonical absolute URL for Tools-Reference (appended to each MCP tool description).
TOOLS_REFERENCE_DOC_URL = "https://github.com/alexeyleshchenko/fast-mcp-telegram/blob/main/docs/Tools-Reference.md"

# MCP-visible tool descriptions (short; full examples at TOOLS_REFERENCE_DOC_URL).


def _tool_description(body: str, *, extra: str = "") -> str:
    return body + extra + f" Full documentation: {TOOLS_REFERENCE_DOC_URL}"


_DESC_SEARCH_GLOBAL = _tool_description(
    "Search all Telegram chats at once (not scoped to one chat). "
    "Comma-separated query terms; optional filters by date, chat kind, and public username. "
    "Success: message list and metadata dict. ",
    extra="Global search ignores include_total_count.",
)

_DESC_GET_MESSAGES = _tool_description(
    "Read or search messages in one chat: browse latest, search text, fetch by ids, "
    "or load replies to a message (comments, forum topics, threads). "
    "Use from_user to filter by sender (server-side, per-chat only). "
    "Use context to include neighboring messages and reply chains around each result. "
    "Use include_replies to fetch up to 5 direct replies per result. "
    "Do not combine message_ids with query or reply_to_id. "
    "Success: messages, has_more, optional total_count and discussion fields. "
)

_DESC_SEND_MESSAGE = _tool_description(
    "Send text and optional file attachments to a Telegram chat. "
    "Supports reply-to (including forum topics and channel discussion groups), "
    "parse_mode: classic markdown/html/auto (entities) or rich (Rich Message document; "
    "dialect auto-detected). parse_mode=rich cannot be combined with files. "
    "File attachments as http(s) URLs, local paths, or data: URIs. "
    "When files are provided, the message text becomes a caption. "
    "For channel posts with reply_to_id, automatically posts in the linked discussion group. "
    "Success: dict with message_id, date, chat, text, status='sent', and sender info "
    "(rich messages also set rich=true and rich_format). "
    "Error: dict with ok=false and error string. "
    "Use send_message to create new messages; use edit_message to modify existing ones. "
    "Use send_message_to_phone when targeting a phone number instead of a chat_id. "
)

_DESC_EDIT_MESSAGE = _tool_description(
    "Replace the text of an existing message in a Telegram chat. "
    "Only works on messages sent by the authenticated account. "
    "Cannot edit media or other message attributes — text only. "
    "parse_mode: classic markdown/html/auto or rich (Rich Message; dialect auto-detected). "
    "Success: dict with message_id, date, chat, text, status='edited', and edit_date "
    "(rich messages also set rich=true and rich_format). "
    "Error: dict with ok=false and error string (e.g. message not found or not editable). "
    "Use edit_message to update a previously sent message; use send_message to create new ones. "
)

_DESC_FIND_CHATS = _tool_description(
    "Find users/groups/channels by name, username, or phone. "
    "Comma-separated usernames are searched in parallel and results are merged round-robin. "
    "Global search (query required) searches all Telegram; "
    "with min_date, max_date, or filter, search uses dialog list or a named filter; "
    "include_peers filters use last-activity from GetPeerDialogs; flag-based filters use dialog list dates. "
    "Success: dict with key chats (list of chat objects). "
)

_DESC_GET_CHAT_INFO = _tool_description(
    "Load profile and metadata for one user, bot, group, or channel. "
    "Success: info dict; forum chats may include topics up to topics_limit; "
    "user targets may include common_chats up to common_chats_limit. "
)

_DESC_SEND_PHONE = _tool_description(
    "Send to a phone number: may create a temporary contact, then send text or files. "
    "Supports parse_mode: classic markdown/html/auto or rich (Rich Message; "
    "dialect auto-detected). parse_mode=rich cannot be combined with files. "
    "Success: send result plus contact_was_new / contact_removed when applicable. "
)

_DESC_INVOKE_MTPROTO = _tool_description(
    "Low-level Telegram API (MTProto) invoke for methods not wrapped by other tools. "
    "Dangerous methods require allow_dangerous=true. "
    "Success: API result dict or normalized error. "
    "PII and credential-shaped fields (phone, access_hash) are dropped from a "
    "successful result by default; pass include_sensitive=true for the raw payload. "
)


def _matches_default(value: Any, default: Any) -> bool:
    """Best-effort: is *value* the simple scalar default?

    Only compares well-defined immutable types (None, bool, int, float, str,
    bytes).  Anything else (lists, dicts, objects) is treated as explicitly
    provided — conservative but safe.
    """
    if isinstance(default, (type(None), bool, int, float, str, bytes)):
        return value == default
    return False


def mcp_tool_with_restrictions(
    operation_name: str, *, allow_bot_sessions: bool = False
):
    """
    Combined decorator for MCP tools: error handling, ACL, auth context, bot restrictions.

    Call order (outer → inner): bot → auth → error → ACL → func.
    Auth must run before ACL so get_request_token() is set for pre-checks.
    ACL wraps the original tool function so signature-based checks remain robust.

    Args:
        operation_name: Name of the operation for error reporting and bot restrictions
        allow_bot_sessions: When True, skip bot restriction (for MTProto bridge tools)
    """

    def decorator(func):
        """Wrap tool call with per-tool timing, parameter-set breakdown, and error traces."""

        # Pre-compute parameter defaults from function signature
        # so _telemetry_wrapper can skip framework-filled defaults
        # and only track params the caller explicitly provided.
        #
        # This relies on Pydantic/MCP always calling tools with fully-populated
        # keyword arguments (all declared params, defaults filled in for missing
        # ones). Params whose values match their signature defaults are treated
        # as likely framework-filled and excluded from the param set key.
        # If the argument-passing mechanism changes (e.g. to positional-only
        # or partial kwargs), this logic must be revisited.
        _sig = inspect.signature(func)
        _param_defaults = {
            name: param.default
            for name, param in _sig.parameters.items()
            if param.default is not param.empty
        }

        @functools.wraps(func)
        async def _telemetry_wrapper(*args, **kwargs):
            # Telemetry layer must never break tool execution.
            # Assume MCP/Pydantic always calls tools with fully-populated keyword args.
            # Only track params that differ from their signature defaults.
            param_keys = frozenset(
                name
                for name, value in kwargs.items()
                if name not in _param_defaults
                or not _matches_default(value, _param_defaults[name])
            )
            t0 = time.perf_counter()
            error: str | None = None
            try:
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    error = sanitize_error_trace(exc)
                    raise
                if isinstance(result, dict) and result.get("ok") is False:
                    error = str(result.get("error", ""))
                return result
            finally:
                metrics.record_tool_call(
                    tool=operation_name,
                    params=param_keys,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    error=error,
                )

        decorated_func = _telemetry_wrapper
        decorated_func = enforce_session_acl(operation_name)(decorated_func)
        decorated_func = server_errors.with_error_handling(operation_name)(
            decorated_func
        )
        decorated_func = server_auth.require_auth(decorated_func)
        if allow_bot_sessions:
            return decorated_func
        return bot_restrictions.restrict_non_bridge_for_bot_sessions(operation_name)(
            decorated_func
        )

    return decorator


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        description=_DESC_SEARCH_GLOBAL,
        annotations=ToolAnnotations(
            title="Search messages globally",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("search_messages_globally")
    async def search_messages_globally(
        query: QueryGlobal,
        limit: LimitMessages = 50,
        min_date: MinDate = None,
        max_date: MaxDate = None,
        chat_type: ChatTypeComma = None,
        public: PublicFilter = None,
        auto_expand_batches: AutoExpandBatches = 2,
        include_total_count: IncludeTotalCount = False,
    ) -> SearchResult:
        """Global Telegram message search (full doc URL is in the MCP tool description)."""
        return await search_messages_impl(
            query=query,
            chat_id=None,
            limit=limit,
            min_date=min_date,
            max_date=max_date,
            chat_type=chat_type,
            public=public,
            auto_expand_batches=auto_expand_batches,
            include_total_count=include_total_count,
        )

    @mcp.tool(
        description=_DESC_GET_MESSAGES,
        annotations=ToolAnnotations(
            title="Get messages in chat",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("get_messages")
    async def get_messages(
        chat_id: ChatId,
        query: QueryInChat = None,
        message_ids: MessageIds = None,
        reply_to_id: ReplyToForThread = None,
        thread_scope: ThreadScope = "auto",
        limit: LimitMessages = 50,
        min_date: MinDate = None,
        max_date: MaxDate = None,
        from_user: FromUser = None,
        context: ContextWindow = 0,
        include_replies: IncludeReplies = False,
        auto_expand_batches: AutoExpandBatches = 2,
        include_total_count: IncludeTotalCount = False,
    ) -> SearchResult:
        """Browse, search, fetch by ids, or load replies in one chat (full doc URL in tool description)."""
        return await search_messages_impl(
            query=query,
            chat_id=chat_id,
            message_ids=message_ids,
            reply_to_id=reply_to_id,
            limit=limit,
            min_date=min_date,
            max_date=max_date,
            chat_type=None,
            auto_expand_batches=auto_expand_batches,
            include_total_count=include_total_count,
            thread_scope=thread_scope,
            from_user=from_user,
            context=context,
            include_replies=include_replies,
        )

    @mcp.tool(
        description=_DESC_SEND_MESSAGE,
        annotations=ToolAnnotations(
            title="Send message",
            destructiveHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("send_message")
    async def send_message(
        chat_id: ChatId,
        message: MessageBody,
        reply_to_id: ReplyToId = None,
        parse_mode: ParseMode = "auto",
        files: FilesListParam = None,
    ) -> SendEditResult:
        """Send text or media to a chat (full doc URL in tool description)."""
        return await send_message_impl(chat_id, message, reply_to_id, parse_mode, files)

    @mcp.tool(
        description=_DESC_EDIT_MESSAGE,
        annotations=ToolAnnotations(
            title="Edit message",
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("edit_message")
    async def edit_message(
        chat_id: ChatId,
        message_id: MessageIdInChat,
        message: MessageBody,
        parse_mode: ParseMode = "auto",
    ) -> SendEditResult:
        """Edit an existing message (full doc URL in tool description)."""
        return await edit_message_impl(
            chat_id,
            message_id,
            message,
            parse_mode,
        )

    @mcp.tool(
        description=_DESC_FIND_CHATS,
        annotations=ToolAnnotations(
            title="Find chats",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("find_chats")
    async def find_chats(
        query: QueryFindChats = None,
        limit: LimitChats = 20,
        chat_type: ChatTypeComma = None,
        public: PublicFilter = None,
        min_date: MinDate = None,
        max_date: MaxDate = None,
        folder: FilterParam = None,
    ) -> FindChatsResult:
        """Find chats by query, folder, or activity dates (full doc URL in tool description)."""
        return await find_chats_impl(
            query, limit, chat_type, public, min_date, max_date, folder
        )

    @mcp.tool(
        description=_DESC_GET_CHAT_INFO,
        annotations=ToolAnnotations(
            title="Get chat info",
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("get_chat_info")
    async def get_chat_info(
        chat_id: ChatId,
        topics_limit: TopicsLimit = 20,
        common_chats_limit: CommonChatsLimit = 10,
    ) -> ChatInfoResult:
        """Profile and metadata for one chat or user (full doc URL in tool description)."""
        return await get_chat_info_impl(
            chat_id,
            topics_limit=topics_limit,
            common_chats_limit=common_chats_limit,
        )

    @mcp.tool(
        description=_DESC_SEND_PHONE,
        annotations=ToolAnnotations(
            title="Send message to phone",
            destructiveHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("send_message_to_phone")
    async def send_message_to_phone(
        phone_number: PhoneE164,
        message: MessageBody,
        first_name: ContactFirstName = "Contact",
        last_name: ContactLastName = "Name",
        remove_if_new: RemoveIfNew = False,
        reply_to_msg_id: ReplyToMsgId = None,
        parse_mode: ParseMode = "auto",
        files: FilesListParam = None,
    ) -> SendToPhoneResult:
        """Send to a phone number with optional contact auto-create (full doc URL in tool description)."""
        return await send_message_to_phone_impl(
            phone_number=phone_number,
            message=message,
            first_name=first_name,
            last_name=last_name,
            remove_if_new=remove_if_new,
            reply_to_msg_id=reply_to_msg_id,
            parse_mode=parse_mode,
            files=files,
        )

    @mcp.tool(
        description=_DESC_INVOKE_MTPROTO,
        annotations=ToolAnnotations(
            title="Invoke MTProto",
            destructiveHint=True,
            openWorldHint=True,
        ),
    )
    @mcp_tool_with_restrictions("invoke_mtproto", allow_bot_sessions=True)
    async def invoke_mtproto(
        method_full_name: MethodFullName,
        params_json: ParamsJson,
        allow_dangerous: AllowDangerous = False,
        resolve: ResolveEntities = True,
        include_sensitive: IncludeSensitive = False,
    ) -> MtprotoResult:
        """Raw Telegram API invoke, advanced (full doc URL in tool description)."""
        return await invoke_mtproto_impl(
            method_full_name=method_full_name,
            params_json=params_json,
            allow_dangerous=allow_dangerous,
            resolve=resolve,
            include_sensitive=include_sensitive,
        )
