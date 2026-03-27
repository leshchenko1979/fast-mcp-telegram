import logging
from datetime import datetime
from enum import Enum, auto
from typing import Any

from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

from src.client.connection import SessionNotAuthorizedError, get_connected_client
from src.tools.links import generate_telegram_links
from src.tools.messages import read_messages_by_ids
from src.utils.discussion import get_post_discussion_info
from src.utils.entity import (
    _get_chat_message_count,
    _matches_chat_type,
    _matches_public_filter,
    compute_entity_identifier,
    get_entity_by_id,
)
from src.utils.error_handling import (
    log_and_build_error,
)
from src.utils.helpers import _append_dedup_until_limit
from src.utils.message_format import (
    _has_any_media,
    build_message_result,
    transcribe_voice_messages,
)

logger = logging.getLogger(__name__)


class MessageRetrievalMode(Enum):
    """Enumeration of message retrieval modes for get_messages."""

    MESSAGE_IDS = auto()
    REPLIES = auto()  # Unified: post comments, forum topics, message replies
    SEARCH = auto()


def _resolve_mode(
    *,
    chat_id: str | None,
    query: str | None,
    message_ids: list[int] | None,
    reply_to_id: int | None,
) -> MessageRetrievalMode:
    """
    Determine the message retrieval mode based on parameter combination.

    Raises ValueError if parameters conflict or required parameters are missing.
    """
    if message_ids is not None and reply_to_id is not None:
        raise ValueError(
            "Cannot combine message_ids with reply_to_id. Use one or the other."
        )
    if message_ids is not None and query is not None:
        raise ValueError(
            "Cannot combine message_ids with query. Specific message IDs don't need search."
        )

    if message_ids is not None:
        if not message_ids:
            raise ValueError("message_ids cannot be empty when provided")
        if not chat_id:
            raise ValueError("chat_id is required when using message_ids")
        return MessageRetrievalMode.MESSAGE_IDS

    if reply_to_id is not None:
        if not chat_id:
            raise ValueError("chat_id is required when using reply_to_id")
        return MessageRetrievalMode.REPLIES

    return MessageRetrievalMode.SEARCH


