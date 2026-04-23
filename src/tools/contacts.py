"""
Contact resolution utilities for the Telegram MCP server.
Provides tools to help language models find chat IDs for specific contacts.
"""

import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import GetForumTopicsRequest, GetPeerDialogsRequest
from telethon.tl.types import Channel as TelethonChannel
from telethon.tl.types import Chat as TelethonChat
from telethon.tl.types import User as TelethonUser

from src.client.connection import (
    SessionNotAuthorizedError,
    TelegramTransportError,
    get_connected_client,
)
from src.utils.entity import (
    _matches_chat_type,
    _matches_public_filter,
    build_dialog_entity_dict,
    build_entity_dict,
    build_entity_dict_enriched,
    get_dialog_filters,
    get_entity_by_id,
)
from src.utils.error_handling import log_and_build_error

logger = logging.getLogger(__name__)

FLAG_MATCH_MAX_DIALOGS = 500
GET_PEER_DIALOGS_CHUNK_SIZE = 50
AVAILABLE_FILTERS_MAX_SHOW = 10


def _normalize_filter_name(name: str | None) -> str:
    """Normalize filter names for comparison: trim and collapse whitespace, lowercase."""
    if not name:
        return ""
    return " ".join(name.split()).lower()


async def _get_filter_by_name(client, filter_name: str) -> dict | None:
    """Find filter by name (string). Returns full filter dict or None."""
    filters = await get_dialog_filters(client)
    normalized = _normalize_filter_name(filter_name)
    return next(
        (
            f
            for f in filters
            if _normalize_filter_name(f.get("title", "")) == normalized
        ),
        None,
    )


