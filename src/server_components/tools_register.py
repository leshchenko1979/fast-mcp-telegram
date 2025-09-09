from typing import Literal

from fastmcp import FastMCP

from src.server_components import auth as server_auth
from src.server_components import errors as server_errors
from src.tools.contacts import get_contact_info, search_contacts_telegram
from src.tools.messages import (
    edit_message_impl,
    read_messages_by_ids,
    send_message_impl,
    send_message_to_phone_impl,
)
from src.tools.mtproto import invoke_mtproto_method
from src.tools.search import search_messages_impl
from src.utils.error_handling import log_and_build_error


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    @server_errors.with_error_handling("search_messages_globally")
    @server_auth.with_auth_context
    async def search_messages_globally(
        query: str,
        limit: int = 50,
        min_date: str | None = None,
        max_date: str | None = None,
        chat_type: Literal["private", "group", "channel"] | None = None,
        auto_expand_batches: int = 2,
        include_total_count: bool = False,
    ):
        """
        Search messages across all Telegram chats (global search).

        FEATURES:
        - Multiple queries: "term1, term2, term3"
        - Date filtering: ISO format (min_date="2024-01-01")
        - Chat type filter: "private", "group", "channel"

        EXAMPLES:
        search_messages_globally(query="deadline", limit=20)  # Global search
        search_messages_globally(query="project, launch", limit=30)  # Multi-term search
        search_messages_globally(query="proj", limit=20)  # Partial word search

        Args:
            query: Search terms (comma-separated). Required for global search.
            limit: Max results (recommended: ≤50)
            chat_type: Filter by chat type ("private"/"group"/"channel")
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
            auto_expand_batches=auto_expand_batches,
            include_total_count=include_total_count,
        )

    @mcp.tool()
    @server_errors.with_error_handling("search_messages_in_chat")
    @server_auth.with_auth_context
    async def search_messages_in_chat(
        chat_id: str,
        query: str | None = None,
        limit: int = 50,
        min_date: str | None = None,
        max_date: str | None = None,
        auto_expand_batches: int = 2,
        include_total_count: bool = False,
    ):
        """
        Search messages within a specific Telegram chat.

        FEATURES:
        - Multiple queries: "term1, term2, term3"
        - Date filtering: ISO format (min_date="2024-01-01")
        - Total count support for per-chat searches
        - No query = returns latest messages from the chat

        EXAMPLES:
        search_messages_in_chat(chat_id="me", limit=10)      # Saved Messages
        search_messages_in_chat(chat_id="-1001234567890", query="launch")  # Specific chat
        search_messages_in_chat(chat_id="telegram", query="update, news")  # Multi-term search

        Args:
            chat_id: Target chat ID ('me' for Saved Messages) or specific chat
            query: Optional search terms (comma-separated). If omitted, returns latest messages.
            limit: Max results (recommended: ≤50)
            min_date: Min date filter (ISO format: "2024-01-01")
            max_date: Max date filter (ISO format: "2024-12-31")
            auto_expand_batches: Extra result batches for filtered searches
            include_total_count: Include total matching messages count (per-chat only)
        """
        return await search_messages_impl(
            query=query,
            chat_id=chat_id,
            limit=limit,
            min_date=min_date,
            max_date=max_date,
            chat_type=None,
            auto_expand_batches=auto_expand_batches,
            include_total_count=include_total_count,
        )

    @mcp.tool()
    @server_errors.with_error_handling("send_message")
    @server_auth.with_auth_context
    async def send_message(
        chat_id: str,
        message: str,
        reply_to_msg_id: int | None = None,
        parse_mode: Literal["markdown", "html"] | None = None,
    ):
        """
        Send new message in Telegram chat.

        FORMATTING:
        - parse_mode=None: Plain text
        - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
        - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

        EXAMPLES:
        send_message(chat_id="me", message="Hello!")  # Send to Saved Messages
        send_message(chat_id="-1001234567890", message="New message", reply_to_msg_id=12345)  # Reply to message

        Args:
            chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
            message: Message text to send
            reply_to_msg_id: Reply to specific message ID (optional)
            parse_mode: Text formatting ("markdown", "html", or None)
        """
        return await send_message_impl(chat_id, message, reply_to_msg_id, parse_mode)

    @mcp.tool()
    @server_errors.with_error_handling("edit_message")
    @server_auth.with_auth_context
    async def edit_message(
        chat_id: str,
        message_id: int,
        message: str,
        parse_mode: Literal["markdown", "html"] | None = None,
    ):
        """
        Edit existing message in Telegram chat.

        FORMATTING:
        - parse_mode=None: Plain text
        - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
        - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

        EXAMPLES:
        edit_message(chat_id="me", message_id=12345, message="Updated text")  # Edit Saved Messages
        edit_message(chat_id="-1001234567890", message_id=67890, message="*Updated* message")  # Edit with formatting

        Args:
            chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
            message_id: Message ID to edit (required)
            message: New message text
            parse_mode: Text formatting ("markdown", "html", or None)
        """
        return await edit_message_impl(chat_id, message_id, message, parse_mode)

    @mcp.tool()
    @server_errors.with_error_handling("read_messages")
    @server_auth.with_auth_context
    async def read_messages(chat_id: str, message_ids: list[int]):
        """
        Read specific messages by their IDs from a Telegram chat.

        SUPPORTED CHAT FORMATS:
        - 'me': Saved Messages
        - Numeric ID: User/chat ID (e.g., 133526395)
        - Username: @channel_name or @username
        - Channel ID: -100xxxxxxxxx

        USAGE:
        - First use search_messages_globally() or search_messages_in_chat() to find message IDs
        - Then read specific messages using those IDs
        - Returns full message content with metadata

        EXAMPLES:
        read_messages(chat_id="me", message_ids=[680204, 680205])  # Saved Messages
        read_messages(chat_id="-1001234567890", message_ids=[123, 124])  # Channel

        Args:
            chat_id: Target chat identifier (use 'me' for Saved Messages)
            message_ids: List of message IDs to retrieve (from search results)
        """
        return await read_messages_by_ids(chat_id, message_ids)

    @mcp.tool()
    @server_errors.with_error_handling("search_contacts")
    @server_auth.with_auth_context
    async def search_contacts(query: str, limit: int = 20):
        """
        Search Telegram contacts and users by name, username, or phone number.

        SEARCH SCOPE:
        - Your saved contacts
        - Global Telegram users
        - Public channels and groups

        QUERY TYPES:
        - Name: "John Doe" or "Иванов"
        - Username: "@username" (without @)
        - Phone: "+1234567890"

        WORKFLOW:
        1. Search for contact: search_contacts("John Doe")
        2. Get chat_id from results
        3. Search messages: search_messages_in_chat(chat_id=chat_id, query="topic")

        EXAMPLES:
        search_contacts("@telegram")      # Find user by username
        search_contacts("John Smith")     # Find by name
        search_contacts("+1234567890")    # Find by phone

        Args:
            query: Search term (name, username without @, or phone with +)
            limit: Max results (default: 20, recommended: ≤50)
        """
        return await search_contacts_telegram(query, limit)

    @mcp.tool()
    @server_errors.with_error_handling("get_contact_details")
    @server_auth.with_auth_context
    async def get_contact_details(chat_id: str):
        """
        Get detailed profile information for a specific Telegram user or chat.

        USE CASES:
        - Get full user profile after finding chat_id
        - Retrieve contact details, bio, and status
        - Check if user is online/bot/channel

        SUPPORTED FORMATS:
        - Numeric user ID: 133526395
        - Username: "telegram" (without @)
        - Channel ID: -100xxxxxxxxx

        EXAMPLES:
        get_contact_details("133526395")      # User by ID
        get_contact_details("telegram")       # User by username
        get_contact_details("-1001234567890") # Channel by ID

        Args:
            chat_id: Target chat/user identifier (numeric ID, username, or channel ID)
        """
        return await get_contact_info(chat_id)

    @mcp.tool()
    @server_errors.with_error_handling("send_message_to_phone")
    @server_auth.with_auth_context
    async def send_message_to_phone(
        phone_number: str,
        message: str,
        first_name: str = "Contact",
        last_name: str = "Name",
        remove_if_new: bool = False,
        reply_to_msg_id: int | None = None,
        parse_mode: Literal["markdown", "html"] | None = None,
    ):
        """
        Send message to phone number, auto-managing Telegram contacts.

        FEATURES:
        - Auto-creates contact if phone not in contacts
        - Sends message immediately after contact creation
        - Optional contact cleanup after sending
        - Full message formatting support

        CONTACT MANAGEMENT:
        - Checks existing contacts first
        - Creates temporary contact only if needed
        - Removes temporary contact if remove_if_new=True

        REQUIREMENTS:
        - Phone number must be registered on Telegram
        - Include country code: "+1234567890"

        EXAMPLES:
        send_message_to_phone("+1234567890", "Hello from Telegram!")  # Basic send
        send_message_to_phone("+1234567890", "*Important*", remove_if_new=True)  # Auto cleanup

        Args:
            phone_number: Target phone number with country code (e.g., "+1234567890")
            message: Message text to send
            first_name: Contact first name (for new contacts only)
            last_name: Contact last name (for new contacts only)
            remove_if_new: Remove contact after sending if newly created
            reply_to_msg_id: Reply to specific message ID
            parse_mode: Text formatting ("markdown", "html", or None)

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
        )

    @mcp.tool()
    @server_errors.with_error_handling("invoke_mtproto")
    @server_auth.with_auth_context
    async def invoke_mtproto(method_full_name: str, params_json: str):
        """
        Execute low-level Telegram MTProto API methods directly.

        USE CASES:
        - Access advanced Telegram API features
        - Custom queries not covered by standard tools
        - Administrative operations

        METHOD FORMAT:
        - Full class name: "messages.GetHistory", "users.GetFullUser"
        - Telegram API method names with proper casing

        PARAMETERS:
        - JSON string with method parameters
        - Parameter names match Telegram API documentation
        - Supports complex nested objects

        EXAMPLES:
        invoke_mtproto("users.GetFullUser", '{"id": {"_": "inputUserSelf"}}')  # Get self info
        invoke_mtproto("messages.GetHistory", '{"peer": {"_": "inputPeerChannel", "channel_id": 123456, "access_hash": 0}, "limit": 10}')

        Args:
            method_full_name: Telegram API method name (e.g., "messages.GetHistory")
            params_json: Method parameters as JSON string

        Returns:
            API response as dict, or error details if failed
        """
        import json

        try:
            try:
                params = json.loads(params_json)
            except Exception as e:
                return log_and_build_error(
                    operation="invoke_mtproto",
                    error_message=f"Invalid JSON in params_json: {e}",
                    params={
                        "method_full_name": method_full_name,
                        "params_json": params_json,
                    },
                    exception=e,
                )

            sanitized_params = {
                (k if isinstance(k, str) else str(k)): v for k, v in params.items()
            }

            return await invoke_mtproto_method(
                method_full_name, sanitized_params, params_json
            )
        except Exception as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Error in invoke_mtproto: {e!s}",
                params={
                    "method_full_name": method_full_name,
                    "params_json": params_json,
                },
                exception=e,
            )