async def _handle_message_ids_mode(
    chat_id: str,
    message_ids: list[int],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle reading specific messages by IDs with unified output format."""
    messages_list = await read_messages_by_ids(chat_id, message_ids)

    if len(messages_list) == 1 and "error" in messages_list[0]:
        return messages_list[0]

    return {
        "messages": messages_list,
        "has_more": False,
    }


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

    has_content = (hasattr(message, "text") and message.text) or _has_any_media(message)
    if not has_content:
        return None

    try:
        identifier = compute_entity_identifier(chat_entity)
        if identifier is None:
            return None
        links = await generate_telegram_links(
            identifier, [message.id], resolved_entity=chat_entity
        )
        link = links.get("message_links", [None])[0]
        return await build_message_result(client, message, chat_entity, link)
    except Exception as e:
        logger.warning(f"Error processing message: {e}")
        return None


async def _fetch_replies(
    client,
    chat_entity,
    reply_to_id: int,
    limit: int,
    query: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """
    Fetch replies/comments for a message.

    Automatically handles:
    - Channel posts with discussion (detects and uses discussion group)
    - Forum topics (uses reply_to directly)
    - Regular message replies (uses reply_to directly)

    Returns tuple of (messages, discussion_metadata_or_none):
    - messages: List of reply message dicts
    - discussion_metadata: Dict with discussion info if channel post, None otherwise
    """
    effective_entity = chat_entity
    effective_reply_to = reply_to_id
    discussion_metadata = None

    if hasattr(chat_entity, "broadcast") and chat_entity.broadcast:
        try:
            discussion_info = await get_post_discussion_info(
                client, chat_entity, reply_to_id
            )
            effective_entity = discussion_info["discussion_peer"]
            effective_reply_to = discussion_info["discussion_msg_id"]
            discussion_metadata = {
                "discussion_chat_id": discussion_info["discussion_chat_id"],
                "discussion_total_count": discussion_info["discussion_total_count"],
                "linked_post_id": reply_to_id,
            }
            logger.debug("Detected channel post with discussion, using discussion chat")
        except ValueError:
            logger.debug(f"Channel post {reply_to_id} has no discussion enabled")

    collected = []
    async for message in client.iter_messages(
        effective_entity,
        reply_to=effective_reply_to,
        search=query or None,
        limit=limit + 1,
    ):
        result = await _build_result_for_message(client, message, effective_entity)
        if not result:
            continue

        collected.append(result)
        if len(collected) >= limit + 1:
            break

    await transcribe_voice_messages(collected[:limit], effective_entity)

    return collected, discussion_metadata


async def _handle_replies_mode(
    chat_id: str,
    reply_to_id: int,
    limit: int,
    query: str | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Handle fetching replies to a message.

    Automatically handles:
    - Channel post comments (via discussion group)
    - Forum topic messages
    - Regular message replies
    """
    client = await get_connected_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            raise ValueError(f"Could not find chat with ID '{chat_id}'")

        collected, discussion_metadata = await _fetch_replies(
            client, entity, reply_to_id, limit, query
        )

        window = collected[:limit] if limit is not None else collected
        has_more = len(collected) > len(window)

        if not window:
            return log_and_build_error(
                operation="get_messages",
                error_message=f"No replies found for message {reply_to_id}",
                params=params,
                exception=ValueError(f"No replies to message {reply_to_id}"),
            )

        logger.info(
            f"Retrieved {len(window)} replies to message {reply_to_id} in chat {chat_id}"
        )

        response = {
            "messages": window,
            "has_more": has_more,
            "reply_to_id": reply_to_id,
        }

        if discussion_metadata:
            response |= discussion_metadata

        return response

    except Exception as e:
        return log_and_build_error(
            operation="get_messages",
            error_message=f"Failed to fetch replies to message {reply_to_id}: {e!s}",
            params=params,
            exception=e,
        )


async def _execute_parallel_searches_generators(
    generators: list, collected: list[dict[str, Any]], seen_keys: set, limit: int
) -> None:
    """Execute multiple search generators in parallel for memory efficiency.

    Round-robin through generators to balance results and collect one extra message to determine has_more.
    """
    active_gens = list(enumerate(generators))
    target_limit = limit + 1

    while active_gens and len(collected) < target_limit:
        next_active = []

        for i, gen in active_gens:
            try:
                result = await gen.__anext__()
                _append_dedup_until_limit(collected, seen_keys, [result], target_limit)
                if len(collected) >= target_limit:
                    break
                next_active.append((i, gen))
            except StopAsyncIteration:
                continue
            except Exception as e:
                logger.warning(f"Error in search generator {i}: {e}")
                continue

        active_gens = next_active


async def _collect_messages_in_chat(
    client,
    chat_id: str,
    queries: list[str],
    limit: int,
    chat_type: str | None,
    public: bool | None,
    auto_expand_batches: int,
    include_total_count: bool,
    collected: list[dict[str, Any]],
    seen_keys: set[Any],
) -> int | None:
    entity = await get_entity_by_id(chat_id)
    if not entity:
        raise ValueError(f"Could not find chat with ID '{chat_id}'")
    per_chat_queries = queries or [""]
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
    await _execute_parallel_searches_generators(generators, collected, seen_keys, limit)
    await transcribe_voice_messages(collected, entity)
    return await _get_chat_message_count(chat_id) if include_total_count else None


async def _collect_messages_global(
    client,
    queries: list[str],
    limit: int,
    min_datetime: datetime | None,
    max_datetime: datetime | None,
    chat_type: str | None,
    public: bool | None,
    auto_expand_batches: int,
    collected: list[dict[str, Any]],
    seen_keys: set[Any],
) -> None:
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
    await _execute_parallel_searches_generators(generators, collected, seen_keys, limit)


async def _handle_search_mode(
    *,
    query: str | None,
    chat_id: str | None,
    limit: int,
    min_date: str | None,
    max_date: str | None,
    chat_type: str | None,
    public: bool | None,
    auto_expand_batches: int,
    include_total_count: bool,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle search/browse mode for messages."""
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

    client = await get_connected_client()
    try:
        total_count = None
        collected: list[dict[str, Any]] = []
        seen_keys: set[Any] = set()

        if chat_id:
            try:
                total_count = await _collect_messages_in_chat(
                    client,
                    chat_id,
                    queries,
                    limit,
                    chat_type,
                    public,
                    auto_expand_batches,
                    include_total_count,
                    collected,
                    seen_keys,
                )
            except Exception as e:
                return log_and_build_error(
                    operation="get_messages",
                    error_message=f"Failed to search in chat '{chat_id}': {e!s}",
                    params=params,
                    exception=e,
                )
        else:
            try:
                await _collect_messages_global(
                    client,
                    queries,
                    limit,
                    min_datetime,
                    max_datetime,
                    chat_type,
                    public,
                    auto_expand_batches,
                    collected,
                    seen_keys,
                )
            except Exception as e:
                return log_and_build_error(
                    operation="get_messages",
                    error_message=f"Failed to perform global search: {e!s}",
                    params=params,
                    exception=e,
                )

        window = collected[:limit] if limit is not None else collected

        logger.info(f"Found {len(window)} messages matching query: {query}")

        has_more = len(collected) > len(window) or (
            len(collected) == limit and len(collected) > 0
        )

        if not window:
            return log_and_build_error(
                operation="get_messages",
                error_message=f"No messages found matching query '{query}'",
                params=params,
                exception=ValueError(f"No messages found matching query '{query}'"),
            )

        response: dict[str, Any] = {"messages": window, "has_more": has_more}
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


async def search_messages_impl(
    query: str | None = None,
    chat_id: str | None = None,
    message_ids: list[int] | None = None,
    reply_to_id: int | None = None,
    limit: int = 20,
    min_date: str | None = None,
    max_date: str | None = None,
    chat_type: str | None = None,
    public: bool | None = None,
    auto_expand_batches: int = 1,
    include_total_count: bool = False,
) -> dict[str, Any]:
    """
    Unified message retrieval: search, browse, read by IDs, or list replies.

    Modes: chat + optional query (browse if query empty); chat + message_ids;
    chat + reply_to_id (optional query filters replies); global search (query only).
    message_ids cannot be combined with query or reply_to_id.

    Args:
        query: Search query string (comma-separated for multiple queries). Optional for per-chat, required for global.
        chat_id: Target chat ID. Required for message_ids and reply_to_id modes.
        message_ids: List of specific message IDs to retrieve. Conflicts with query and reply_to_id.
        reply_to_id: Message ID to get replies from. Works for:
            - Channel posts (fetches discussion comments automatically)
            - Forum topics (fetches topic messages)
            - Regular messages (fetches direct replies)
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
        - 'reply_to_id': Original message ID (if reply_to_id used)
        - 'discussion_chat_id': Discussion group ID (if channel post with discussion)
        - 'discussion_total_count': Total replies (if available)

    Global search requires a non-empty query; per-chat allows empty query (recent
    messages). include_total_count applies only to per-chat search. Channel
    post replies use the linked discussion group when available.
    """
    params = {
        "query": query,
        "chat_id": chat_id,
        "message_ids": message_ids,
        "reply_to_id": reply_to_id,
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

    try:
        mode = _resolve_mode(
            chat_id=chat_id,
            query=query,
            message_ids=message_ids,
            reply_to_id=reply_to_id,
        )
    except ValueError as e:
        return log_and_build_error(
            operation="get_messages",
            error_message=str(e),
            params=params,
            exception=e,
        )

    if mode is MessageRetrievalMode.MESSAGE_IDS:
        if chat_id is None or message_ids is None:
            return log_and_build_error(
                operation="get_messages",
                error_message="chat_id and message_ids required for message_ids mode",
                params=params,
                exception=ValueError("Missing required params"),
            )
        return await _handle_message_ids_mode(chat_id, message_ids, params)

    if mode is MessageRetrievalMode.REPLIES:
        if chat_id is None or reply_to_id is None:
            return log_and_build_error(
                operation="get_messages",
                error_message="chat_id and reply_to_id required for replies mode",
                params=params,
                exception=ValueError("Missing required params"),
            )
        return await _handle_replies_mode(chat_id, reply_to_id, limit, query, params)

    return await _handle_search_mode(
        query=query,
        chat_id=chat_id,
        limit=limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=chat_type,
        public=public,
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
        params=params,
    )


async def _search_chat_messages_generator(
    client, entity, query, limit, chat_type, public, auto_expand_batches
):
    """Async generator version of chat message search for memory efficiency."""
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0

    while batch_count < max_batches:
        last_id = None
        async for message in client.iter_messages(
            entity, search=query, offset_id=next_offset_id
        ):
            if not message:
                continue
            last_id = getattr(message, "id", None) or last_id

            if not _matches_chat_type(entity, chat_type):
                continue

            if not _matches_public_filter(entity, public):
                continue

            result = await _build_result_for_message(client, message, entity)
            if not result:
                continue

            yield result

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
            except Exception as e:
                logger.warning(f"Error processing message: {e}")
                continue

        if result.messages:
            next_offset_id = result.messages[-1].id
        batch_count += 1
