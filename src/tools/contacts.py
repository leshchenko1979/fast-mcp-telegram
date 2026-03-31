"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import GetForumTopicsRequest

from src.client.connection import SessionNotAuthorizedError, get_connected_client
from src.utils.entity import (
    _matches_chat_type,
    _matches_public_filter,
    build_dialog_entity_dict,
    build_entity_dict,
    build_entity_dict_enriched,
    get_available_folders,
    get_entity_by_id,
)
from src.utils.error_handling import handle_telegram_errors, log_and_build_error

logger = logging.getLogger(__name__)


async def _resolve_folder_id(client, folder: int | str) -> int | None:
    """Resolve folder parameter to folder ID.

    Args:
        folder: Folder ID (int) or folder name (str, case-insensitive exact match)

    Returns:
        Folder ID (int) or None if not found

    Note: Folder 0 (default) shows as folder_id=null on Dialog objects,
          so iter_dialogs(folder=0) returns dialogs with folder_id=null
    """
    if isinstance(folder, int):
        return folder

    # String name - load folders and match by title
    folders = await get_available_folders(client)
    folder_lower = folder.lower()
    for f in folders:
        title = f.get("title", "")
        if title and title.lower() == folder_lower:
            return f.get("id")
    return None


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
                if chat_type and not _matches_chat_type(user, chat_type):
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
                if chat_type and not _matches_chat_type(chat, chat_type):
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
        "query_length": len(query) if query else 0,
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
    folder: int | str | None = None,  # NEW
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    High-level contacts search with support for comma-separated multi-term queries.

    When min_date or max_date is provided, uses dialog-based search with last_activity_date.
    Otherwise, uses global Telegram search (no last_activity_date).

    Args:
        query: Single term or comma-separated terms (optional for date-based searches)
        limit: Maximum number of results to return
        chat_type: Optional filter ("private"|"group"|"channel")
        public: Optional filter for public discoverability
        min_date: Minimum last activity date filter (ISO format "2024-01-01")
        max_date: Maximum last activity date filter (ISO format "2024-12-31")
        folder: Filter by folder (int ID or str name)

    Returns:
        Dict with "chats" key containing list of matches, or error dict
    """
    if min_date is not None or max_date is not None or folder is not None:
        return await _find_chats_by_dialogs(
            query=query,
            limit=limit,
            chat_type=chat_type,
            public=public,
            min_date=min_date,
            max_date=max_date,
            folder=folder,  # NEW
        )

    return await _find_chats_global(
        query=query,
        limit=limit,
        chat_type=chat_type,
        public=public,
    )


async def _find_chats_global(
    query: str | None,
    limit: int,
    chat_type: str | None,
    public: bool | None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Global Telegram search without date filtering."""
    normalized_query = query or ""
    terms = [t.strip() for t in normalized_query.split(",") if t.strip()]

    if len(terms) <= 1:
        result = await _search_contacts_as_list(
            normalized_query, limit, chat_type, public
        )
        return {"chats": result} if isinstance(result, list) else result

    try:
        generators = [
            search_contacts_native(term, limit, chat_type, public) for term in terms
        ]

        merged: list[dict[str, Any]] = []
        seen_ids: set[Any] = set()
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
                    next_active.append((i, gen))
                except Exception:
                    continue
            active_gens = next_active

        if not merged:
            return log_and_build_error(
                operation="search_contacts_multi",
                error_message=f"No contacts found matching query '{query}'",
                params={
                    "query": query,
                    "limit": limit,
                    "chat_type": chat_type,
                    "public": public,
                },
                exception=ValueError(f"No contacts found matching query '{query}'"),
            )
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


async def _find_chats_by_dialogs(
    query: str | None,
    limit: int,
    chat_type: str | None,
    public: bool | None,
    min_date: str | None,
    max_date: str | None,
    folder: int | str | None = None,  # NEW
) -> dict[str, Any]:
    """Dialog-based search with date filtering and last_activity_date."""
    # Validate and parse date parameters once to avoid redundant parsing
    min_date_dt = _parse_iso_date(min_date)
    if min_date is not None and min_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid min_date format: '{min_date}'. Use ISO format (e.g., '2024-01-01')",
            params={
                "query": query,
                "limit": limit,
                "chat_type": chat_type,
                "public": public,
                "min_date": min_date,
                "max_date": max_date,
                "folder": folder,
            },
            exception=ValueError(f"Invalid min_date format: '{min_date}'"),
        )

    max_date_dt = _parse_iso_date(max_date)
    if max_date is not None and max_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid max_date format: '{max_date}'. Use ISO format (e.g., '2024-12-31')",
            params={
                "query": query,
                "limit": limit,
                "chat_type": chat_type,
                "public": public,
                "min_date": min_date,
                "max_date": max_date,
                "folder": folder,
            },
            exception=ValueError(f"Invalid max_date format: '{max_date}'"),
        )

    # Resolve folder name to ID if needed
    client = await get_connected_client()
    folder_id = await _resolve_folder_id(client, folder) if folder else None

    results = []
    async for item in search_dialogs_impl(
        query, limit, chat_type, public, min_date_dt, max_date_dt, folder_id
    ):
        results.append(item)

    if results:
        return {"chats": results}

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


