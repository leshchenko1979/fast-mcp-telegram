"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

from typing import Any

from loguru import logger
from telethon.tl.functions.contacts import SearchRequest

from src.client.connection import get_connected_client
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.utils.error_handling import log_and_build_error


async def search_contacts_telegram(
    query: str, limit: int = 20
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Search contacts using Telegram's native contacts.SearchRequest method.

    This method searches through your contacts and global Telegram users
    using Telegram's built-in search functionality.

    Args:
        query: The search query (name, username, or phone number)
        limit: Maximum number of results to return

    Returns:
        List of matching contacts with their information, or error dict if operation fails
    """
    params = {"query": query, "limit": limit, "query_length": len(query)}

    try:
        client = await get_connected_client()

        # Use Telegram's native contact search
        result = await client(SearchRequest(q=query, limit=limit))

        matches = []

        # Process users found in contacts
        if hasattr(result, "users") and result.users:
            for user in result.users:
                user_info = build_entity_dict(user)
                matches.append(
                    {
                        "chat_id": user.id,
                        "title": f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip(),
                        "type": "User",
                        "username": getattr(user, "username", None),
                        "phone": getattr(user, "phone", None),
                        "match_type": "telegram_search",
                        "user_info": user_info,
                    }
                )

        # Process chats found in contacts
        if hasattr(result, "chats") and result.chats:
            for chat in result.chats:
                chat_info = build_entity_dict(chat)
                matches.append(
                    {
                        "chat_id": chat.id,
                        "title": getattr(chat, "title", ""),
                        "type": chat.__class__.__name__,
                        "username": getattr(chat, "username", None),
                        "match_type": "telegram_search",
                        "chat_info": chat_info,
                    }
                )

        logger.info(
            f"Found {len(matches)} contacts using Telegram search for '{query}'"
        )

        # If no contacts found, return error instead of empty list for consistency
        if not matches:
            return log_and_build_error(
                operation="search_contacts",
                error_message=f"No contacts found matching query '{query}'",
                params=params,
                exception=ValueError(f"No contacts found matching query '{query}'"),
            )

        return matches

    except Exception as e:
        return log_and_build_error(
            operation="search_contacts",
            error_message=f"Failed to search contacts: {e!s}",
            params=params,
            exception=e,
        )


async def get_contact_info(chat_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific contact.

    Args:
        chat_id: The chat ID of the contact

    Returns:
        Contact information or error message if not found
    """
    params = {"chat_id": chat_id}

    try:
        entity = await get_entity_by_id(chat_id)

        if not entity:
            return log_and_build_error(
                operation="get_contact_details",
                error_message=f"Contact with ID '{chat_id}' not found",
                params=params,
                exception=ValueError(f"Contact with ID '{chat_id}' not found"),
            )

        return build_entity_dict(entity)

    except Exception as e:
        return log_and_build_error(
            operation="get_contact_details",
            error_message=f"Failed to get contact info for '{chat_id}': {e!s}",
            params=params,
            exception=e,
        )
