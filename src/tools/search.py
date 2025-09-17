from datetime import datetime
from typing import Any

from loguru import logger
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

from src.client.connection import get_connected_client
from src.tools.links import generate_telegram_links
from src.utils.entity import (
    _get_chat_message_count,
    _matches_chat_type,
    compute_entity_identifier,
    get_entity_by_id,
)
from src.utils.error_handling import (
    add_logging_metadata,
    log_and_build_error,
    sanitize_params_for_logging,
)
from src.utils.helpers import _append_dedup_until_limit
from src.utils.message_format import _has_any_media, build_message_result


async def _process_message_for_results(
    client, message, chat_entity, chat_type: str, results: list[dict[str, Any]]
) -> bool:
    """Process a single message and add it to results if it matches criteria.

    Returns True if the message was added, False otherwise.
    """
    if not message:
        return False

    # Check if message has content (text or any type of media)
    has_content = (hasattr(message, "text") and message.text) or _has_any_media(message)

    if not has_content:
        return False

    if not _matches_chat_type(chat_entity, chat_type):
        return False

    try:
        identifier = compute_entity_identifier(chat_entity)
        links = await generate_telegram_links(identifier, [message.id])
        link = links.get("message_links", [None])[0]
        results.append(await build_message_result(client, message, chat_entity, link))
        return True
    except Exception as e:
        logger.warning(f"Error processing message: {e}")
        return False


async def _execute_parallel_searches_generators(
    generators: list, collected: list[dict[str, Any]], seen_keys: set, limit: int
) -> None:
    """Execute multiple search generators in parallel for memory efficiency.

    Round-robin through generators to balance results and stop early when limit reached.
    """
    active_gens = list(enumerate(generators))

    while active_gens and len(collected) < limit:
        next_active = []

        for i, gen in active_gens:
            try:
                result = await gen.__anext__()
                _append_dedup_until_limit(collected, seen_keys, [result], limit)
                if len(collected) >= limit:
                    break
                next_active.append((i, gen))  # Keep generator active
            except StopAsyncIteration:
                continue  # Generator exhausted
            except Exception as e:
                logger.warning(f"Error in search generator {i}: {e}")
                continue  # Skip errors in individual generators

        active_gens = next_active


async def search_messages_impl(
    query: str,
    chat_id: str | None = None,
    limit: int = 20,
    min_date: str | None = None,  # ISO format date string
    max_date: str | None = None,  # ISO format date string
    chat_type: str | None = None,  # 'private', 'group', 'channel', or None
    auto_expand_batches: int = 1,  # Fewer extra batches to reduce RAM
    include_total_count: bool = False,  # Whether to include total count in response
) -> dict[str, Any]:
    """
    Search for messages in Telegram chats using Telegram's global or per-chat search functionality with optional chat type filtering and auto-expansion for filtered results.

    Args:
        query: Search query string (use comma-separated terms for multiple queries). For per-chat, may be empty; for global, must not be empty. Results are merged and deduplicated.
        chat_id: Optional chat ID to search in a specific chat. If not provided, performs a global search.
        limit: Maximum number of results to return
        min_date: Optional minimum date for search results (ISO format string)
        max_date: Optional maximum date for search results (ISO format string)
        chat_type: Optional filter for chat type ('private', 'group', 'channel')
        auto_expand_batches: Maximum additional batches to fetch if not enough filtered results (default 2)
        include_total_count: Whether to include total count of matching messages in response (default False)

    Returns:
        Dictionary containing:
        - 'messages': List of dictionaries containing message information
        - 'total_count': Total number of matching messages (if include_total_count=True)
        - 'has_more': Boolean indicating if there are more results available

    Note:
        - For per-chat search (chat_id provided), an empty query returns all messages in the specified chat (optionally filtered by date).
        - For global search (no chat_id), query must not be empty.
        - Total count is only available for per-chat searches, not global searches.
    """
    params = {
        "query": query,
        "chat_id": chat_id,
        "limit": limit,
        "min_date": min_date,
        "max_date": max_date,
        "chat_type": chat_type,
        "auto_expand_batches": auto_expand_batches,
        "include_total_count": include_total_count,
        "is_global_search": chat_id is None,
        "has_query": bool(query and query.strip()),
        "has_date_filter": bool(min_date or max_date),
    }

    # Normalize and validate queries
    queries: list[str] = (
        [q.strip() for q in query.split(",") if q.strip()] if query else []
    )

    if not chat_id and not queries:
        return log_and_build_error(
            operation="search_messages",
            error_message="Search query must not be empty for global search",
            params=params,
            exception=ValueError("Search query must not be empty for global search"),
        )
    min_datetime = datetime.fromisoformat(min_date) if min_date else None
    max_datetime = datetime.fromisoformat(max_date) if max_date else None
    safe_params = sanitize_params_for_logging(params)
    enhanced_params = add_logging_metadata(safe_params)
    logger.debug(
        "Starting Telegram search",
        extra={"params": enhanced_params},
    )
    client = await get_connected_client()
    try:
        total_count = None
        collected: list[dict[str, Any]] = []
        seen_keys = set()

        if chat_id:
            # Per-chat search; allow empty queries meaning "all messages"
            try:
                entity = await get_entity_by_id(chat_id)
                if not entity:
                    raise ValueError(f"Could not find chat with ID '{chat_id}'")

                per_chat_queries = queries if queries else [""]
                generators = [
                    _search_chat_messages_generator(
                        client,
                        entity,
                        (q or ""),
                        limit,
                        chat_type,
                        auto_expand_batches,
                    )
                    for q in per_chat_queries
                ]
                await _execute_parallel_searches_generators(
                    generators, collected, seen_keys, limit
                )

                if include_total_count:
                    total_count = await _get_chat_message_count(chat_id)

            except Exception as e:
                return log_and_build_error(
                    operation="search_messages",
                    error_message=f"Failed to search in chat '{chat_id}': {e!s}",
                    params=params,
                    exception=e,
                )
        else:
            # Global search across queries (skip empty)
            try:
                generators = [
                    _search_global_messages_generator(
                        client,
                        q,
                        limit,
                        min_datetime,
                        max_datetime,
                        chat_type,
                        auto_expand_batches,
                    )
                    for q in queries
                    if q and str(q).strip()
                ]
                await _execute_parallel_searches_generators(
                    generators, collected, seen_keys, limit
                )
            except Exception as e:
                return log_and_build_error(
                    operation="search_messages",
                    error_message=f"Failed to perform global search: {e!s}",
                    params=params,
                    exception=e,
                )

        # Return results up to limit
        window = collected[:limit] if limit is not None else collected

        logger.info(f"Found {len(window)} messages matching query: {query}")

        has_more = len(collected) > len(window)

        # If no messages found, return error instead of empty list for consistency
        if not window:
            return log_and_build_error(
                operation="search_messages",
                error_message=f"No messages found matching query '{query}'",
                params=params,
                exception=ValueError(f"No messages found matching query '{query}'"),
            )

        response = {"messages": window, "has_more": has_more}

        if total_count is not None:
            response["total_count"] = total_count

        return response
    except Exception as e:
        return log_and_build_error(
            operation="search_messages",
            error_message=f"Search operation failed: {e!s}",
            params=params,
            exception=e,
        )


