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

        SEARCH LIMITATIONS:
        - NO wildcards: "proj*", "meet%" won't work
        - NO regex: "^project", "deadline$" won't work
        - Use simple terms: "proj" finds "project", "projects"
        - Case insensitive: "DEADLINE" finds "deadline"

        EXAMPLES:
        search_messages_globally(query="deadline", limit=20)
        search_messages_globally(query="project, launch", limit=30)
        search_messages_globally(query="proj", limit=20)
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
        """Send new message in Telegram chat."""
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
        """Edit existing message in Telegram chat."""
        return await edit_message_impl(chat_id, message_id, message, parse_mode)

    @mcp.tool()
    @server_errors.with_error_handling("read_messages")
    @server_auth.with_auth_context
    async def read_messages(chat_id: str, message_ids: list[int]):
        """Read specific messages by their IDs from a Telegram chat."""
        return await read_messages_by_ids(chat_id, message_ids)

    @mcp.tool()
    @server_errors.with_error_handling("search_contacts")
    @server_auth.with_auth_context
    async def search_contacts(query: str, limit: int = 20):
        """Search Telegram contacts and users by name, username, or phone number."""
        return await search_contacts_telegram(query, limit)

    @mcp.tool()
    @server_errors.with_error_handling("get_contact_details")
    @server_auth.with_auth_context
    async def get_contact_details(chat_id: str):
        """Get detailed profile information for a specific Telegram user or chat."""
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
