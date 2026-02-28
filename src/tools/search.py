import logging
from datetime import datetime
from typing import Any

from telethon.tl.functions.messages import GetDiscussionMessageRequest, SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

from src.client.connection import SessionNotAuthorizedError, get_connected_client
from src.tools.links import generate_telegram_links
from src.tools.messages import read_messages_by_ids
from src.utils.entity import (
    _get_chat_message_count,
    _matches_chat_type,
    _matches_public_filter,
    compute_entity_identifier,
    get_entity_by_id,
)
from src.utils.error_handling import (
    add_logging_metadata,
    log_and_build_error,
    sanitize_params_for_logging,
)
from src.utils.helpers import _append_dedup_until_limit
from src.utils.message_format import (
    _has_any_media,
    build_message_result,
    transcribe_voice_messages,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Post Comments / Discussion Threads
# ============================================================================


async def _build_result_for_message(
    client,
    message,
    chat_entity,
) -> dict[str, Any] | None:
    """Build result dict for a single message with link generation.
    
    Returns None if message is invalid or has no content.
    """
    if not message:
        return None

    has_content = (hasattr(message, "text") and message.text) or _has_any_media(
        message
    )
    if not has_content:
        return None

    try:
        identifier = compute_entity_identifier(chat_entity)
        links = await generate_telegram_links(
            identifier, [message.id], resolved_entity=chat_entity
        )
        link = links.get("message_links", [None])[0]
        return await build_message_result(client, message, chat_entity, link)
    except Exception as e:
        logger.warning(f"Error processing message: {e}")
        return None


async def _get_post_discussion_info(
    client, channel_entity, post_id: int
) -> dict[str, Any]:
    """
    Get discussion group information for a channel post.

    Returns dict with:
    - discussion_peer: The discussion chat entity
    - discussion_chat_id: Chat ID of discussion group
    - discussion_msg_id: Root message ID in discussion group
    - discussion_total_count: Total comment count (if available)

    Raises ValueError if post has no discussion enabled.
    """
    try:
        result = await client(
            GetDiscussionMessageRequest(
                peer=channel_entity,
                msg_id=post_id,
            )
        )

        if not result or not hasattr(result, "messages") or not result.messages:
            raise ValueError(f"Post {post_id} has no discussion thread enabled")

        discussion_msg = result.messages[0]
        discussion_peer = getattr(discussion_msg, "peer_id", None)

        if not discussion_peer:
            raise ValueError(f"Post {post_id} has no discussion peer")

        # Get the discussion chat entity
        discussion_entity = await client.get_entity(discussion_peer)
        discussion_chat_id = compute_entity_identifier(discussion_entity)

        # Get total comment count if available
        total_count = getattr(result, "count", None)
        if total_count is None and hasattr(discussion_msg, "replies"):
            total_count = getattr(discussion_msg.replies, "replies", None)

        return {
            "discussion_peer": discussion_entity,
            "discussion_chat_id": discussion_chat_id,
            "discussion_msg_id": discussion_msg.id,
            "discussion_total_count": total_count,
        }

    except Exception as e:
        logger.error(f"Failed to get discussion info for post {post_id}: {e}")
        raise ValueError(
            f"Cannot access discussion for post {post_id}: {e!s}"
        ) from e


async def _fetch_post_comments(
    client,
    channel_entity,
    post_id: int,
    limit: int,
    query: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Fetch comments from a channel post's discussion thread.

    Returns tuple of (messages, metadata):
    - messages: List of comment message dicts
    - metadata: Discussion metadata (chat_id, total_count, etc.)
    """
    # Get discussion information
    discussion_info = await _get_post_discussion_info(client, channel_entity, post_id)

    discussion_entity = discussion_info["discussion_peer"]
    discussion_msg_id = discussion_info["discussion_msg_id"]

    # Fetch comments from discussion thread
    # Comments are replies to the root discussion message
    collected = []
    async for message in client.iter_messages(
        discussion_entity,
        reply_to=discussion_msg_id,
        search=query if query else None,
        limit=limit + 1,  # Fetch one extra to check has_more
    ):
        result = await _build_result_for_message(client, message, discussion_entity)
        if not result:
            continue

        collected.append(result)
        if len(collected) >= limit + 1:
            break

    # Transcribe voice messages if any
    await transcribe_voice_messages(collected[:limit], discussion_entity)

    metadata = {
        "discussion_chat_id": discussion_info["discussion_chat_id"],
        "discussion_total_count": discussion_info["discussion_total_count"],
        "linked_post_id": post_id,
    }

    return collected, metadata


async def _handle_post_comments_mode(
    chat_id: str,
    post_id: int,
    limit: int,
    query: str | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle fetching and returning post comments with unified error handling."""
    client = await get_connected_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            raise ValueError(f"Could not find chat with ID '{chat_id}'")

        collected, metadata = await _fetch_post_comments(
            client, entity, post_id, limit, query
        )

        window = collected[:limit] if limit is not None else collected
        has_more = len(collected) > len(window)

        if not window:
            return log_and_build_error(
                operation="get_messages",
                error_message=f"No comments found for post {post_id}",
                params=params,
                exception=ValueError(f"No comments found for post {post_id}"),
            )

        logger.info(
            f"Retrieved {len(window)} comments from post {post_id} in chat {chat_id}"
        )
        return {
            "messages": window,
            "has_more": has_more,
            **metadata,
        }
    except Exception as e:
        return log_and_build_error(
            operation="get_messages",
            error_message=f"Failed to fetch comments for post {post_id}: {e!s}",
            params=params,
            exception=e,
        )


# ============================================================================
# Search Execution Helpers
# ============================================================================


async def _execute_parallel_searches_generators(
    generators: list, collected: list[dict[str, Any]], seen_keys: set, limit: int
) -> None:
    """Execute multiple search generators in parallel for memory efficiency.

    Round-robin through generators to balance results and collect one extra message to determine has_more.
    """
    active_gens = list(enumerate(generators))
    # Collect one extra message to determine if there are more results
    target_limit = limit + 1

    while active_gens and len(collected) < target_limit:
        next_active = []

        for i, gen in active_gens:
            try:
                result = await gen.__anext__()
                _append_dedup_until_limit(collected, seen_keys, [result], target_limit)
                if len(collected) >= target_limit:
                    break
                next_active.append((i, gen))  # Keep generator active
            except StopAsyncIteration:
                continue  # Generator exhausted
            except Exception as e:
                logger.warning(f"Error in search generator {i}: {e}")
                continue  # Skip errors in individual generators

        active_gens = next_active


# ============================================================================
# Main Implementation
# ============================================================================


async def search_messages_impl(
    query: str | None = None,
    chat_id: str | None = None,
    message_ids: list[int] | None = None,
    post_id: int | None = None,
    limit: int = 20,
    min_date: str | None = None,  # ISO format date string
    max_date: str | None = None,  # ISO format date string
    chat_type: str | None = None,  # 'private', 'group', 'channel', or None
    public: bool
    | None = None,  # True=with username, False=without username, None=no filter
    auto_expand_batches: int = 1,  # Fewer extra batches to reduce RAM
    include_total_count: bool = False,  # Whether to include total count in response
) -> dict[str, Any]:
    """
    Unified message retrieval supporting search, specific message IDs, and post comments.

    PARAMETER COMBINATIONS:
    1. Search in chat: chat_id + query
    2. Browse chat: chat_id (returns recent messages)
    3. Read specific messages: chat_id + message_ids
    4. Read post comments: chat_id + post_id
    5. Search in comments: chat_id + post_id + query
    6. Global search: query only (no chat_id)

    CONFLICTS (will return error):
    - message_ids + post_id: Cannot combine
    - message_ids + query: Cannot combine (specific IDs don't need search)

    Args:
        query: Search query string (comma-separated for multiple queries). Optional for per-chat, required for global.
        chat_id: Target chat ID. Required for message_ids and post_id modes.
        message_ids: List of specific message IDs to retrieve. Conflicts with query and post_id.
        post_id: Channel post ID to retrieve discussion comments from. Conflicts with message_ids.
        limit: Maximum number of results to return
        min_date: Minimum date filter (ISO format)
        max_date: Maximum date filter (ISO format)
        chat_type: Filter by chat type ('private', 'group', 'channel', comma-separated)
        public: Filter by public discoverability (True=with username, False=without). Never applies to private chats.
        auto_expand_batches: Additional batches to fetch for filtered searches (default 1)
        include_total_count: Include total count in response (per-chat only, default False)

    Returns:
        Dictionary with:
        - 'messages': List of message dicts
        - 'has_more': Boolean indicating more results available (always False for message_ids mode)
        - 'total_count': Total messages (if include_total_count=True, chat search only)
        - 'discussion_chat_id': Discussion group ID (if post_id used)
        - 'discussion_total_count': Total comments (if post_id used and available)
        - 'linked_post_id': Original post ID (if post_id used)

    Note:
        - Global search requires non-empty query
        - Per-chat search allows empty query (returns recent messages)
        - Total count only available for per-chat searches, not global
        - Post comments require discussion to be enabled on the channel post
    """
    params = {
        "query": query,
        "chat_id": chat_id,
        "message_ids": message_ids,
        "post_id": post_id,
        "limit": limit,
        "min_date": min_date,
        "max_date": max_date,
        "chat_type": chat_type,
        "public": public,
        "auto_expand_batches": auto_expand_batches,
        "include_total_count": include_total_count,
        "is_global_search": chat_id is None,
        "has_query": bool(query and query.strip()),
        "has_date_filter": bool(min_date or max_date),
        "message_count": len(message_ids) if message_ids else 0,
    }

    # Parameter conflict validation
    if message_ids and post_id:
        return log_and_build_error(
            operation="get_messages",
            error_message="Cannot combine message_ids with post_id. Use one or the other.",
            params=params,
            exception=ValueError("Parameter conflict: message_ids and post_id are mutually exclusive"),
        )

    if message_ids and query:
        return log_and_build_error(
            operation="get_messages",
            error_message="Cannot combine message_ids with query. Specific message IDs don't need search.",
            params=params,
            exception=ValueError("Parameter conflict: message_ids and query are mutually exclusive"),
        )

    # Mode: Read specific messages by IDs
    if message_ids is not None:
        if not chat_id:
            return log_and_build_error(
                operation="get_messages",
                error_message="chat_id is required when using message_ids",
                params=params,
                exception=ValueError("chat_id required for message_ids mode"),
            )
        # Delegate to read_messages_by_ids and wrap in unified format
        messages_list = await read_messages_by_ids(chat_id, message_ids)
        
        # Check if it's an error (single-item list with error field)
        if len(messages_list) == 1 and "error" in messages_list[0]:
            return messages_list[0]
        
        # Wrap in unified format for consistency
        return {
            "messages": messages_list,
            "has_more": False,  # Reading by specific IDs never has more
        }

    # Mode: Read post comments
    if post_id is not None:
        if not chat_id:
            return log_and_build_error(
                operation="get_messages",
                error_message="chat_id is required when using post_id",
                params=params,
                exception=ValueError("chat_id required for post_id mode"),
            )
        return await _handle_post_comments_mode(chat_id, post_id, limit, query, params)

    # Normalize and validate queries for search modes
    queries: list[str] = (
        [q.strip() for q in query.split(",") if q.strip()] if query else []
    )

    if not chat_id and not queries:
        return log_and_build_error(
            operation="get_messages",
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
                        public,
                        auto_expand_batches,
                    )
                    for q in per_chat_queries
                ]
                await _execute_parallel_searches_generators(
                    generators, collected, seen_keys, limit
                )

                await transcribe_voice_messages(collected, entity)

                if include_total_count:
                    total_count = await _get_chat_message_count(chat_id)

            except Exception as e:
                return log_and_build_error(
                    operation="get_messages",
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
                        public,
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
                    operation="get_messages",
                    error_message=f"Failed to perform global search: {e!s}",
                    params=params,
                    exception=e,
                )

        # Return results up to limit
        window = collected[:limit] if limit is not None else collected

        logger.info(f"Found {len(window)} messages matching query: {query}")

        # Check if there are more messages available by collecting one extra message
        # If we collected exactly limit messages, assume there might be more (conservative approach)
        has_more = len(collected) > len(window) or (
            len(collected) == limit and len(collected) > 0
        )

        # If no messages found, return error instead of empty list for consistency
        if not window:
            return log_and_build_error(
                operation="get_messages",
                error_message=f"No messages found matching query '{query}'",
                params=params,
                exception=ValueError(f"No messages found matching query '{query}'"),
            )

        response = {"messages": window, "has_more": has_more}

        if total_count is not None:
            response["total_count"] = total_count

        return response
    except SessionNotAuthorizedError as e:
        return log_and_build_error(
            operation="get_messages",
            error_message="Session not authorized. Please authenticate your Telegram session first.",
            params=params,
            exception=e,
            action="authenticate_session",
        )
    except Exception as e:
        return log_and_build_error(
            operation="get_messages",
            error_message=f"Message retrieval failed: {e!s}",
            params=params,
            exception=e,
        )


async def _search_chat_messages_generator(
    client, entity, query, limit, chat_type, public, auto_expand_batches
):
    """Async generator version of chat message search for memory efficiency."""
    batch_count = 0
    # Allow more batches to ensure we can detect has_more properly
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0
    yielded_count = 0

    while batch_count < max_batches:
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

            if not _matches_public_filter(entity, public):
                continue

            result = await _build_result_for_message(client, message, entity)
            if not result:
                continue

            yield result
            yielded_count += 1

            # Continue processing all messages in this batch to ensure we can detect has_more

        if not last_id:
            break

        next_offset_id = last_id
        batch_count += 1


async def _search_global_messages_generator(
    client,
    query,
    limit,
    min_datetime,
    max_datetime,
    chat_type,
    public,
    auto_expand_batches,
):
    """Async generator version of global message search for memory efficiency."""
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0
    yielded_count = 0

    while batch_count < max_batches:
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
                limit=min(limit * 2, 50),
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

                if not _matches_public_filter(chat, public):
                    continue

                msg_result = await _build_result_for_message(client, message, chat)
                if not msg_result:
                    continue

                yield msg_result
                yielded_count += 1
            except Exception as e:
                logger.warning(f"Error processing message: {e}")
                continue

        if result.messages:
            next_offset_id = result.messages[-1].id
        batch_count += 1
