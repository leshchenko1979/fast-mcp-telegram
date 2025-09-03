"""
Main server module for the Telegram bot functionality.
Provides API endpoints and core bot features.
"""

import asyncio
import os
import sys
import time
import traceback

from fastmcp import FastMCP
from loguru import logger

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.logging import setup_logging
from src.tools.contacts import get_contact_info, search_contacts_telegram
from src.tools.messages import (
    edit_message,
    read_messages_by_ids,
    send_message,
    send_message_to_phone_impl,
)
from src.tools.mtproto import invoke_mtproto_method
from src.tools.search import search_messages as search_messages_impl
from src.utils.error_handling import (
    handle_tool_error,
    log_and_build_error,
)

IS_TEST_MODE = "--test-mode" in sys.argv

if IS_TEST_MODE:
    transport = "http"
    host = "127.0.0.1"
    port = 8000
else:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP("Telegram MCP Server")

# Set up logging
setup_logging()


# Register tools with the MCP server
@mcp.tool()
async def search_messages(
    query: str,
    chat_id: str | None = None,
    limit: int = 50,
    chat_type: str | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    auto_expand_batches: int = 2,
    include_total_count: bool = False,
):
    """
    Search Telegram messages with advanced filtering.

    MODES:
    - Per-chat: Set chat_id + optional query (use 'me' for Saved Messages)
    - Global: No chat_id + required query (searches all chats)

    FEATURES:
    - Multiple queries: "term1, term2, term3"
    - Date filtering: ISO format (min_date="2024-01-01")
    - Chat type filter: "private", "group", "channel"

    EXAMPLES:
    search_messages(query="deadline", limit=20)  # Global search
    search_messages(chat_id="me", limit=10)      # Saved Messages
    search_messages(chat_id="-1001234567890", query="launch")  # Specific chat

    Args:
        query: Search terms (comma-separated). Required for global search, optional for per-chat
        chat_id: Target chat ID ('me' for Saved Messages) or None for global search
        limit: Max results (recommended: ≤50)
        chat_type: Filter by chat type ("private"/"group"/"channel")
        min_date: Min date filter (ISO format: "2024-01-01")
        max_date: Max date filter (ISO format: "2024-12-31")
        auto_expand_batches: Extra result batches for filtered searches
        include_total_count: Include total matching messages count (per-chat only)
    """
    search_result = await search_messages_impl(
        query,
        chat_id,
        limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=chat_type,
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
    )

    # Check if this is an error response
    error_response = handle_tool_error(
        search_result,
        "search_messages",
        f"search_{int(time.time())}",
        {
            "query": query,
            "chat_id": chat_id,
            "limit": limit,
            "min_date": min_date,
            "max_date": max_date,
            "chat_type": chat_type,
            "auto_expand_batches": auto_expand_batches,
            "include_total_count": include_total_count,
        },
    )
    if error_response:
        return error_response

    return search_result


@mcp.tool()
async def send_or_edit_message(
    chat_id: str,
    message: str,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
    message_id: int | None = None,
):
    """
    Send new message or edit existing message in Telegram chat.

    MODES:
    - Send: message_id=None (default)
    - Edit: message_id=<existing_message_id>

    FORMATTING:
    - parse_mode=None: Plain text
    - parse_mode="markdown": *bold*, _italic_, [link](url), `code`
    - parse_mode="html": <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>

    EXAMPLES:
    send_or_edit_message(chat_id="me", message="Hello!")  # Send to Saved Messages
    send_or_edit_message(chat_id="-1001234567890", message="Updated text", message_id=12345)  # Edit message

    Args:
        chat_id: Target chat ID ('me' for Saved Messages, numeric ID, or username)
        message: Message text to send or new text for editing
        reply_to_msg_id: Reply to specific message ID (send mode only)
        parse_mode: Text formatting ("markdown", "html", or None)
        message_id: Message ID to edit (None = send new message)
    """
    if message_id is not None:
        # Edit existing message
        result = await edit_message(chat_id, message_id, message, parse_mode)
    else:
        # Send new message
        result = await send_message(chat_id, message, reply_to_msg_id, parse_mode)

    # Check if this is an error response
    error_response = handle_tool_error(
        result,
        "send_or_edit_message",
        f"msg_op_{int(time.time())}",
        {
            "chat_id": chat_id,
            "message": message,
            "reply_to_msg_id": reply_to_msg_id,
            "parse_mode": parse_mode,
            "message_id": message_id,
        },
    )
    if error_response:
        return error_response

    return result


