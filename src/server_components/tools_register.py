from typing import Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.server_components import auth as server_auth
from src.server_components import bot_restrictions
from src.server_components import errors as server_errors
from src.tools.contacts import find_chats_impl, get_chat_info_impl
from src.tools.messages import (
    edit_message_impl,
    send_message_impl,
    send_message_to_phone_impl,
)
from src.tools.mtproto import invoke_mtproto_impl
from src.tools.search import search_messages_impl


def mcp_tool_with_restrictions(operation_name: str):
    """
    Combined decorator for MCP tools that applies error handling, auth context, and bot restrictions.

    This reduces repetition of the three common decorators:
    - @server_errors.with_error_handling
    - @server_auth.with_auth_context
    - @bot_restrictions.restrict_non_bridge_for_bot_sessions

    Args:
        operation_name: Name of the operation for error reporting and bot restrictions
    """

    def decorator(func):
        # Apply the three decorators in the correct order
        decorated_func = server_errors.with_error_handling(operation_name)(func)
        decorated_func = server_auth.with_auth_context(decorated_func)
        return bot_restrictions.restrict_non_bridge_for_bot_sessions(operation_name)(
            decorated_func
        )

    return decorator


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, idempotentHint=True, openWorldHint=True
        )
    )
    @mcp_tool_with_restrictions("search_messages_globally")
    async def search_messages_globally(
        query: str,
        limit: int = 50,
        min_date: str | None = None,
        max_date: str | None = None,
        chat_type: str | None = None,
        public: bool | None = None,
        auto_expand_batches: int = 2,
        include_total_count: bool = False,
    ) -> dict:
        """
        Search messages across all Telegram chats (global search).

        FEATURES:
        - Multiple queries: "term1, term2, term3"
        - Date filtering: ISO format (min_date="2024-01-01")
        - Chat type filter: "private", "group", "channel" (comma-separated for multiple)
        - Public filter: True=with username, False=without username (never applies to private chats)

        EXAMPLES:
        search_messages_globally(query="deadline", limit=20)  # Global search
        search_messages_globally(query="project, launch", limit=30)  # Multi-term search
        search_messages_globally(query="urgent", chat_type="private")  # Private chats only
        search_messages_globally(query="news", chat_type="channel,group")  # Channels and groups
        search_messages_globally(query="team", chat_type="group", public=False)  # Private groups
        search_messages_globally(query="urgent", chat_type="private, group")  # Private chats and groups

        Args:
            query: Search terms (comma-separated). Required for global search.
            limit: Max results (recommended: ≤50)
            chat_type: Filter by chat type ("private"/"group"/"channel", comma-separated for multiple)
            public: Filter by public discoverability (True=with username, False=without username)
            min_date: Min date filter (ISO format: "2024-01-01")
            max_date: Max date filter (ISO format: "2024-12-31")
            auto_expand_batches: Extra result batches for filtered searches
            include_total_count: Include total matching messages count (ignored in global mode)
        """
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
        annotations=ToolAnnotations(
            readOnlyHint=True, idempotentHint=True, openWorldHint=True
        )
    )
    @mcp_tool_with_restrictions("get_messages")
    async def get_messages(
        chat_id: str,
        query: str | None = None,
        message_ids: list[int] | None = None,
        reply_to_id: int | None = None,
        limit: int = 50,
        min_date: str | None = None,
        max_date: str | None = None,
        auto_expand_batches: int = 2,
        include_total_count: bool = False,
    ) -> dict:
        """
        Get messages from a Telegram chat - supports search, specific IDs, and replies.

        MODES (mutually exclusive):
        1. SEARCH: chat_id + query - Search messages in chat
        2. BROWSE: chat_id only - Get latest messages
        3. READ BY IDs: chat_id + message_ids - Get specific messages
        4. GET REPLIES: chat_id + reply_to_id - Get replies to a message
        5. SEARCH REPLIES: chat_id + reply_to_id + query - Search within replies

        REPLIES MODE AUTOMATICALLY HANDLES:
        - Channel post comments (via discussion group)
        - Forum topic messages (topic_id = root message)
        - Regular message replies

        CONFLICTS (will error):
        - message_ids + reply_to_id: Cannot combine
        - message_ids + query: Cannot combine

        FEATURES:
        - Multiple search queries: "term1, term2, term3"
        - Date filtering: ISO format (min_date="2024-01-01")
        - Total count support for chat searches
        - Automatic discussion group detection for channel posts

        EXAMPLES:
        get_messages(chat_id="me", limit=10)  # Latest messages
        get_messages(chat_id="-1001234567890", query="launch")  # Search
        get_messages(chat_id="me", message_ids=[680204, 680205])  # Specific messages
        get_messages(chat_id="-1001234567890", reply_to_id=123)  # Post comments OR topic messages
        get_messages(chat_id="-1001234567890", reply_to_id=52)  # Forum topic messages
        get_messages(chat_id="me", reply_to_id=100, query="bug")  # Search in replies

        Args:
            chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
            query: Search terms (comma-separated). Optional unless global search.
            message_ids: List of specific message IDs to retrieve. Conflicts with query/reply_to_id.
            reply_to_id: Message ID to get replies from (post comments, forum topics, or regular replies)
            limit: Max results (recommended: ≤50)
            min_date: Min date filter (ISO format: "2024-01-01")
            max_date: Max date filter (ISO format: "2024-12-31")
            auto_expand_batches: Extra batches for filtered searches
            include_total_count: Include total message count (per-chat only)

        Returns:
            Dictionary with:
            - messages: List of message dicts
            - has_more: Boolean (always False for message_ids mode)
            - total_count: Total messages (if include_total_count=True)
            - reply_to_id: Original message ID (if reply_to_id used)
            - discussion_chat_id/discussion_total_count: (if channel post with discussion)
        """
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True))
    @mcp_tool_with_restrictions("send_message")
    async def send_message(
        chat_id: str,
        message: str,
        reply_to_id: int | None = None,
        parse_mode: Literal["markdown", "html", "auto"] | None = "auto",
        files: str | list[str] | None = None,
    ) -> dict:
        """
        Send new message in Telegram chat, optionally with files.

        FORMATTING:
        - parse_mode="auto" (default): Automatically detects Markdown or HTML based on content
        - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
        - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

        FILE SENDING:
        - files: Single file or list of files (URLs or local paths)
        - URLs work in all modes (http:// or https://)
        - Local file paths only work in stdio mode
        - Supports images, videos, documents, audio, and other file types
        - When files are provided, message becomes the caption

        EXAMPLES:
        send_message(chat_id="me", message="Hello!")  # Send text to Saved Messages
        send_message(chat_id="-1001234567890", message="New message", reply_to_id=12345)  # Reply
        send_message(chat_id="-1001234567890", message="Topic message", reply_to_id=52)  # Post into forum topic
        send_message(chat_id="-1001234567890", message="My comment", reply_to_id=42)  # Channel post comment
        send_message(chat_id="me", message="Check this", files="https://example.com/doc.pdf")  # Send file from URL
        send_message(chat_id="me", message="Photos", files=["https://ex.com/1.jpg", "https://ex.com/2.jpg"])  # Multiple files
        send_message(chat_id="me", message="Report", files="/path/to/file.pdf")  # Local file (stdio mode only)

        Args:
            chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
            message: Message text to send (becomes caption when files are provided)
            reply_to_id: Message ID to reply to. For forum chats, topic root ID. For channel posts, post ID (auto-posts comment).
            parse_mode: Text formatting ("markdown", "html", "auto", or None). Default: "auto"
            files: Single file or list of files to send (URLs or local paths, optional)
        """
        return await send_message_impl(chat_id, message, reply_to_id, parse_mode, files)

    @mcp.tool(
        annotations=ToolAnnotations(
            destructiveHint=True, idempotentHint=True, openWorldHint=True
        )
    )
    @mcp_tool_with_restrictions("edit_message")
    async def edit_message(
        chat_id: str,
        message_id: int,
        message: str,
        parse_mode: Literal["markdown", "html", "auto"] | None = "auto",
    ) -> dict:
        """
        Edit existing message in Telegram chat.

        FORMATTING:
        - parse_mode="auto" (default): Automatically detects Markdown or HTML based on content
        - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
        - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

        EXAMPLES:
        edit_message(chat_id="me", message_id=12345, message="Updated text")  # Edit Saved Messages
        edit_message(chat_id="-1001234567890", message_id=67890, message="*Updated* message")  # Edit with formatting

        Args:
            chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
            message_id: Message ID to edit (required)
            message: New message text
            parse_mode: Text formatting ("markdown", "html", "auto", or None). Default: "auto"
        """
        return await edit_message_impl(
            chat_id,
            message_id,
            message,
            parse_mode,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, idempotentHint=True, openWorldHint=True
        )
    )
    @mcp_tool_with_restrictions("find_chats")
    async def find_chats(
        query: str | None = None,
        limit: int = 20,
        chat_type: str | None = None,
        public: bool | None = None,
        min_date: str | None = None,
        max_date: str | None = None,
        muted: bool | None = None,
    ) -> list[dict] | dict:
        """
        Find Telegram chats (users, groups, channels, bots) by name, username, or phone number.

        TWO SEARCH MODES:

        1. GLOBAL SEARCH (default, no date filtering):
        - Searches all of Telegram by name/username/phone
        - Can find any user, group, or channel
        - Does NOT return last_activity_date or muted

        2. DIALOG SEARCH (when date filtering is used):
        - Searches only your sidebar/dialog list
        - Cannot find chats you're not already connected to
        - Returns last_activity_date and muted for each chat

        QUERY TYPES:
        - Name: "John Doe" or "Иванов"
        - Username: "@username" (without @)
        - Phone: "+1234567890"

        MULTI-TERM QUERIES:
        - Comma-separated terms are supported: "john, @telegram, +123"
        - Each term is searched independently, then results are merged and deduplicated by chat_id
        - The final list is truncated to the requested limit

        PUBLIC FILTER:
        - Public filter never applies to private chats or bot users
        - Only affects groups and channels

        DATE FILTERING:
        - When min_date or max_date is provided, switches to dialog-based search
        - **Dialog search only returns chats from your Telegram sidebar** (not global Telegram search)
        - Dialog search provides last_activity_date and muted for each chat
        - Query matching in dialog search is case-insensitive substring match against title/username/name
        - Without date filters, uses global Telegram search (can find any chat by name/username/phone)
        - Date filtering is done client-side (Telegram API ignores offset_date parameter)
        - Supports full ISO 8601 datetime: "2024-01-01", "2024-01-01T14:30:00", "2024-01-01T14:30:00+00:00"
        - Timezone-naive values are assumed UTC

        WORKFLOW:
        1. Find chat: find_chats("John Doe")
        2. Get chat_id from results
        3. Search messages: get_messages(chat_id=chat_id, query="topic")

        EXAMPLES:
        # Global search (no date filtering) - can find any chat
        find_chats("@telegram")      # Find user by username (global search)
        find_chats("John Smith")     # Find by name (global search)
        find_chats("+1234567890")    # Find by phone (global search)
        find_chats("news", chat_type="channel,group")    # Find channels and groups
        find_chats("news", public=True)    # Find public groups and channels only
        find_chats("team", chat_type="group", public=False)  # Private groups only
        find_chats("assistant", chat_type="bot")              # Find bot accounts

        # Dialog search (with date filtering) - searches YOUR sidebar chats only
        find_chats(min_date="2024-01-01")  # Your chats active since 2024
        find_chats("project", min_date="2024-01-01", max_date="2024-12-31")  # Your chats active in 2024
        find_chats(muted=True, min_date="2024-01-01")     # Muted chats (with date filter)
        find_chats("alert", muted=False)                   # Unmuted chats matching "alert"

        TYPE FIELD IN RESULTS:
        - "private" = human user
        - "bot"    = bot user (also exempt from public filter)
        - "group"  = group/supergroup
        - "channel" = channel

        Args:
            query: Search term(s). Supports comma-separated multi-queries. When date filtering is used, searches your sidebar chats only.
            limit: Max results (default: 20, recommended: ≤50)
            chat_type: Optional filter ("private"|"group"|"channel"|"bot", comma-separated for multiple)
            public: Optional filter for public discoverability (True=with username, False=without username). Ignored for private chats and bots.
            min_date: Minimum last activity date (ISO 8601 format, e.g. "2024-01-01" or "2024-01-01T14:30:00"). Uses dialog search (your sidebar chats only).
            max_date: Maximum last activity date (ISO 8601 format, e.g. "2024-12-31" or "2024-12-31T23:59:59"). Uses dialog search (your sidebar chats only).
            muted: Optional filter for muted chats (dialog-based; silently ignored in global search). True=muted, False=unmuted.
        """
        return await find_chats_impl(
            query, limit, chat_type, public, min_date, max_date, muted
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, idempotentHint=True, openWorldHint=True
        )
    )
    @mcp_tool_with_restrictions("get_chat_info")
    async def get_chat_info(chat_id: str, topics_limit: int = 20) -> dict:
        """
        Get detailed profile information for a specific Telegram user or chat.

        USE CASES:
        - Get full user profile after finding chat_id
        - Retrieve contact details, bio, status, subscribers count, and muted status
        - Check if user is online/bot/channel

        SUPPORTED FORMATS:
        - Numeric user ID: 133526395
        - Username: "telegram" (without @)
        - Channel ID: -100xxxxxxxxx

        EXAMPLES:
        get_chat_info("133526395")      # User by ID
        get_chat_info("telegram")       # User by username
        get_chat_info("-1001234567890") # Channel by ID

        Args:
            chat_id: Target chat/user identifier (numeric ID, username, or channel ID)
            topics_limit: Max forum topics to include when chat is forum-enabled

        Returns:
            Chat info including muted status. Also includes last_activity_date and
            topics (for forums) when available.
        """
        return await get_chat_info_impl(chat_id, topics_limit=topics_limit)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True))
    @mcp_tool_with_restrictions("send_message_to_phone")
    async def send_message_to_phone(
        phone_number: str,
        message: str,
        first_name: str = "Contact",
        last_name: str = "Name",
        remove_if_new: bool = False,
        reply_to_msg_id: int | None = None,
        parse_mode: Literal["markdown", "html", "auto"] | None = "auto",
        files: str | list[str] | None = None,
    ) -> dict:
        """
        Send message to phone number, auto-managing Telegram contacts, optionally with files.

        FEATURES:
        - Auto-creates contact if phone not in contacts
        - Sends message immediately after contact creation
        - Optional contact cleanup after sending
        - Full message formatting support
        - File sending support (URLs or local paths)

        CONTACT MANAGEMENT:
        - Checks existing contacts first
        - Creates temporary contact only if needed
        - Removes temporary contact if remove_if_new=True

        FILE SENDING:
        - files: Single file or list of files (URLs or local paths)
        - URLs work in all modes (http:// or https://)
        - Local file paths only work in stdio mode
        - Supports images, videos, documents, audio, and other file types
        - When files are provided, message becomes the caption

        REQUIREMENTS:
        - Phone number must be registered on Telegram
        - Include country code: "+1234567890"

        EXAMPLES:
        send_message_to_phone("+1234567890", "Hello from Telegram!")  # Basic send
        send_message_to_phone("+1234567890", "*Important*", remove_if_new=True)  # Auto cleanup
        send_message_to_phone("+1234567890", "Check this", files="https://example.com/doc.pdf")  # Send with file

        Args:
            phone_number: Target phone number with country code (e.g., "+1234567890")
            message: Message text to send (becomes caption when files are provided)
            first_name: Contact first name (for new contacts only)
            last_name: Contact last name (for new contacts only)
            remove_if_new: Remove contact after sending if newly created
            reply_to_msg_id: Reply to specific message ID
            parse_mode: Text formatting ("markdown", "html", "auto", or None). Default: "auto"
            files: Single file or list of files to send (URLs or local paths, optional)

        Returns:
            Message send result + contact management info (contact_was_new, contact_removed)
        """
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True))
    @server_errors.with_error_handling("invoke_mtproto")
    @server_auth.with_auth_context
    async def invoke_mtproto(
        method_full_name: str,
        params_json: str,
        allow_dangerous: bool = False,
        resolve: bool = True,
    ) -> dict:
        """
        Execute low-level Telegram MTProto API methods directly.

        USE CASES:
        - Access advanced Telegram API features
        - Custom queries not covered by standard tools
        - Administrative operations

        METHOD FORMAT:
        - Full class name: "messages.GetHistory", "users.GetFullUser"
        - Telegram API method names with proper casing (case-insensitive)
        - Methods are automatically normalized to correct format

        PARAMETERS:
        - JSON string with method parameters
        - Parameter names match Telegram API documentation
        - Supports complex nested objects

        ENTITY RESOLUTION:
        - Set resolve=true to automatically resolve entity-like parameters
        - Handles: peer, user, chat, channel, etc. (strings/ints → TL objects)
        - Useful for simplifying parameter preparation

        SECURITY:
        - Dangerous methods (delete operations) blocked by default
        - Pass allow_dangerous=true to override for destructive operations

        EXAMPLES:
        invoke_mtproto("users.GetFullUser", '{"id": {"_": "inputUserSelf"}}')  # Get self info
        invoke_mtproto("messages.GetHistory", '{"peer": "username", "limit": 10}')  # Auto-resolve peer (default)
        invoke_mtproto("messages.DeleteMessages", '{"id": [123]}', allow_dangerous=True)  # Dangerous operation

        Args:
            method_full_name: Telegram API method name (e.g., "messages.GetHistory")
            params_json: Method parameters as JSON string
            allow_dangerous: Allow dangerous methods like delete operations (default: False)
            resolve: Automatically resolve entity-like parameters (default: True)

        Returns:
            API response as dict, or error details if failed
        """
        return await invoke_mtproto_impl(
            method_full_name=method_full_name,
            params_json=params_json,
            allow_dangerous=allow_dangerous,
            resolve=resolve,
        )