def _filter_matches_flags(entity, dialog, filter_dict: dict) -> bool:
    """Check if entity matches filter flags.

    filter_dict contains: contacts, non_contacts, groups, broadcasts, bots,
    exclude_muted, exclude_read, exclude_archived (from filter's flags)

    Note: exclude_muted/exclude_read/exclude_archived require dialog object,
    not just entity. entity param is the Chat/User/Channel, dialog is the Dialog object.
    """
    is_user = isinstance(entity, TelethonUser)
    is_chat = isinstance(entity, TelethonChat)
    is_channel = isinstance(entity, TelethonChannel)

    # Handle contacts AND non_contacts = all users (no contact filter)
    contacts_flag = filter_dict.get("contacts", False)
    non_contacts_flag = filter_dict.get("non_contacts", False)

    if contacts_flag and non_contacts_flag:
        pass  # include all users, skip contact status check
    elif (
        contacts_flag
        and not (
            is_user
            and (
                getattr(entity, "contact", False)
                or getattr(entity, "mutual_contact", False)
            )
        )
    ) or (
        non_contacts_flag
        and not (
            is_user
            and not getattr(entity, "contact", False)
            and not getattr(entity, "mutual_contact", False)
        )
    ):
        return False

    # groups=True → include supergroups (megagroup - Channel with megagroup=True)
    if filter_dict.get("groups") and not (
        is_chat or (is_channel and getattr(entity, "megagroup", False))
    ):
        return False
    # broadcasts=True → include channels
    if filter_dict.get("broadcasts") and not is_channel:
        return False
    # bots=True → include bots
    if filter_dict.get("bots") and (
        not is_user or not getattr(entity, "bot", False)
    ):
        return False

    # Exclude filters
    now = datetime.now(UTC).timestamp()
    mute_until = getattr(getattr(dialog, "notify_settings", None) or {}, "mute_until", 0) or 0
    if filter_dict.get("exclude_muted") and mute_until > now:
        return False
    return (
        False
        if filter_dict.get("exclude_read")
        and getattr(dialog, "unread_count", 0) == 0
        else not filter_dict.get("exclude_archived")
        or getattr(dialog, "folder_id", None) != 1
    )


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

    except SessionNotAuthorizedError:
        raise
    except TelegramTransportError:
        raise
    except Exception as e:
        # For async generators, we raise instead of yielding error dict
        raise RuntimeError(f"Failed to search contacts: {e!s}") from e


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
    filter: str | None = None,
) -> dict[str, Any]:
    """
    High-level contacts search with support for comma-separated multi-term queries.

    When min_date or max_date is provided, uses dialog-based search with last_activity_date.
    Otherwise, uses global Telegram search (no last_activity_date).

    Args:
        query: Single term or comma-separated terms (optional for date-based searches)
        limit: Maximum number of results to return
        chat_type: Optional filter ("private"|"group"|"channel")
        public: Optional filter for public discoverability
        min_date: Minimum last activity date filter (ISO format, e.g. "2024-01-01" or "2024-01-01T14:30:00")
        max_date: Maximum last activity date filter (ISO format, e.g. "2024-12-31" or "2024-12-31T23:59:59")
        filter: Filter by dialog filter name (str). When filter has include_peers,
                date parameters (min_date/max_date) are ignored.

    Returns:
        Dict with "chats" key containing list of matches, or standardized error dict

    Raises:
        ValueError: For invalid parameter combinations (e.g., empty query without date/filter)
    """
    has_date_or_filter = (
        min_date is not None or max_date is not None or filter is not None
    )

    params = {
        "query": query,
        "limit": limit,
        "chat_type": chat_type,
        "public": public,
        "min_date": min_date,
        "max_date": max_date,
        "filter": filter,
    }

    # Validate: global search requires non-empty query
    if not has_date_or_filter and (
        not query or (isinstance(query, str) and not query.strip())
    ):
        return log_and_build_error(
            operation="find_chats",
            error_message=(
                "query parameter is required for global Telegram search. "
                "Telegram's global search requires a non-empty search term (name, username, or phone). "
                "To browse chats in a specific folder, use filter parameter. "
                "To find chats active in a date range, use min_date/max_date filters. "
                f"Received: query={query!r} with no date/filter."
            ),
            params=params,
            exception=ValueError("Empty query not allowed without date/filter"),
        )

    # Validate limit
    if limit <= 0:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"limit must be positive, got {limit}",
            params=params,
            exception=ValueError(f"Invalid limit: {limit}"),
        )

    if filter is not None:
        return await _find_chats_by_filter(
            query=query,
            limit=limit,
            chat_type=chat_type,
            public=public,
            min_date=min_date,
            max_date=max_date,
            filter_name=filter,
        )

    if has_date_or_filter:
        return await _find_chats_by_dialogs(
            query=query,
            limit=limit,
            chat_type=chat_type,
            public=public,
            min_date=min_date,
            max_date=max_date,
            folder_id=None,
        )

    result = await _find_chats_global(
        query=query,
        limit=limit,
        chat_type=chat_type,
        public=public,
    )
    return {"chats": result} if isinstance(result, list) else result


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
    folder_id: int | None = None,
) -> dict[str, Any]:
    """Dialog-based search with date filtering and last_activity_date."""
    params = {
        "query": query,
        "limit": limit,
        "chat_type": chat_type,
        "public": public,
        "min_date": min_date,
        "max_date": max_date,
        "folder_id": folder_id,
    }

    min_date_dt = _parse_iso_date(min_date)
    if min_date is not None and min_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid min_date format: '{min_date}'. Use ISO format (e.g., '2024-01-01')",
            params=params,
            exception=ValueError(f"Invalid min_date format: '{min_date}'"),
        )

    max_date_dt = _parse_iso_date(max_date)
    if max_date is not None and max_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid max_date format: '{max_date}'. Use ISO format (e.g., '2024-12-31')",
            params=params,
            exception=ValueError(f"Invalid max_date format: '{max_date}'"),
        )

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
        params=params,
        exception=ValueError(f"No chats found {query_str}{date_str}"),
    )


async def _find_chats_by_filter(
    query: str | None,
    limit: int,
    chat_type: str | None,
    public: bool | None,
    min_date: str | None,
    max_date: str | None,
    filter_name: str,
) -> dict[str, Any]:
    """Filter-based search using dialog filter definition."""
    params = {
        "query": query,
        "limit": limit,
        "chat_type": chat_type,
        "public": public,
        "min_date": min_date,
        "max_date": max_date,
        "filter": filter_name,
    }

    client = await get_connected_client()
    filter_dict = await _get_filter_by_name(client, filter_name)

    if not filter_dict:
        all_filters = await get_dialog_filters(client)
        available = "; ".join(
            f'"{f.get("title", "")}"' for f in all_filters[:AVAILABLE_FILTERS_MAX_SHOW]
        )
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Filter '{filter_name}' not found. Available: [{available}]",
            params=params,
            exception=ValueError(f"Filter '{filter_name}' not found"),
        )

    include_peers = filter_dict.get("include_peers", []) or []
    has_flags = any(
        filter_dict.get(flag)
        for flag in (
            "contacts",
            "non_contacts",
            "groups",
            "broadcasts",
            "bots",
            "exclude_muted",
            "exclude_read",
            "exclude_archived",
        )
    )

    if include_peers:
        return await _find_chats_by_include_peers(
            client,
            filter_dict,
            query,
            limit,
            chat_type,
            public,
            min_date,
            max_date,
        )
    if has_flags:
        return await _find_chats_by_filter_flags(
            client,
            filter_dict,
            query,
            limit,
            chat_type,
            public,
            min_date,
            max_date,
        )
    # Filter exists but has no include_peers and no active flags
    return {"chats": []}


