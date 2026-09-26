"""Single-chat info and forum topics for get_chat_info."""

import logging
from typing import Any

from telethon.tl.functions.messages import GetCommonChatsRequest, GetForumTopicsRequest

from src.client.connection import get_connected_client
from src.utils.entity import (
    build_entity_dict,
    build_entity_dict_enriched,
    get_entity_by_id,
)
from src.utils.error_handling import log_and_build_error

logger = logging.getLogger(__name__)


async def _list_forum_topics(entity, limit: int = 20) -> dict[str, Any]:
    """Return compact forum topics list for forum-enabled chats."""
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
        has_more = len(raw_topics) > requested_limit
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


async def _list_common_chats(entity, limit: int = 10) -> dict[str, Any] | None:
    """Return compact list of chats/groups shared with a user target.

    Only meaningful for user targets; returns None for anything else so the
    field is simply omitted (non-fatal, mirrors forum-topics behavior).
    """
    try:
        entity_type = entity.__class__.__name__
    except AttributeError:
        entity_type = ""
    if entity_type != "User":
        return None

    try:
        requested_limit = max(1, min(limit, 100))
    except TypeError:
        requested_limit = 10

    try:
        client = await get_connected_client()

        result = await client(
            GetCommonChatsRequest(user_id=entity, max_id=0, limit=requested_limit)
        )

        raw_chats = getattr(result, "chats", []) or []
        chats = []
        for chat in raw_chats:
            chat_dict = build_entity_dict(chat)
            if chat_dict is not None:
                chats.append(chat_dict)

        count = getattr(result, "count", None)
        if count is not None:
            has_more = count > len(chats)
        else:
            has_more = len(chats) >= requested_limit

        return {"common_chats": chats, "common_chats_has_more": has_more}
    except Exception as e:
        logger.debug("Failed to fetch common chats for %s: %s", entity, e)
        return None


async def get_chat_info_impl(
    chat_id: str, topics_limit: int = 20, common_chats_limit: int = 10
) -> dict[str, Any]:
    """
    Get detailed information about a specific chat (user, group, or channel).

    Args:
        chat_id: The chat identifier (user/chat/channel)
        topics_limit: Max topics to include for forum-enabled chats
        common_chats_limit: Max common groups to list for user targets

    Returns:
        Chat information or error message if not found
    """
    params = {
        "chat_id": chat_id,
        "topics_limit": topics_limit,
        "common_chats_limit": common_chats_limit,
    }

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

    if info.get("is_forum"):
        try:
            topics_result = await _list_forum_topics(entity, topics_limit)
            info["topics"] = topics_result["topics"]
            info["topics_has_more"] = topics_result["has_more"]
        except Exception as e:
            logger.debug("Failed to fetch forum topics for %s: %s", chat_id, e)

    if info.get("type") in ("private", "bot"):
        common_chats_result = await _list_common_chats(entity, common_chats_limit)
        if common_chats_result is not None:
            info["common_chats"] = common_chats_result["common_chats"]
            info["common_chats_has_more"] = common_chats_result["common_chats_has_more"]

    return info
