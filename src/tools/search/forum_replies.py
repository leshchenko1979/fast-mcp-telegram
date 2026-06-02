"""Forum in-topic reply fetch via messages.search + offset jump."""

from typing import Any

from telethon.tl.functions.messages import GetForumTopicsByIDRequest

from src.utils.message_format import (
    _extract_topic_metadata,
    message_has_displayable_content,
)

from . import results
from .topic_search import topic_search_request
from .types import (
    FORUM_ID_WINDOW_MAX_MARGIN,
    FORUM_LEGACY_SCAN_CAP,
    FORUM_REPLY_OFFSET_MARGIN_DIRECT,
    FORUM_REPLY_OFFSET_MARGIN_FULL,
    FORUM_REPLY_OFFSET_WIDEN,
    THREAD_SEARCH_CHUNK,
)


class ForumAnchorNotInTopicError(ValueError):
    """Anchor message cannot be resolved to a forum topic for in-topic search."""


async def _is_forum_topic_id(client, entity, topic_id: int) -> bool:
    """True when id is a real forum topic (not a stub from GetForumTopicsByID)."""
    result = await client(GetForumTopicsByIDRequest(peer=entity, topics=[topic_id]))
    topics = getattr(result, "topics", None) or []
    for topic in topics:
        if getattr(topic, "id", None) != topic_id:
            continue
        if topic.__class__.__name__ == "ForumTopicDeleted":
            continue
        if (
            getattr(topic, "title", None)
            or getattr(topic, "top_message", None) is not None
        ):
            return True
    return False


def _message_reply_parent_id(message: Any) -> int | None:
    reply_to = getattr(message, "reply_to", None)
    return getattr(message, "reply_to_msg_id", None) or getattr(
        reply_to, "reply_to_msg_id", None
    )


async def _forum_topic_id_from_anchor(client, entity, anchor_message: Any) -> int:
    reply_to = getattr(anchor_message, "reply_to", None)
    top_id = getattr(reply_to, "reply_to_top_id", None) if reply_to else None
    if top_id:
        return top_id

    topic_id = _extract_topic_metadata(anchor_message).get("topic_id")
    if topic_id is None:
        raise ForumAnchorNotInTopicError(
            f"Message {getattr(anchor_message, 'id', '?')} is not in a forum topic"
        )

    parent_id = _message_reply_parent_id(anchor_message)
    if parent_id is not None and topic_id == parent_id:
        if await _is_forum_topic_id(client, entity, topic_id):
            return topic_id
        parent = await client.get_messages(entity, ids=parent_id)
        if parent:
            parent_reply = getattr(parent, "reply_to", None)
            parent_top = (
                getattr(parent_reply, "reply_to_top_id", None) if parent_reply else None
            )
            if parent_top:
                return parent_top
            parent_topic = _extract_topic_metadata(parent).get("topic_id")
            if parent_topic is not None and parent_topic != parent_id:
                return parent_topic

    return topic_id


async def _get_messages_by_ids_batched(
    client, entity, message_ids: list[int]
) -> list[Any]:
    messages: list[Any] = []
    for offset in range(0, len(message_ids), THREAD_SEARCH_CHUNK):
        batch = message_ids[offset : offset + THREAD_SEARCH_CHUNK]
        loaded = await client.get_messages(entity, ids=batch)
        messages.extend(message for message in loaded if message)
    return messages


def _forum_offset_margins(include_nested: bool) -> tuple[int, ...]:
    initial = (
        FORUM_REPLY_OFFSET_MARGIN_FULL
        if include_nested
        else FORUM_REPLY_OFFSET_MARGIN_DIRECT
    )
    widen = [n for n in FORUM_REPLY_OFFSET_WIDEN if n > initial]
    return (initial, *widen)


async def _forum_topic_search(
    client,
    entity,
    topic_id: int,
    offset_id: int,
    query: str | None,
    min_date=None,
    max_date=None,
) -> list[Any]:
    result = await client(
        topic_search_request(
            entity,
            top_msg_id=topic_id,
            offset_id=offset_id,
            query=query,
            min_date=min_date,
            max_date=max_date,
        )
    )
    return list(getattr(result, "messages", None) or [])


def _forum_search_stub_needs_reply_reload(
    message: Any, anchor_msg_id: int, topic_id: int
) -> bool:
    """Search stubs may omit reply_to or set reply_to_msg_id to the topic root."""
    if message.id <= anchor_msg_id:
        return False
    parent_id = _message_reply_parent_id(message)
    return parent_id is None or parent_id == topic_id


async def _forum_collect_replies_in_id_window(
    client,
    entity,
    anchor_msg_id: int,
    max_message_id: int,
    limit: int,
) -> list[Any]:
    """Load messages in (anchor, max_id] and keep direct replies (forum id gaps are rare)."""
    if max_message_id <= anchor_msg_id:
        return []
    candidate_ids = list(range(anchor_msg_id + 1, max_message_id + 1))
    messages = await _get_messages_by_ids_batched(client, entity, candidate_ids)
    matched = [m for m in messages if _message_reply_parent_id(m) == anchor_msg_id]
    matched.sort(key=lambda m: m.id, reverse=True)
    return matched[:limit]