@mcp.tool()
async def read_messages(chat_id: str, message_ids: list[int]):
    """
    Read specific messages by their IDs from a Telegram chat.

    SUPPORTED CHAT FORMATS:
    - 'me': Saved Messages
    - Numeric ID: User/chat ID (e.g., 133526395)
    - Username: @channel_name or @username
    - Channel ID: -100xxxxxxxxx

    USAGE:
    - First use search_messages() to find message IDs
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
    3. Search messages: search_messages(chat_id=chat_id, query="topic")

    EXAMPLES:
    search_contacts("@telegram")      # Find user by username
    search_contacts("John Smith")     # Find by name
    search_contacts("+1234567890")    # Find by phone

    Args:
        query: Search term (name, username without @, or phone with +)
        limit: Max results (default: 20, recommended: ≤50)
    """
    result = await search_contacts_telegram(query, limit)

    # Check if this is an error response
    error_response = handle_tool_error(
        result,
        "search_contacts",
        f"contact_search_{int(time.time())}",
        {
            "query": query,
            "limit": limit,
        },
    )
    if error_response:
        return error_response

    return result


@mcp.tool()
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
async def send_message_to_phone(
    phone_number: str,
    message: str,
    first_name: str = "Contact",
    last_name: str = "Name",
    remove_if_new: bool = False,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
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
    try:
        import json

        try:
            params = json.loads(params_json)
        except Exception as e:
            return log_and_build_error(
                request_id=f"mtproto_json_{int(time.time())}",
                operation="invoke_mtproto",
                error_message=f"Invalid JSON in params_json: {e}",
                params={
                    "method_full_name": method_full_name,
                    "params_json": params_json,
                },
                exception=e,
            )

        # Convert any non-string keys to strings
        sanitized_params = {
            (k if isinstance(k, str) else str(k)): v for k, v in params.items()
        }

        result = await invoke_mtproto_method(
            method_full_name, sanitized_params, params_json
        )

        # Check if this is an error response
        error_response = handle_tool_error(
            result,
            "invoke_mtproto",
            f"mtproto_{int(time.time())}",
            {
                "method_full_name": method_full_name,
                "params_json": params_json,
            },
        )
        if error_response:
            return error_response

        return result
    except Exception as e:
        return log_and_build_error(
            request_id=f"mtproto_{int(time.time())}",
            operation="invoke_mtproto",
            error_message=f"Error in invoke_mtproto: {e!s}",
            params={
                "method_full_name": method_full_name,
                "params_json": params_json,
            },
            exception=e,
        )


def shutdown_procedure():
    """Synchronously performs async cleanup."""
    logger.info("Starting cleanup procedure.")
    from src.client.connection import cleanup_client

    # Create a new event loop for cleanup to avoid conflicts.
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup_client())
        loop.close()
        logger.info("Cleanup successful.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}\n{traceback.format_exc()}")


def main():
    """Entry point for console script; runs the MCP server and ensures cleanup."""
    if transport == "http":
        try:
            mcp.run(transport="http", host=host, port=port)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Initiating shutdown.")
        finally:
            shutdown_procedure()
    else:
        # For stdio transport, just run directly
        # FastMCP handles the stdio communication automatically
        try:
            mcp.run(transport="stdio")
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Initiating shutdown.")
        finally:
            shutdown_procedure()


# Run the server if this file is executed directly
if __name__ == "__main__":
    main()