async def _search_chat_messages_generator(
    client, entity, query, limit, chat_type, auto_expand_batches
):
    """Async generator version of chat message search for memory efficiency."""
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0
    yielded_count = 0

    while batch_count < max_batches and yielded_count < limit:
        last_id = None
        processed_in_batch = 0
        async for message in client.iter_messages(
            entity, search=query, offset_id=next_offset_id
        ):
            if not message:
                continue
            last_id = getattr(message, "id", None) or last_id
            processed_in_batch += 1

            # Check if message should be yielded
            if not _matches_chat_type(entity, chat_type):
                continue

            has_content = (hasattr(message, "text") and message.text) or _has_any_media(
                message
            )
            if not has_content:
                continue

            try:
                identifier = compute_entity_identifier(entity)
                links = await generate_telegram_links(identifier, [message.id])
                link = links.get("message_links", [None])[0]
                result = await build_message_result(client, message, entity, link)
                yield result
                yielded_count += 1
                if yielded_count >= limit:
                    return
            except Exception as e:
                logger.warning(f"Error processing message: {e}")
                continue

            # Soft cap batch size to avoid RAM spikes
            if processed_in_batch >= max(50, limit):
                break

        if not last_id:
            break

        next_offset_id = last_id
        batch_count += 1


async def _search_chat_messages(
    client, entity, query, limit, chat_type, auto_expand_batches
):
    """Backward compatibility wrapper - collects generator results into list."""
    results = []
    async for result in _search_chat_messages_generator(
        client, entity, query, limit, chat_type, auto_expand_batches
    ):
        results.append(result)
        if len(results) >= limit:
            break
    return results[:limit]


async def _search_global_messages_generator(
    client, query, limit, min_datetime, max_datetime, chat_type, auto_expand_batches
):
    """Async generator version of global message search for memory efficiency."""
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0
    yielded_count = 0

    while batch_count < max_batches and yielded_count < limit:
        offset_id = next_offset_id
        result = await client(
            SearchGlobalRequest(
                q=query,
                filter=InputMessagesFilterEmpty(),
                min_date=min_datetime,
                max_date=max_datetime,
                offset_rate=0,
                offset_peer=InputPeerEmpty(),
                offset_id=offset_id,
                limit=min(limit * 2, 50),  # Cap batch size
            )
        )

        if not hasattr(result, "messages") or not result.messages:
            break

        for message in result.messages:
            try:
                chat = await get_entity_by_id(message.peer_id)
                if not chat:
                    logger.warning(
                        f"Could not get entity for peer_id: {message.peer_id}"
                    )
                    continue

                if not _matches_chat_type(chat, chat_type):
                    continue

                has_content = (
                    hasattr(message, "text") and message.text
                ) or _has_any_media(message)
                if not has_content:
                    continue

                identifier = compute_entity_identifier(chat)
                links = await generate_telegram_links(identifier, [message.id])
                link = links.get("message_links", [None])[0]
                msg_result = await build_message_result(client, message, chat, link)
                yield msg_result
                yielded_count += 1
                if yielded_count >= limit:
                    return
            except Exception as e:
                logger.warning(f"Error processing message: {e}")
                continue

        if result.messages:
            next_offset_id = result.messages[-1].id
        batch_count += 1


async def _search_global_messages(
    client, query, limit, min_datetime, max_datetime, chat_type, auto_expand_batches
):
    """Backward compatibility wrapper - collects generator results into list."""
    results = []
    async for result in _search_global_messages_generator(
        client, query, limit, min_datetime, max_datetime, chat_type, auto_expand_batches
    ):
        results.append(result)
        if len(results) >= limit:
            break
    return results[:limit]