async def _find_chats_by_include_peers(
    client,
    filter_dict: dict,
    query: str | None,
    limit: int,
    chat_type: str | None,
    public: bool | None,
    min_date: str | None,
    max_date: str | None,
) -> dict[str, Any]:
    """Handle filter with explicit include_peers using GetPeerDialogsRequest."""
    include_peers = filter_dict.get("include_peers", []) or []
    exclude_peers = filter_dict.get("exclude_peers", []) or []

    # Resolve include_peers InputPeers → actual entities
    ordered_peer_ids: list[int] = []
    peer_entity_map: dict[int, dict] = {}

    for inp_peer in include_peers:
        try:
            entity = await client.get_entity(inp_peer)
            eid = getattr(entity, "id", None)
            if eid is None:
                continue
            if eid in ordered_peer_ids:
                continue
            entity_dict = build_entity_dict(entity)
            if not entity_dict:
                continue
            ordered_peer_ids.append(eid)
            peer_entity_map[eid] = entity_dict
        except Exception as e:
            logger.debug(f"Failed to resolve include_peer {inp_peer}: {e}")
            continue

    # Apply exclude_peers
    for inp_peer in exclude_peers:
        try:
            entity = await client.get_entity(inp_peer)
            eid = getattr(entity, "id", None)
            if eid and eid in ordered_peer_ids:
                ordered_peer_ids.remove(eid)
                peer_entity_map.pop(eid, None)
        except Exception as e:
            logger.debug(f"Failed to resolve exclude_peer {inp_peer}: {e}")

    # If filter has flags too, add flag-matching dialogs
    has_flags = any(
        filter_dict.get(flag)
        for flag in (
            "contacts",
            "non_contacts",
            "groups",
            "broadcasts",
            "bots",
            "exclude_muted",
            "exclude_read",
            "exclude_archived",
        )
    )
    if has_flags:
        async for dialog in client.iter_dialogs(
            limit=min(limit * 10, FLAG_MATCH_MAX_DIALOGS),
        ):
            entity = getattr(dialog, "entity", None)
            if not entity:
                continue
            eid = getattr(entity, "id", None)
            if (
                eid
                and eid not in ordered_peer_ids
                and _filter_matches_flags(entity, dialog, filter_dict)
                and (entity_dict := build_entity_dict(entity))
            ):
                ordered_peer_ids.append(eid)
                peer_entity_map[eid] = entity_dict

    if not ordered_peer_ids:
        return {"chats": []}

    # Build InputPeers and batch call GetPeerDialogsRequest
    last_activity_map: dict[int, str] = {}
    for chunk_start in range(0, len(ordered_peer_ids), GET_PEER_DIALOGS_CHUNK_SIZE):
        chunk_ids = ordered_peer_ids[
            chunk_start : chunk_start + GET_PEER_DIALOGS_CHUNK_SIZE
        ]

        input_peers = []
        for pid in chunk_ids:
            ent = peer_entity_map.get(pid)
            if not ent:
                continue
            ent_type = ent.get("type")
            if ent_type == "channel":
                from telethon.tl.types import InputPeerChannel

                input_peers.append(
                    InputPeerChannel(
                        channel_id=pid, access_hash=ent.get("access_hash", 0) or 0
                    )
                )
            elif ent_type == "group":
                from telethon.tl.types import InputPeerChat

                input_peers.append(InputPeerChat(chat_id=pid))
            elif ent_type in ("private", "bot"):
                from telethon.tl.types import InputPeerUser

                input_peers.append(
                    InputPeerUser(
                        user_id=pid, access_hash=ent.get("access_hash", 0) or 0
                    )
                )

        if not input_peers:
            continue

        try:
            result = await client(GetPeerDialogsRequest(peers=input_peers))
            for d, m in zip(result.dialogs, result.messages, strict=True):
                # Extract peer_id from message.peer
                peer_id = _extract_peer_id(d.peer)
                if peer_id and m.date:
                    last_activity_map[peer_id] = m.date.isoformat()
        except Exception as e:
            logger.debug(f"GetPeerDialogsRequest failed: {e}")

    # Build result with filtering
    results = []
    for pid in ordered_peer_ids:
        ent_dict = peer_entity_map.get(pid)
        if not ent_dict:
            continue

        # Apply chat_type filter
        if chat_type and not _matches_chat_type_from_dict(ent_dict, chat_type):
            continue

        # Apply public filter
        if public is not None and not _matches_public_filter_from_dict(
            ent_dict, public
        ):
            continue

        # Apply query filter
        if query:
            query_lower = query.lower().strip()
            if query_lower and not _matches_dict_query(ent_dict, query_lower):
                continue

        result_dict = dict(ent_dict)
        if pid in last_activity_map:
            result_dict["last_activity_date"] = last_activity_map[pid]

        results.append(result_dict)
        if len(results) >= limit:
            break

    return {"chats": results}


