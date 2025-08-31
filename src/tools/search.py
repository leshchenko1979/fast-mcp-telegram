import asyncio
import time
import traceback
from datetime import datetime
from typing import Any

from loguru import logger
from telethon.tl.functions.messages import GetSearchCountersRequest, SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

from src.client.connection import get_connected_client
from src.tools.links import generate_telegram_links
from src.utils.entity import compute_entity_identifier, get_entity_by_id
from src.utils.message_format import build_message_result


async def _get_chat_message_count(chat_id: str) -> int | None:
    """
    Get total message count for a specific chat.
    """
    try:
        client = await get_connected_client()
        entity = await get_entity_by_id(chat_id)
        if not entity:
            return None

        result = await client(
            GetSearchCountersRequest(peer=entity, filters=[InputMessagesFilterEmpty()])
        )

        if hasattr(result, "counters") and result.counters:
            for counter in result.counters:
                if hasattr(counter, "filter") and isinstance(
                    counter.filter, InputMessagesFilterEmpty
                ):
                    return getattr(counter, "count", 0)

        return 0

    except Exception as e:
        logger.warning(f"Error getting search count for chat {chat_id}: {str(e)}")
        return None


def _append_dedup_until_limit(
    collected: list[dict[str, Any]],
    seen_keys: set,
    new_messages: list[dict[str, Any]],
    target_total: int,
) -> None:
    """Append messages into collected with deduplication until target_total is reached.

    Deduplicates by (chat.id, message.id) pair.
    """
    for msg in new_messages:
        key = (msg.get("chat", {}).get("id"), msg.get("id"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        collected.append(msg)
        if len(collected) >= target_total:
            break


def _has_any_media(message) -> bool:
    """Check if message contains any type of media content."""
    if not hasattr(message, "media") or message.media is None:
        return False

    media = message.media
    media_class = media.__class__.__name__

    # Check for all known media types
    return media_class in [
        "MessageMediaPhoto",  # Photos
        "MessageMediaDocument",  # Documents, files, audio, video files
        "MessageMediaAudio",  # Audio files
        "MessageMediaVoice",  # Voice messages
        "MessageMediaVideo",  # Videos
        "MessageMediaWebPage",  # Link previews
        "MessageMediaGeo",  # Location
        "MessageMediaContact",  # Contact cards
        "MessageMediaPoll",  # Polls
        "MessageMediaDice",  # Dice animations
        "MessageMediaVenue",  # Venue/location with name
        "MessageMediaGame",  # Games
        "MessageMediaInvoice",  # Payments/invoices
        "MessageMediaUnsupported",  # Unsupported media types
    ]


def _matches_chat_type(entity, chat_type: str) -> bool:
    """Check if entity matches the specified chat type filter."""
    if not chat_type:
        return True

    entity_class = entity.__class__.__name__
    return (
        (chat_type == "private" and entity_class == "User")
        or (chat_type == "group" and entity_class == "Chat")
        or (chat_type == "channel" and entity_class in ["Channel", "ChannelForbidden"])
    )


async def _process_message_for_results(
    client,
    message,
    chat_entity,
    chat_type: str,
    results: list[dict[str, Any]],
    limit: int,
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


async def _execute_parallel_searches(
    search_tasks: list,
    collected: list[dict[str, Any]],
    seen_keys: set,
    offset: int,
    limit: int,
) -> None:
    """Execute multiple search tasks in parallel and collect results with deduplication."""
    results_lists = await asyncio.gather(*search_tasks)
    for partial in results_lists:
        _append_dedup_until_limit(collected, seen_keys, partial, offset + limit)
        if len(collected) >= (offset + limit):
            break


async def search_messages(
    query: str,
    chat_id: str = None,
    limit: int = 20,
    min_date: str = None,  # ISO format date string
    max_date: str = None,  # ISO format date string
    offset: int = 0,  # Offset for pagination
    chat_type: str = None,  # 'private', 'group', 'channel', or None
    auto_expand_batches: int = 2,  # Maximum additional batches to fetch if not enough filtered results
    include_total_count: bool = False,  # Whether to include total count in response
) -> dict[str, Any]:
    """
    Search for messages in Telegram chats using Telegram's global or per-chat search functionality with pagination, optional chat type filtering, and auto-expansion for filtered results.

    Args:
        query: Search query string (use comma-separated terms for multiple queries). For per-chat, may be empty; for global, must not be empty. Results are merged and deduplicated.
        chat_id: Optional chat ID to search in a specific chat. If not provided, performs a global search.
        limit: Maximum number of results to return
        min_date: Optional minimum date for search results (ISO format string)
        max_date: Optional maximum date for search results (ISO format string)
        offset: Number of messages to skip (for pagination)
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
    # Normalize and validate queries
    queries: list[str] = (
        [q.strip() for q in query.split(",") if q.strip()] if query else []
    )

    if not chat_id:
        if not queries:
            raise ValueError("Search query must not be empty for global search.")

    request_id = f"search_{int(time.time() * 1000)}"
    min_datetime = datetime.fromisoformat(min_date) if min_date else None
    max_datetime = datetime.fromisoformat(max_date) if max_date else None
    logger.debug(
        f"[{request_id}] Starting Telegram search",
        extra={
            "search_params": {
                "query": query,
                "chat_id": chat_id,
                "limit": limit,
                "min_date": min_date,
                "max_date": max_date,
                "offset": offset,
                "chat_type": chat_type,
            }
        },
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
                search_tasks = [
                    _search_chat_messages(
                        client,
                        entity,
                        (q or ""),
                        limit,
                        0,
                        chat_type,
                        auto_expand_batches,
                    )
                    for q in per_chat_queries
                ]
                await _execute_parallel_searches(
                    search_tasks, collected, seen_keys, offset, limit
                )

                if include_total_count:
                    total_count = await _get_chat_message_count(chat_id)

            except Exception as e:
                logger.error(f"Error searching in specific chat: {str(e)}")
                logger.debug(f"Full error details for chat {chat_id}:", exc_info=True)
                raise
        else:
            # Global search across queries (skip empty)
            try:
                search_tasks = [
                    _search_global_messages(
                        client,
                        q,
                        limit,
                        min_datetime,
                        max_datetime,
                        0,
                        chat_type,
                        auto_expand_batches,
                    )
                    for q in queries
                    if q and str(q).strip()
                ]
                await _execute_parallel_searches(
                    search_tasks, collected, seen_keys, offset, limit
                )
            except Exception as e:
                logger.error(f"Error in global search: {e}")
                raise

        # Apply pagination window after deduplication
        window = (
            collected[offset : offset + limit]
            if limit is not None
            else collected[offset:]
        )

        logger.info(
            f"[{request_id}] Found {len(window)} messages matching query: {query}"
        )

        has_more = len(collected) > (offset + len(window))

        response = {"messages": window, "has_more": has_more}

        if total_count is not None:
            response["total_count"] = total_count

        return response
    except Exception as e:
        error_info = {
            "request_id": request_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
            "search_params": {
                "query": query,
                "chat_id": chat_id,
                "limit": limit,
                "min_date": min_date,
                "max_date": max_date,
                "offset": offset,
                "chat_type": chat_type,
            },
        }
        logger.error(f"[{request_id}] Error searching Telegram", extra=error_info)
        raise


async def _search_chat_messages(
    client, entity, query, limit, offset, chat_type, auto_expand_batches
):
    results = []
    count = 0
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0

    while batch_count < max_batches and len(results) < limit:
        batch = []
        async for message in client.iter_messages(
            entity, search=query, offset_id=next_offset_id
        ):
            if not message:
                continue
            if count < offset:
                count += 1
                continue
            batch.append(message)
            if len(batch) >= limit * 2:
                break
        if not batch:
            break

        for message in batch:
            if await _process_message_for_results(
                client, message, entity, chat_type, results, limit
            ):
                if len(results) >= limit:
                    break

        if batch:
            next_offset_id = batch[-1].id
        batch_count += 1

    return results[:limit]


async def _search_global_messages(
    client,
    query,
    limit,
    min_datetime,
    max_datetime,
    offset,
    chat_type,
    auto_expand_batches,
):
    results = []
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0

    while batch_count < max_batches and len(results) < limit:
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
                limit=limit * 2,
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

                if await _process_message_for_results(
                    client, message, chat, chat_type, results, limit
                ):
                    if len(results) >= limit:
                        break
            except Exception as e:
                logger.warning(f"Error processing message: {e}")
                continue

        if result.messages:
            next_offset_id = result.messages[-1].id
        batch_count += 1

    return results[:limit]
