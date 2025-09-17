"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

from typing import Any

from loguru import logger
from telethon.tl.functions.contacts import SearchRequest

from src.client.connection import get_connected_client
from src.utils.entity import (
    build_entity_dict,
    build_entity_dict_enriched,
    get_entity_by_id,
    get_normalized_chat_type,
)
from src.utils.error_handling import log_and_build_error


async def search_contacts_native(
    query: str, limit: int = 20, chat_type: str | None = None
):
    """
    Search contacts using Telegram's native contacts.SearchRequest method via async generator.

    Yields contact dictionaries one by one for memory efficiency.

    Args:
        query: The search query (name, username, or phone number)
        limit: Maximum number of results to return

    Yields:
        Contact dictionaries one by one
    """
    try:
        client = await get_connected_client()
        result = await client(SearchRequest(q=query, limit=limit))

        count = 0

        # Process users
        if hasattr(result, "users") and result.users:
            for user in result.users:
                if count >= limit:
                    break
                if chat_type and get_normalized_chat_type(user) != chat_type:
                    continue
                info = build_entity_dict(user)
                if info:
                    yield info
                    count += 1

        # Process chats
        if hasattr(result, "chats") and result.chats and count < limit:
            for chat in result.chats:
                if count >= limit:
                    break
                if chat_type and get_normalized_chat_type(chat) != chat_type:
                    continue
                info = build_entity_dict(chat)
                if info:
                    yield info
                    count += 1

    except Exception as e:
        # For async generators, we raise instead of yielding error dict
        raise RuntimeError(f"Failed to search contacts: {e!s}") from e


async def _search_contacts_as_list(
    query: str, limit: int = 20, chat_type: str | None = None
) -> list[dict[str, Any]] | dict[str, Any]:
    """Wrapper to collect generator results into a list for backward compatibility."""
    results = []
    params = {
        "query": query,
        "limit": limit,
        "query_length": len(query),
        "chat_type": chat_type,
    }

    try:
        async for item in search_contacts_native(query, limit, chat_type):
            results.append(item)
    except Exception as e:
        return log_and_build_error(
            operation="search_contacts",
            error_message=f"Failed to search contacts: {e!s}",
            params=params,
            exception=e,
        )

    if not results:
        return log_and_build_error(
            operation="search_contacts",
            error_message=f"No contacts found matching query '{query}'",
            params=params,
            exception=ValueError(f"No contacts found matching query '{query}'"),
        )

    logger.info(f"Found {len(results)} contacts using Telegram search for '{query}'")
    return results


async def find_chats_impl(
    query: str, limit: int = 20, chat_type: str | None = None
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
        chat_type: Optional filter ("private"|"group"|"channel")

    Returns:
        List of matching contacts or error dict
    """
    terms = [t.strip() for t in (query or "").split(",") if t.strip()]

    # Single term: use backward-compatible wrapper
    if len(terms) <= 1:
        return await _search_contacts_as_list(query, limit, chat_type)

    try:
        # Start all generators
        generators = [search_contacts_native(term, limit, chat_type) for term in terms]

        merged: list[dict[str, Any]] = []
        seen_ids: set[Any] = set()

        # Round-robin through generators to balance results
        active_gens = list(enumerate(generators))

        while active_gens and len(merged) < limit:
            next_active = []

            for i, gen in active_gens:
                try:
                    item = await gen.__anext__()

                    entity_id = item.get("id") if isinstance(item, dict) else None
                    if entity_id and entity_id not in seen_ids:
                        seen_ids.add(entity_id)
                        merged.append(item)
                        if len(merged) >= limit:
                            break

                    next_active.append((i, gen))  # Keep generator active

                except StopAsyncIteration:
                    continue  # Generator exhausted
                except Exception:
                    continue  # Skip errors in individual generators

            active_gens = next_active

        return merged[:limit]
    except Exception as e:
        return log_and_build_error(
            operation="search_contacts_multi",
            error_message=f"Failed multi-term contact search: {e!s}",
            params={"query": query, "limit": limit, "chat_type": chat_type},
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

        # Return enriched info with counts and about/bio when applicable
        return await build_entity_dict_enriched(entity)

    except Exception as e:
        return log_and_build_error(
            operation="get_chat_info",
            error_message=f"Failed to get chat info for '{chat_id}': {e!s}",
            params=params,
            exception=e,
        )


# Backwards-compatible alias
get_chat_info = get_chat_info_impl
