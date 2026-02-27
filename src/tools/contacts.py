"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

import logging
from typing import Any

from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import GetForumTopicsRequest

from src.client.connection import SessionNotAuthorizedError, get_connected_client
from src.utils.entity import (
    _matches_public_filter,
    build_entity_dict,
    build_entity_dict_enriched,
    get_entity_by_id,
    get_normalized_chat_type,
)
from src.utils.error_handling import handle_telegram_errors, log_and_build_error

logger = logging.getLogger(__name__)


async def search_contacts_native(
    query: str,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
):
    """
    Search contacts using Telegram's native contacts.SearchRequest method via async generator.

    Yields contact dictionaries one by one for memory efficiency.

    Args:
        query: The search query (name, username, or phone number)
        limit: Maximum number of results to return
        chat_type: Optional filter for chat type ("private"|"group"|"channel")
        public: Optional filter for public discoverability (True=with username, False=without username)

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
                if not _matches_public_filter(user, public):
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
                if not _matches_public_filter(chat, public):
                    continue
                info = build_entity_dict(chat)
                if info:
                    yield info
                    count += 1

    except SessionNotAuthorizedError as e:
        # For async generators, we raise instead of yielding error dict
        raise RuntimeError(
            "Session not authorized. Please authenticate your Telegram session first."
        ) from e
    except Exception as e:
        # For async generators, we raise instead of yielding error dict
        raise RuntimeError(f"Failed to search contacts: {e!s}") from e


@handle_telegram_errors(operation="search_contacts")
async def _search_contacts_as_list(
    query: str,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Wrapper to collect generator results into a list for backward compatibility."""
    results = []
    params = {
        "query": query,
        "limit": limit,
        "query_length": len(query),
        "chat_type": chat_type,
        "public": public,
    }

    async for item in search_contacts_native(query, limit, chat_type, public):
        results.append(item)

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
    query: str,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
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
        public: Optional filter for public discoverability (True=with username, False=without username, None=no filter). Never applies to private chats.

    Returns:
        List of matching contacts or error dict
    """

    terms = [t.strip() for t in (query or "").split(",") if t.strip()]

    # Single term: use backward-compatible wrapper
    if len(terms) <= 1:
        result = await _search_contacts_as_list(query, limit, chat_type, public)
        if isinstance(result, list):
            return {"chats": result}
        return result  # Error case

    try:
        # Start all generators
        generators = [
            search_contacts_native(term, limit, chat_type, public) for term in terms
        ]

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

        return {"chats": merged[:limit]}
    except Exception as e:
        return log_and_build_error(
            operation="search_contacts_multi",
            error_message=f"Failed multi-term contact search: {e!s}",
            params={
                "query": query,
                "limit": limit,
                "chat_type": chat_type,
                "public": public,
            },
            exception=e,
        )


# Backwards-compatible alias for previous name
search_contacts = find_chats_impl

# Backwards-compatible alias (do not remove without updating all imports)
search_contacts_telegram = search_contacts_native


async def _list_forum_topics(entity, limit: int = 20) -> dict[str, Any]:
    """Return compact forum topics list for forum-enabled chats."""
    try:
        requested_limit = int(limit) if limit is not None else 20
    except (TypeError, ValueError):
        requested_limit = 20
    requested_limit = max(1, min(requested_limit, 100))

    # Overfetch by one where possible. At API cap (100) we use a follow-up probe.
    fetch_limit = min(requested_limit + 1, 100)

    client = await get_connected_client()

    result = await client(
        GetForumTopicsRequest(
            peer=entity,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=fetch_limit,
            q="",
        )
    )

    raw_topics = getattr(result, "topics", []) or []
    has_more = False

    # Normal case: overfetch worked (requested_limit < 100).
    if fetch_limit > requested_limit:
        has_more = len(raw_topics) > requested_limit
    # Cap case: requested_limit == 100, cannot overfetch, do probe for next page.
    elif len(raw_topics) >= requested_limit:
        last_topic_id = getattr(raw_topics[-1], "id", None) if raw_topics else None
        if last_topic_id is not None:
            probe = await client(
                GetForumTopicsRequest(
                    peer=entity,
                    offset_date=None,
                    offset_id=0,
                    offset_topic=last_topic_id,
                    limit=1,
                    q="",
                )
            )
            probe_topics = getattr(probe, "topics", []) or []
            has_more = len(probe_topics) > 0

    topics = []
    for topic in raw_topics[:requested_limit]:
        topic_id = getattr(topic, "id", None)
        title = getattr(topic, "title", None)
        if topic_id is None or title is None:
            continue
        topics.append({"topic_id": topic_id, "title": title})

    return {"topics": topics, "has_more": has_more}


@handle_telegram_errors(operation="get_chat_info")
async def get_chat_info_impl(chat_id: str, topics_limit: int = 20) -> dict[str, Any]:
    """
    Get detailed information about a specific chat (user, group, or channel).

    Args:
        chat_id: The chat identifier (user/chat/channel)
        topics_limit: Max topics to include for forum-enabled chats

    Returns:
        Chat information or error message if not found
    """
    params = {"chat_id": chat_id, "topics_limit": topics_limit}

    entity = await get_entity_by_id(chat_id)

    if not entity:
        not_found_msg = f"Chat with ID '{chat_id}' not found"
        return log_and_build_error(
            operation="get_chat_info",
            error_message=not_found_msg,
            params=params,
            exception=ValueError(not_found_msg),
        )

    info = await build_entity_dict_enriched(entity)

    # Add topics list only for forum-enabled chats.
    if info and info.get("is_forum"):
        try:
            topics_result = await _list_forum_topics(entity, topics_limit)
            info["topics"] = topics_result["topics"]
            info["topics_has_more"] = topics_result["has_more"]
        except Exception as e:
            logger.debug(f"Failed to fetch forum topics for {chat_id}: {e}")

    return info


# Backwards-compatible alias
get_chat_info = get_chat_info_impl