# Backwards-compatible alias for previous name
search_contacts = find_chats_impl

# Backwards-compatible alias (do not remove without updating all imports)
search_contacts_telegram = search_contacts_native


def _parse_iso_date(raw: str | None) -> datetime | None:
    """Parse ISO date string to datetime (UTC if timezone not specified), returning None on failure."""
    if not raw:
        return None
    with suppress(ValueError):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        # Ensure timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    return None


def _matches_dialog_query(entity, query_lower: str) -> bool:
    """Check if entity matches query (case-insensitive substring match)."""
    if not query_lower:
        return True

    title = getattr(entity, "title", "") or ""
    username = getattr(entity, "username", "") or ""
    first_name = getattr(entity, "first_name", "") or ""
    last_name = getattr(entity, "last_name", "") or ""
    phone = getattr(entity, "phone", "") or ""

    searchable = " ".join(
        part for part in (title, username, first_name, last_name, phone) if part
    ).lower()
    return query_lower in searchable


async def _dialog_in_date_range(
    entity,
    client,
    dialog_date,
    min_date_dt: datetime | None,
    max_date_dt: datetime | None,
) -> bool:
    """
    Check if dialog is in date range.

    Returns True if dialog should be included, False otherwise.
    """
    if dialog_date:
        # Ensure dialog_date is timezone-aware (assume UTC if naive)
        # Telethon's iter_dialogs() returns naive datetimes
        if dialog_date.tzinfo is None:
            dialog_date = dialog_date.replace(tzinfo=UTC)

        # Too new (above max_date upper bound) - exclude
        if max_date_dt and dialog_date > max_date_dt:
            return False
        # Too old (below min_date lower bound) - exclude
        return not min_date_dt or dialog_date >= min_date_dt

    # Fallback: check message history
    # Skip fallback when no date filtering is active to avoid unnecessary API calls
    if min_date_dt is None and max_date_dt is None:
        return True

    fallback_date = await _get_last_message_date(entity, client)
    if not fallback_date:
        return True

    return (
        (not min_date_dt or fallback_dt >= min_date_dt)
        and (not max_date_dt or fallback_dt <= max_date_dt)
        if (fallback_dt := _parse_iso_date(fallback_date))
        else True
    )


async def _get_last_message_date(entity, client) -> str | None:
    """Get last message date from chat history as fallback when dialog.date is unavailable."""
    with suppress(Exception):
        async for msg in client.iter_messages(entity, limit=1):
            if msg and msg.date:
                return msg.date.isoformat()
    return None


async def search_dialogs_impl(
    query: str | None = None,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
    min_date_dt: datetime | None = None,
    max_date_dt: datetime | None = None,
    folder_id: int | None = None,  # NEW
):
    """
    Search dialogs using client.iter_dialogs() with optional date filtering.

    Unlike search_contacts_native() which uses Telegram's SearchRequest,
    this function uses iter_dialogs() which provides dialog.date for
    last activity tracking. However, iter_dialogs() has no query parameter,
    so query matching is done client-side against entity display names.

    Note: iter_dialogs() may return pinned chats that break chronological ordering,
    so early break optimization is not safe when date filtering.

    Args:
        query: Search query (matched against title, username, first_name, phone). Optional.
        limit: Maximum number of results to return
        chat_type: Optional filter for chat type ("private"|"group"|"channel")
        public: Optional filter for public discoverability
        min_date_dt: Minimum last activity date as parsed datetime (UTC)
        max_date_dt: Maximum last activity date as parsed datetime (UTC)
        folder_id: Filter by folder ID (int). Note: folder 0 (default) shows as null on Dialog objects.

    Yields:
        Contact dictionaries one by one with last_activity_date field
    """
    try:
        client = await get_connected_client()
        query_lower = query.lower().strip() if query else ""

        count = 0
        # Fetch more than limit server-side to account for filtering
        # Since we apply multiple filters (query, chat_type, public, date),
        # we need more dialogs than the requested limit
        async for dialog in client.iter_dialogs(limit=limit * 10, folder=folder_id):  # type: ignore[arg-type]
            if count >= limit:
                break

            entity = getattr(dialog, "entity", None)
            if not entity:
                continue

            # Query filter (cheapest)
            if query_lower and not _matches_dialog_query(entity, query_lower):
                continue

            # Date filter
            dialog_date = getattr(dialog, "date", None)
            if not await _dialog_in_date_range(
                entity, client, dialog_date, min_date_dt, max_date_dt
            ):
                continue

            # Chat type and public filters
            if chat_type and not _matches_chat_type(entity, chat_type):
                continue
            if not _matches_public_filter(entity, public):
                continue

            if result := build_dialog_entity_dict(dialog, entity):
                yield result
                count += 1

    except SessionNotAuthorizedError as e:
        raise RuntimeError(
            "Session not authorized. Please authenticate your Telegram session first."
        ) from e


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
