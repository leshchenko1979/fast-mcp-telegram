"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

import logging
from contextlib import suppress
from datetime import datetime
from typing import Any

from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import GetForumTopicsRequest

from src.client.connection import SessionNotAuthorizedError, get_connected_client
from src.utils.entity import (
    _matches_public_filter,
    build_dialog_entity_dict,
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
                if info := build_entity_dict(user):
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
                if info := build_entity_dict(chat):
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
    query: str | None = None,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    High-level contacts search with support for comma-separated multi-term queries.

    - Splits the input by commas
    - Runs per-term searches concurrently via search_contacts_telegram
    - Merges and deduplicates results by chat_id
    - Truncates to the requested limit

    When min_date or max_date is provided, uses iter_dialogs() which provides
    last_activity_date, but has no native query search (query matching is done client-side).

    Args:
        query: Single term or comma-separated terms (optional for date-based searches)
        limit: Maximum number of results to return
        chat_type: Optional filter ("private"|"group"|"channel")
        public: Optional filter for public discoverability (True=with username, False=without username, None=no filter). Never applies to private chats.
        min_date: Minimum last activity date filter (ISO format "2024-01-01"). When provided, uses dialog-based search with last_activity_date.
        max_date: Maximum last activity date filter (ISO format "2024-12-31"). When provided, uses dialog-based search with last_activity_date.

    Returns:
        List of matching contacts or error dict
    """
    # When date filtering is requested, use dialog-based search
    if min_date is not None or max_date is not None:
        results = []
        async for item in search_dialogs_impl(
            query, limit, chat_type, public, min_date, max_date
        ):
            results.append(item)

        if not results:
            date_desc = []
            if min_date:
                date_desc.append(f"since {min_date}")
            if max_date:
                date_desc.append(f"until {max_date}")
            date_str = " and ".join(date_desc) if date_desc else "with date filter"
            query_str = f"matching '{query}' " if query else ""
            return log_and_build_error(
                operation="find_chats",
                error_message=f"No chats found {query_str}{date_str}",
                params={
                    "query": query,
                    "limit": limit,
                    "chat_type": chat_type,
                    "public": public,
                    "min_date": min_date,
                    "max_date": max_date,
                },
                exception=ValueError(f"No chats found {query_str}{date_str}"),
            )
        return {"chats": results}

    # Original behavior without date filtering
    terms = [t.strip() for t in (query or "").split(",") if t.strip()]

    # Single term: use backward-compatible wrapper
    if len(terms) <= 1:
        result = await _search_contacts_as_list(query, limit, chat_type, public)
        return {"chats": result} if isinstance(result, list) else result
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

                except Exception:
                    continue  # Generator exhausted
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


async def _get_last_message_date(entity) -> str | None:
    """
    Get last message date from chat history as fallback when dialog.date is unavailable.

    Args:
        entity: Telethon entity (User, Chat, or Channel)

    Returns:
        ISO format date string or None if no messages or error
    """
    with suppress(Exception):
        client = await get_connected_client()
        async for msg in client.iter_messages(entity, limit=1):
            if msg and msg.date:
                return msg.date.isoformat()
    return None


async def search_dialogs_impl(
    query: str | None = None,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
):
    """
    Search dialogs using client.iter_dialogs() with optional date filtering.

    Unlike search_contacts_native() which uses Telegram's SearchRequest,
    this function uses iter_dialogs() which provides dialog.date for
    last activity tracking. However, iter_dialogs() has no query parameter,
    so query matching is done client-side against entity display names.

    Note: iter_dialogs() returns dialogs SORTED by recency (most recent first).
    This allows early termination when max_date filter is satisfied.

    Args:
        query: Search query (matched against title, username, first_name, phone). Optional.
        limit: Maximum number of results to return
        chat_type: Optional filter for chat type ("private"|"group"|"channel")
        public: Optional filter for public discoverability
        min_date: Minimum last activity date (ISO format "2024-01-01")
        max_date: Maximum last activity date (ISO format "2024-12-31")

    Yields:
        Contact dictionaries one by one with last_activity_date field
    """
    try:
        client = await get_connected_client()

        # Parse date filters once
        min_date_dt = None
        max_date_dt = None
        if min_date:
            with suppress(ValueError):
                min_date_dt = datetime.fromisoformat(min_date.replace("Z", "+00:00"))
        if max_date:
            with suppress(ValueError):
                max_date_dt = datetime.fromisoformat(max_date.replace("Z", "+00:00"))

        # Normalize query for case-insensitive matching
        query_lower = query.lower().strip() if query else ""

        count = 0
        async for dialog in client.iter_dialogs():
            if count >= limit:
                break

            entity = getattr(dialog, "entity", None)
            if not entity:
                continue

            # Apply query filter first (cheapest non-date filter)
            if query_lower:
                title = getattr(entity, "title", None) or ""
                username = getattr(entity, "username", None) or ""
                first_name = getattr(entity, "first_name", None) or ""
                last_name = getattr(entity, "last_name", None) or ""
                phone = getattr(entity, "phone", None) or ""

                full_name = f"{first_name} {last_name}".strip().lower()
                searchable = (
                    f"{title} {username} {first_name} {full_name} {phone}".lower()
                )

                if query_lower not in searchable:
                    continue

            # Apply date filters (most important for optimization)
            # Dialogs are sorted by recency, so we can break early for max_date
            dialog_date = getattr(dialog, "date", None)
            if dialog_date:
                # max_date early termination: dialogs are sorted newest-first
                # Once dialog.date < max_date, all subsequent dialogs will be older
                if max_date_dt and dialog_date < max_date_dt:
                    break
                # min_date check
                if min_date_dt and dialog_date < min_date_dt:
                    continue
            else:
                # Fallback: only check after basic filters pass
                if fallback_date := await _get_last_message_date(entity):
                    with suppress(ValueError):
                        fallback_dt = datetime.fromisoformat(
                            fallback_date.replace("Z", "+00:00")
                        )
                        # For fallback, we can't break early (not sorted)
                        if min_date_dt and fallback_dt < min_date_dt:
                            continue
                        if max_date_dt and fallback_dt > max_date_dt:
                            continue

            # Apply chat_type and public filters last (after date check)
            if chat_type and get_normalized_chat_type(entity) != chat_type:
                continue

            if not _matches_public_filter(entity, public):
                continue

            # Build result with last_activity_date
            if result := build_dialog_entity_dict(dialog, entity):
                yield result
                count += 1

    except SessionNotAuthorizedError as e:
        raise RuntimeError(
            "Session not authorized. Please authenticate your Telegram session first."
        ) from e
    except Exception as e:
        raise RuntimeError(f"Failed to search dialogs: {e!s}") from e


async def _list_forum_topics(entity, limit: int = 20) -> dict[str, Any]:
    """Return compact forum topics list for forum-enabled chats."""
    try:
        requested_limit = limit if limit is not None else 20
        requested_limit = max(1, min(requested_limit, 100))
    except (TypeError, ValueError):
        requested_limit = 20

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
    if info is None:
        return log_and_build_error(
            operation="get_chat_info",
            error_message="Failed to build entity info",
            params=params,
            exception=ValueError("build_entity_dict_enriched returned None"),
        )

    # Add topics list only for forum-enabled chats.
    if info.get("is_forum"):
        try:
            topics_result = await _list_forum_topics(entity, topics_limit)
            info["topics"] = topics_result["topics"]
            info["topics_has_more"] = topics_result["has_more"]
        except Exception as e:
            logger.debug(f"Failed to fetch forum topics for {chat_id}: {e}")

    return info


# Backwards-compatible alias
get_chat_info = get_chat_info_impl