def _extract_peer_id(peer) -> int | None:
    """Extract numeric peer ID from PeerUser/PeerChannel/PeerChat."""
    if hasattr(peer, "user_id"):
        return peer.user_id
    if hasattr(peer, "channel_id"):
        return peer.channel_id
    return peer.chat_id if hasattr(peer, "chat_id") else None


def _matches_chat_type_from_dict(entity_dict: dict, chat_type: str) -> bool:
    """Check if entity dict matches chat_type filter."""
    if not chat_type:
        return True
    chat_types = [ct.strip().lower() for ct in chat_type.split(",") if ct.strip()]
    valid_types = {"private", "bot", "group", "channel"}
    if any(ct not in valid_types for ct in chat_types):
        return False
    entity_type = entity_dict.get("type")
    return entity_type in chat_types


def _matches_public_filter_from_dict(entity_dict: dict, public: bool | None) -> bool:
    """Check if entity dict matches public filter."""
    if entity_dict.get("type") in ("private", "bot"):
        return True
    if public is None:
        return True
    has_username = bool(entity_dict.get("username"))
    return has_username if public else not has_username


def _matches_dict_query(entity_dict: dict, query_lower: str) -> bool:
    """Check if entity dict matches query string."""
    title = entity_dict.get("title", "") or ""
    username = entity_dict.get("username", "") or ""
    first_name = entity_dict.get("first_name", "") or ""
    last_name = entity_dict.get("last_name", "") or ""
    searchable = " ".join(
        part for part in (title, username, first_name, last_name) if part
    ).lower()
    return query_lower in searchable


async def _find_chats_by_filter_flags(
    client,
    filter_dict: dict,
    query: str | None,
    limit: int,
    chat_type: str | None,
    public: bool | None,
    min_date: str | None,
    max_date: str | None,
) -> dict[str, Any]:
    """Handle flag-based filter by iterating all dialogs and matching flags."""
    min_date_dt = _parse_iso_date(min_date)
    if min_date is not None and min_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid min_date format: '{min_date}'. Use ISO format (e.g., '2024-01-01')",
            params={},
            exception=ValueError(f"Invalid min_date format: '{min_date}'"),
        )

    max_date_dt = _parse_iso_date(max_date)
    if max_date is not None and max_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid max_date format: '{max_date}'. Use ISO format (e.g., '2024-12-31')",
            params={},
            exception=ValueError(f"Invalid max_date format: '{max_date}'"),
        )

    results = []
    async for dialog in client.iter_dialogs(
        limit=min(limit * 10, FLAG_MATCH_MAX_DIALOGS)
    ):
        entity = getattr(dialog, "entity", None)
        if not entity:
            continue

        if not _filter_matches_flags(entity, dialog, filter_dict):
            continue

        dialog_date = getattr(dialog, "date", None)
        if not await _dialog_in_date_range(
            entity, client, dialog_date, min_date_dt, max_date_dt
        ):
            continue

        if chat_type and not _matches_chat_type(entity, chat_type):
            continue
        if not _matches_public_filter(entity, public):
            continue

        if result := build_dialog_entity_dict(dialog, entity):
            # Apply query filter
            if query:
                query_lower = query.lower().strip()
                if query_lower and not _matches_dialog_query(entity, query_lower):
                    continue
            results.append(result)
            if len(results) >= limit:
                break

    return {"chats": results}


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
    folder_id: int | None = None,
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

    except SessionNotAuthorizedError:
        raise
    except TelegramTransportError:
        raise


async def _list_forum_topics(entity, limit: int = 20) -> dict[str, Any]:
    """Return compact forum topics list for forum-enabled chats."""
    # Clamp to [1, 100]; overfetch by one when not at cap.
    try:
        requested_limit = max(1, min(limit, 100))
    except TypeError:
        requested_limit = 20
    fetch_limit = requested_limit + 1 if requested_limit < 100 else 100

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

    if requested_limit < 100:
        # Overfetch worked — detect overflow by result count.
        has_more = len(raw_topics) > requested_limit
    elif len(raw_topics) >= requested_limit:
        # At API cap (100) — probe for next page.
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