async def _enrich_forum_search_reply_metadata(
    client,
    entity,
    raw_messages: list[Any],
    anchor_msg_id: int,
    topic_id: int,
    *,
    max_message_id: int | None = None,
) -> list[Any]:
    """Reload search hits above the anchor when reply metadata is missing or wrong."""
    by_id = {m.id: m for m in raw_messages}
    reload_ids = [
        mid
        for mid, message in by_id.items()
        if (max_message_id is None or mid <= max_message_id)
        and _forum_search_stub_needs_reply_reload(message, anchor_msg_id, topic_id)
    ]
    if not reload_ids:
        return raw_messages
    for message in await _get_messages_by_ids_batched(client, entity, reload_ids):
        by_id[message.id] = message
    return [by_id.get(message.id, message) for message in raw_messages]


def _filter_forum_anchor_matches(
    raw_messages: list[Any],
    anchor_msg_id: int,
    *,
    include_nested: bool,
) -> list[Any]:
    if not include_nested:
        return [m for m in raw_messages if _message_reply_parent_id(m) == anchor_msg_id]

    descendant_ids: set[int] = {anchor_msg_id}
    matched: list[Any] = []
    while True:
        grew = False
        for message in raw_messages:
            if message.id in descendant_ids:
                continue
            parent_id = _message_reply_parent_id(message)
            if parent_id is None or parent_id not in descendant_ids:
                continue
            descendant_ids.add(message.id)
            matched.append(message)
            grew = True
        if not grew:
            break
    return matched


async def _scan_forum_topic_messages(
    client,
    entity,
    topic_id: int,
    anchor_msg_id: int,
    limit: int,
    query: str | None,
    *,
    start_offset_id: int,
    cap: int | None,
    include_nested: bool,
    min_date=None,
    max_date=None,
) -> list[Any]:
    raw_messages: list[Any] = []
    offset_id = start_offset_id
    target = limit + 1
    direct_count = 0

    while cap is None or len(raw_messages) < cap:
        messages = await _forum_topic_search(
            client, entity, topic_id, offset_id, query,
            min_date=min_date, max_date=max_date,
        )
        if not messages:
            break
        raw_messages.extend(messages)
        if not include_nested:
            direct_count += sum(
                _message_reply_parent_id(m) == anchor_msg_id for m in messages
            )
            if direct_count >= target or messages[-1].id <= anchor_msg_id:
                break
        elif messages[-1].id <= anchor_msg_id:
            break
        offset_id = messages[-1].id

    return raw_messages


async def _forum_search_collect_pass(
    client,
    entity,
    topic_id: int,
    anchor_msg_id: int,
    limit: int,
    query: str | None,
    *,
    start_offset_id: int,
    scan_cap: int | None,
    margin: int,
    include_nested: bool,
    min_date=None,
    max_date=None,
) -> list[Any]:
    raw = await _scan_forum_topic_messages(
        client,
        entity,
        topic_id,
        anchor_msg_id,
        limit,
        query,
        start_offset_id=start_offset_id,
        cap=scan_cap,
        include_nested=include_nested,
        min_date=min_date,
        max_date=max_date,
    )
    raw = await _enrich_forum_search_reply_metadata(
        client,
        entity,
        raw,
        anchor_msg_id,
        topic_id,
        max_message_id=start_offset_id or None,
    )
    matched = _filter_forum_anchor_matches(
        raw, anchor_msg_id, include_nested=include_nested
    )
    if matched or not raw or margin > FORUM_ID_WINDOW_MAX_MARGIN:
        return matched
    return await _forum_collect_replies_in_id_window(
        client, entity, anchor_msg_id, start_offset_id, limit + 1
    )


async def _collect_forum_anchor_replies(
    client,
    entity,
    anchor_message: Any,
    topic_id: int,
    limit: int,
    query: str | None,
    include_chat_entity: bool,
    *,
    include_nested: bool,
    min_date=None,
    max_date=None,
) -> list[dict[str, Any]]:
    """Replies to a message inside a forum topic via messages.search."""
    anchor_msg_id = anchor_message.id
    matched: list[Any] = []

    for margin in _forum_offset_margins(include_nested):
        matched = await _forum_search_collect_pass(
            client,
            entity,
            topic_id,
            anchor_msg_id,
            limit,
            query,
            start_offset_id=anchor_msg_id + margin,
            scan_cap=THREAD_SEARCH_CHUNK * 3,
            margin=margin,
            include_nested=include_nested,
            min_date=min_date,
            max_date=max_date,
        )
        if matched:
            break

    if not matched:
        matched = await _forum_search_collect_pass(
            client,
            entity,
            topic_id,
            anchor_msg_id,
            limit,
            query,
            start_offset_id=0,
            scan_cap=FORUM_LEGACY_SCAN_CAP,
            margin=FORUM_LEGACY_SCAN_CAP,
            include_nested=include_nested,
            min_date=min_date,
            max_date=max_date,
        )

    matched.sort(key=lambda m: m.id, reverse=True)
    matched = matched[: limit + 1]
    if not matched:
        return []

    ids_needing_reload = [
        m.id for m in matched if not message_has_displayable_content(m)
    ]
    by_id: dict[int, Any] = {m.id: m for m in matched}
    for message in await _get_messages_by_ids_batched(
        client, entity, ids_needing_reload
    ):
        by_id[message.id] = message

    collected: list[dict[str, Any]] = []
    for stub in matched:
        built = await results._build_result_for_message(
            client, by_id.get(stub.id, stub), entity, include_chat_entity
        )
        if built:
            collected.append(built)
    return collected
