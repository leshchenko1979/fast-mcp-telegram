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
    ContactFirstName,
    ContactLastName,
    FilesParam,
    FolderFilter,
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
    TopicsLimit,
)
from src.tools.contacts import find_chats_impl, get_chat_info_impl
from src.tools.messages import (
    edit_message_impl,
    send_message_impl,
    send_message_to_phone_impl,
)
from src.tools.mtproto import invoke_mtproto_impl
from src.tools.search import search_messages_impl

# Canonical absolute URL for Tools-Reference (appended to each MCP tool description).
TOOLS_REFERENCE_DOC_URL = "https://github.com/leshchenko1979/fast-mcp-telegram/blob/main/docs/Tools-Reference.md"

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
    "Do not combine message_ids with query or reply_to_id. "
    "Success: messages, has_more, optional total_count and discussion fields. "
)

_DESC_SEND_MESSAGE = _tool_description(
    "Send text and optional attachments to a chat. Success: send result dict. "
)

_DESC_EDIT_MESSAGE = _tool_description(
    "Replace text of an existing message you can edit in this chat. Success: edit result dict. "
)

_DESC_FIND_CHATS = _tool_description(
    "Find users/groups/channels by name, username, or phone. "
    "Global search (query required) searches all Telegram; "
    "with min_date, max_date, or folder, search is limited to your sidebar dialogs. "
    "Success: dict with key chats (list of chat objects). "
)

_DESC_GET_CHAT_INFO = _tool_description(
    "Load profile and metadata for one user, bot, group, or channel. "
    "Success: info dict; forum chats may include topics up to topics_limit. "
)

_DESC_SEND_PHONE = _tool_description(
    "Send to a phone number: may create a temporary contact, then send text or files. "
    "Success: send result plus contact_was_new / contact_removed when applicable. "
)

_DESC_INVOKE_MTPROTO = _tool_description(
    "Low-level Telegram API (MTProto) invoke for methods not wrapped by other tools. "
    "Dangerous methods require allow_dangerous=true. "
    "Success: API result dict or normalized error. "
)


def mcp_tool_with_restrictions(operation_name: str):
    """
    Combined decorator for MCP tools: error handling, auth context, bot restrictions.

    Args:
        operation_name: Name of the operation for error reporting and bot restrictions
    """

    def decorator(func):
        decorated_func = server_errors.with_error_handling(operation_name)(func)
        decorated_func = server_auth.with_auth_context(decorated_func)
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
    ) -> dict[str, Any]:
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
        limit: LimitMessages = 50,
        min_date: MinDate = None,
        max_date: MaxDate = None,
        auto_expand_batches: AutoExpandBatches = 2,
        include_total_count: IncludeTotalCount = False,
    ) -> dict[str, Any]:
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
        files: FilesParam = None,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
        folder: FolderFilter = None,
    ) -> dict[str, Any]:
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
        chat_id: ChatId, topics_limit: TopicsLimit = 20
    ) -> dict[str, Any]:
        """Profile and metadata for one chat or user (full doc URL in tool description)."""
        return await get_chat_info_impl(chat_id, topics_limit=topics_limit)

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
        files: FilesParam = None,
    ) -> dict[str, Any]:
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
    @server_errors.with_error_handling("invoke_mtproto")
    @server_auth.with_auth_context
    async def invoke_mtproto(
        method_full_name: MethodFullName,
        params_json: ParamsJson,
        allow_dangerous: AllowDangerous = False,
        resolve: ResolveEntities = True,
    ) -> dict[str, Any]:
        """Raw Telegram API invoke, advanced (full doc URL in tool description)."""
        return await invoke_mtproto_impl(
            method_full_name=method_full_name,
            params_json=params_json,
            allow_dangerous=allow_dangerous,
            resolve=resolve,
        )
