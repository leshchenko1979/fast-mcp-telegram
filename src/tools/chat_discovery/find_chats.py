"""find_chats tool implementation: global search, dialogs, and folder filters."""

import asyncio
import logging
from itertools import zip_longest
from typing import Any

from src.client.connection import get_connected_client
from src.utils.datetime_parse import parse_iso_datetime_utc
from src.utils.entity import get_dialog_filters
from src.utils.error_handling import log_and_build_error

from .constants import AVAILABLE_FILTERS_MAX_SHOW
from .contact_search import _search_contacts_as_list
from .dialog_filters import _get_filter_by_name
from .dialog_search import search_dialogs_impl
from .filter_flags import _find_chats_by_filter_flags
from .include_peers import _find_chats_by_include_peers

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CONCURRENT: int = 2


async def find_chats_impl(
    query: str | None = None,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    folder: str | None = None,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
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
        folder: Filter by Telegram folder name (str). Folders are called "dialog filters" internally.
                For include_peers folders, min_date/max_date apply to last-activity from GetPeerDialogs;
                for flag-based folders, dialog last activity uses dialog top-message date (early skip)
                or a history fallback when needed.
        max_concurrent: Maximum concurrent search requests for multi-term queries (default: 2)

    Returns:
        Dict with "chats" key containing list of matches, or standardized error dict

    Raises:
        ValueError: For invalid parameter combinations (e.g., empty query without date/filter)
    """
    has_date_or_folder = (
        min_date is not None or max_date is not None or folder is not None
    )

    params = {
        "query": query,
        "limit": limit,
        "chat_type": chat_type,
        "public": public,
        "min_date": min_date,
        "max_date": max_date,
        "folder": folder,
    }

    if not has_date_or_folder and (
        not query or (isinstance(query, str) and not query.strip())
    ):
        return log_and_build_error(
            operation="find_chats",
            error_message=(
                "query parameter is required for global Telegram search. "
                "Telegram's global search requires a non-empty search term (name, username, or phone). "
                "To browse chats in a specific folder, use folder parameter. "
                "To find chats active in a date range, use min_date/max_date parameters. "
                f"Received: query={query!r} with no date/folder."
            ),
            params=params,
            exception=ValueError("Empty query not allowed without date/folder"),
        )

    if limit <= 0:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"limit must be positive, got {limit}",
            params=params,
            exception=ValueError(f"Invalid limit: {limit}"),
        )

    if folder is not None:
        return await _find_chats_by_filter(
            query=query,
            limit=limit,
            chat_type=chat_type,
            public=public,
            min_date=min_date,
            max_date=max_date,
            filter_name=folder,
        )

    if has_date_or_folder:
        return await _find_chats_by_dialogs(
            query=query,
            limit=limit,
            chat_type=chat_type,
            public=public,
            min_date=min_date,
            max_date=max_date,
            folder_id=None,
        )

    # For group/channel search: contacts.SearchRequest searches USERS by username
    # substring — it does NOT find groups/channels by title. Route to dialog
    # iteration instead, which matches by display name (title/username) via
    # entity_matches_dialog_query(). This is the only Telegram API approach
    # that searches by chat name rather than by message content.
    if chat_type in (
        "group",
        "groups",
        "megagroup",
        "channel",
        "channels",
        "broadcast",
    ):
        return await _find_chats_by_dialogs(
            query=query,
            limit=limit,
            chat_type=chat_type,
            public=public,
            min_date=None,
            max_date=None,
            folder_id=None,
        )

    # No chat_type → combined search: users via contacts.SearchRequest (username-based)
    # + groups/channels via dialog iteration (title-based). Merged round-robin.
    if not chat_type:
        return await _find_chats_combined(
            query=query,
            limit=limit,
            public=public,
        )

    # Private/bot → contacts.SearchRequest only (user search by username).
    result = await _find_chats_global(
        query=query,
        limit=limit,
        chat_type=chat_type,
        public=public,
        max_concurrent=max_concurrent,
    )
    return {"chats": result} if isinstance(result, list) else result


async def _find_chats_global(
    query: str | None,
    limit: int,
    chat_type: str | None,
    public: bool | None,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
) -> dict[str, Any]:
    """
    Global Telegram search without date filtering.

    NOTE: This uses contacts.SearchRequest which searches USERS by username
    substring — it does NOT search groups/channels by title. The chat_type
    parameter here is only a filter on user results, not a different API.
    Use search_dialogs_impl for name-based group/channel search.
    """
    normalized_query = query or ""
    terms: list[str] = [t.strip() for t in normalized_query.split(",") if t.strip()]

    if len(terms) <= 1:
        result = await _search_contacts_as_list(
            normalized_query, limit, chat_type, public
        )
        return {"chats": result} if isinstance(result, list) else result

    return await _find_chats_global_multi_term(
        terms, limit, chat_type, public, max_concurrent
    )


def _normalize_gather_result(
    result: Any,
    source_name: str,
) -> list[dict[str, Any]] | None:
    """Extract chat list from a gather result, or None on error.

    Args:
        result: A result from asyncio.gather(return_exceptions=True).
        source_name: Name of the source for logging.

    Returns:
        List of chat dicts, or None if the result was an error or empty.
    """
    if isinstance(result, BaseException):
        if isinstance(result, (KeyboardInterrupt, SystemExit)):
            raise result
        logger.warning("Combined search: %s failed: %s", source_name, result)
        return None
    if isinstance(result, dict):
        chats = result.get("chats")
        if isinstance(chats, list) and chats:
            return chats
    return None


async def _find_chats_combined(
    query: str | None,
    limit: int,
    public: bool | None,
) -> dict[str, Any]:
    """
    Combined search: contacts.SearchRequest (users) + dialog iteration (groups/channels).

    Runs both searches in parallel via asyncio.gather, then merges results
    round-robin with dedup by entity ID. Gracefully degrades if one path fails
    (e.g., contacts.SearchRequest under FloodWait → dialog-only results).

    Args:
        query: Search query
        limit: Maximum results
        public: Optional public filter

    Returns:
        Dict with 'chats' key, or error dict if both paths failed.
    """
    params = {"query": query, "limit": limit, "public": public}

    try:
        # asyncio.gather(return_exceptions=True) can return BaseException instances
        user_result: dict[str, Any] | BaseException
        dialog_result: dict[str, Any] | BaseException
        user_result, dialog_result = await asyncio.gather(
            _find_chats_global(query=query, limit=limit, chat_type=None, public=public),
            _find_chats_by_dialogs(
                query=query,
                limit=limit,
                chat_type=None,
                public=public,
                min_date=None,
                max_date=None,
                folder_id=None,
            ),
            return_exceptions=True,
        )
    except Exception as e:
        logger.warning("Combined search failed unexpectedly: %s", e)
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Combined search failed: {e}",
            params=params,
            exception=e,
        )

    term_results: list[list[dict[str, Any]]] = []

    user_chats = _normalize_gather_result(user_result, "contact search (users)")
    if user_chats is not None:
        term_results.append(user_chats)

    dialog_chats = _normalize_gather_result(
        dialog_result, "dialog search (groups/channels)"
    )
    if dialog_chats is not None:
        term_results.append(dialog_chats)

    if not term_results:
        if error_result := next(
            (
                r
                for r in (user_result, dialog_result)
                if isinstance(r, dict) and r.get("ok") is False
            ),
            None,
        ):
            return error_result
        return {"chats": []}

    return {"chats": _merge_results_round_robin(term_results, limit)}


async def _gather_term_results(
    terms: list[str],
    limit: int,
    chat_type: str | None,
    public: bool | None,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
) -> tuple[list[list[dict[str, Any]]] | None, tuple[str, ...]]:
    """Execute all term searches with optional concurrency limit.

    Uses asyncio.Semaphore when max_concurrent is set to throttle concurrent requests.
    Falls back to bare asyncio.gather when max_concurrent is None (original behavior).

    Returns (term_results, errors) where term_results is None if no term succeeded.
    """
    semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    async def _run_with_limits(term: str) -> list[dict[str, Any]] | dict[str, Any]:
        """Run a single term search, applying semaphore if configured."""
        coro = _search_contacts_as_list(term, limit, chat_type, public)
        if semaphore:
            async with semaphore:
                return await coro
        return await coro

    tasks = [_run_with_limits(term) for term in terms]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    term_results: list[list[dict[str, Any]]] = []
    errors: list[str] = []
    for term, result in zip(terms, results, strict=True):
        if isinstance(result, Exception):
            errors.append(f"'{term}': {result}")
            logger.warning(
                "Multi-term search failed for '%s': %s",
                term,
                result,
                exc_info=(type(result), result, result.__traceback__),
            )
            continue
        if not isinstance(result, list):
            errors.append(f"'{term}': unexpected result type {type(result).__name__}")
            continue
        term_results.append(result)

    return (term_results, tuple(errors)) if term_results else (None, tuple(errors))


def _merge_results_round_robin(
    term_results: list[list[dict[str, Any]]], limit: int
) -> list[dict[str, Any]]:
    """Round-robin across term result lists with dedup by entity ID."""
    merged: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()

    for items in zip_longest(*term_results):
        if len(merged) >= limit:
            break
        for item in items:
            if item is None:
                continue
            if not isinstance(item, dict):
                continue
            entity_id = item.get("id")
            if entity_id is not None and entity_id not in seen_ids:
                seen_ids.add(entity_id)
                merged.append(item)
                if len(merged) >= limit:
                    break

    return merged[:limit]


async def _find_chats_global_multi_term(
    terms: list[str],
    limit: int,
    chat_type: str | None,
    public: bool | None,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
) -> dict[str, Any]:
    """
    Multi-term global search using parallel gather + round-robin merge.

    Runs all SearchRequest calls concurrently via asyncio.gather(),
    then merges results in round-robin across terms for fairness
    (avoids earlier terms dominating the output).
    Deduplicates by entity ID.
    """
    term_results, failed_terms = await _gather_term_results(
        terms, limit, chat_type, public, max_concurrent
    )
    if term_results is None:
        error_detail = (
            "; ".join(failed_terms) if failed_terms else "no results from any term"
        )
        query_str = ", ".join(terms)
        return log_and_build_error(
            operation="search_contacts_multi",
            error_message=(
                f"No contacts found matching query '{query_str}': {error_detail}"
            ),
            params={
                "query": query_str,
                "limit": limit,
                "chat_type": chat_type,
                "public": public,
            },
            exception=ValueError(f"No contacts found: {error_detail}"),
        )

    return {"chats": _merge_results_round_robin(term_results, limit)}


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

    min_date_dt = parse_iso_datetime_utc(min_date)
    if min_date is not None and min_date_dt is None:
        return log_and_build_error(
            operation="find_chats",
            error_message=f"Invalid min_date format: '{min_date}'. Use ISO format (e.g., '2024-01-01')",
            params=params,
            exception=ValueError(f"Invalid min_date format: '{min_date}'"),
        )

    max_date_dt = parse_iso_datetime_utc(max_date)
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
    return {"chats": []}
