"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

import asyncio
from typing import Any

from loguru import logger
from telethon.tl.functions.contacts import SearchRequest

from src.client.connection import get_connected_client
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.utils.error_handling import log_and_build_error


async def search_contacts_native(
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

        # combine users and chats, providing they may not be present
        if hasattr(result, "users") and result.users:
            matches.extend(result.users)
        if hasattr(result, "chats") and result.chats:
            matches.extend(result.chats)

        for match in matches:
            info = build_entity_dict(match)
            if not info:
                continue
            matches.append(info)

        logger.info(f"Found {len(matches)} matches using Telegram search for '{query}'")

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


async def find_chats_impl(
    query: str, limit: int = 20
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    High-level contacts search with support for comma-separated multi-term queries.

    - Splits the input by commas
    - Runs per-term searches concurrently via search_contacts_telegram
    - Merges and deduplicates results by chat_id
    - Truncates to the requested limit

    Args:
        query: Single term or comma-separated terms
        limit: Maximum number of results to return

    Returns:
        List of matching contacts or error dict
    """
    terms = [t.strip() for t in (query or "").split(",") if t.strip()]

    # Single term: delegate directly
    if len(terms) <= 1:
        return await search_contacts_native(query, limit)

    try:
        tasks = [search_contacts_native(term, limit) for term in terms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[dict[str, Any]] = []
        seen_ids: set[Any] = set()

        for res in results:
            if isinstance(res, list):
                for item in res:
                    entity_id = item.get("id") if isinstance(item, dict) else None
                    if entity_id is None or entity_id in seen_ids:
                        continue
                    seen_ids.add(entity_id)
                    merged.append(item)
            # ignore error dicts and exceptions to allow partial success
            if len(merged) >= limit:
                break

        return merged[:limit]
    except Exception as e:
        return log_and_build_error(
            operation="search_contacts_multi",
            error_message=f"Failed multi-term contact search: {e!s}",
            params={"query": query, "limit": limit},
            exception=e,
        )


# Backwards-compatible alias for previous name
search_contacts = find_chats_impl

# Backwards-compatible alias (do not remove without updating all imports)
search_contacts_telegram = search_contacts_native


async def get_chat_info_impl(chat_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific chat (user, group, or channel).

    Args:
        chat_id: The chat identifier (user/chat/channel)

    Returns:
        Chat information or error message if not found
    """
    params = {"chat_id": chat_id}

    try:
        entity = await get_entity_by_id(chat_id)

        if not entity:
            return log_and_build_error(
                operation="get_chat_info",
                error_message=f"Chat with ID '{chat_id}' not found",
                params=params,
                exception=ValueError(f"Chat with ID '{chat_id}' not found"),
            )

        return build_entity_dict(entity)

    except Exception as e:
        return log_and_build_error(
            operation="get_chat_info",
            error_message=f"Failed to get chat info for '{chat_id}': {e!s}",
            params=params,
            exception=e,
        )


# Backwards-compatible alias
get_chat_info = get_chat_info_impl
