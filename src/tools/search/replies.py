"""Reply/thread fetch for get_messages reply_to_id mode."""

import logging
from typing import Any

from src.client.connection import get_connected_client
from src.utils.discussion import get_post_discussion_info
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.message_format import (
    response_attachment_warning,
    transcribe_voice_messages,
)

from . import results
from .forum_replies import (
    ForumAnchorNotInTopicError,
    _collect_forum_anchor_replies,
    _forum_topic_id_from_anchor,
    _is_forum_topic_id,
)
from .topic_search import topic_search_request
from .types import ThreadScope

logger = logging.getLogger(__name__)


async def _load_reply_anchor(client, entity, reply_to_id: int) -> Any:
    message = await client.get_messages(entity, ids=reply_to_id)
    if not message:
        raise ValueError(f"Message {reply_to_id} not found")
    return message


async def _is_forum_topic_anchor(
    client,
    effective_entity,
    effective_reply_to: int,
) -> bool:
    is_forum = bool(getattr(effective_entity, "forum", False))
    if not is_forum or effective_reply_to == 1:
        return False
    return await _is_forum_topic_id(client, effective_entity, effective_reply_to)


async def _should_use_thread_search(
    client,
    effective_entity,
    effective_reply_to: int,
    thread_scope: ThreadScope,
    discussion_metadata: dict[str, Any] | None,
) -> bool:
    """SearchRequest(top_msg_id) for supergroup threads; not for forum topics or discussions."""
    if thread_scope != "full":
        return False
    if discussion_metadata is not None:
        return False
    return not await _is_forum_topic_anchor(
        client, effective_entity, effective_reply_to
    )


async def _collect_full_thread_messages(
    client,
    entity,
    top_msg_id: int,
    limit: int,
    query: str | None,
    include_chat_entity: bool,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    offset_id = 0
    target = limit + 1

    while len(collected) < target:
        result = await client(
            topic_search_request(
                entity,
                top_msg_id=top_msg_id,
                offset_id=offset_id,
                query=query,
            )
        )
        messages = getattr(result, "messages", None) or []
        if not messages:
            break

        remaining = target - len(collected)
        collected.extend(
            await results._build_results_up_to_limit(
                client,
                messages,
                entity,
                include_chat_entity,
                limit=remaining - 1,
            )
        )
        if len(collected) >= target:
            break
        offset_id = messages[-1].id

    return collected


async def _fetch_direct_replies(
    client,
    entity,
    reply_to_id: int,
    limit: int,
    query: str | None,
    include_chat_entity: bool,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    async for message in client.iter_messages(
        entity,
        reply_to=reply_to_id,
        search=query or None,
        limit=limit + 1,
    ):
        result = await results._build_result_for_message(
            client, message, entity, include_chat_entity
        )
        if not result:
            continue
        collected.append(result)
        if len(collected) >= limit + 1:
            break
    return collected


async def _fetch_replies(
    client,
    chat_entity,
    reply_to_id: int,
    limit: int,
    query: str | None = None,
    include_chat_entity: bool = False,
    thread_scope: ThreadScope = "auto",
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Fetch replies/comments; routes forum in-topic, discussion, and thread search."""
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

    is_forum = bool(getattr(effective_entity, "forum", False))
    collected: list[dict[str, Any]] | None = None

    if is_forum and effective_reply_to != 1:
        anchor_message = await _load_reply_anchor(
            client, effective_entity, effective_reply_to
        )
        reply_to = getattr(anchor_message, "reply_to", None)
        in_topic_anchor = getattr(
            reply_to, "reply_to_top_id", None
        ) is not None or not await _is_forum_topic_id(
            client, effective_entity, effective_reply_to
        )
        if in_topic_anchor:
            try:
                topic_id = await _forum_topic_id_from_anchor(
                    client, effective_entity, anchor_message
                )
                collected = await _collect_forum_anchor_replies(
                    client,
                    effective_entity,
                    anchor_message,
                    topic_id,
                    limit,
                    query,
                    include_chat_entity,
                    include_nested=thread_scope == "full",
                )
            except ForumAnchorNotInTopicError:
                logger.debug(
                    "Anchor %s is not in-topic; trying GetReplies for topic id",
                    effective_reply_to,
                )
                collected = await _fetch_direct_replies(
                    client,
                    effective_entity,
                    effective_reply_to,
                    limit,
                    query,
                    include_chat_entity,
                )
        else:
            collected = await _fetch_direct_replies(
                client,
                effective_entity,
                effective_reply_to,
                limit,
                query,
                include_chat_entity,
            )

    if collected is None:
        if await _should_use_thread_search(
            client,
            effective_entity,
            effective_reply_to,
            thread_scope,
            discussion_metadata,
        ):
            collected = await _collect_full_thread_messages(
                client,
                effective_entity,
                effective_reply_to,
                limit,
                query,
                include_chat_entity,
            )
        else:
            collected = await _fetch_direct_replies(
                client,
                effective_entity,
                effective_reply_to,
                limit,
                query,
                include_chat_entity,
            )

    await transcribe_voice_messages(collected[:limit], effective_entity, client=client)

    return collected, discussion_metadata


async def _handle_reply_mode(
    chat_id: str,
    reply_to_id: int,
    limit: int,
    query: str | None,
    params: dict[str, Any],
    thread_scope: ThreadScope = "auto",
) -> dict[str, Any]:
    """Handle reply_to_id mode (discussion, forum, direct replies, full thread)."""
    client = await get_connected_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            raise ValueError(f"Could not find chat with ID '{chat_id}'")

        collected, discussion_metadata = await _fetch_replies(
            client,
            entity,
            reply_to_id,
            limit,
            query,
            include_chat_entity=False,
            thread_scope=thread_scope,
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

        if warning := response_attachment_warning(window):
            response["_warning"] = warning  # ty: ignore

        return response

    except Exception as e:
        return log_and_build_error(
            operation="get_messages",
            error_message=f"Failed to fetch replies to message {reply_to_id}: {e!s}",
            params=params,
            exception=e,
        )
