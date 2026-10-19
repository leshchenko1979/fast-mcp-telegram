"""Context enrichment for search results (neighbors, reply-to, reply threads)."""

import asyncio
import logging
import time
from typing import Any

from telethon.errors import FloodWaitError

from src.utils.message_format import (
    extract_reply_quote,
    extract_topic_metadata,
    message_has_displayable_content,
)

from .forum_replies import _get_messages_by_ids_batched
from .replies import _fetch_replies

logger = logging.getLogger(__name__)

# Context enrichment caps
_CONTEXT_TIMEOUT_BUDGET = 30  # seconds for entire enrichment phase
_CONTEXT_MAX_IDS = 500  # max neighbor + reply_to IDs per batch
_CONTEXT_MAX_REPLY_FETCHES = 20  # max _fetch_replies calls
_CONTEXT_REPLY_LIMIT = 5  # max replies per result
_CONTEXT_PER_REPLY_TIMEOUT = 10  # seconds per individual reply fetch


def _is_valid_context_neighbor(
    message, is_forum: bool, result_topic_id: int | None
) -> bool:
    """Check if a neighbor message is valid for context inclusion."""
    if not message:
        return False
    if not message_has_displayable_content(message):
        return False
    if is_forum:
        neighbor_meta = extract_topic_metadata(message)
        neighbor_topic = neighbor_meta.get("topic_id")
        if result_topic_id is not None:
            return neighbor_topic == result_topic_id
        return neighbor_topic is None
    return True


def _lightweight_from_raw(message) -> dict[str, Any]:
    """Build lightweight context dict from a raw Telethon message."""
    full_text = (
        getattr(message, "text", None)
        or getattr(message, "message", None)
        or getattr(message, "caption", None)
    )
    # Include media type hint when text is absent
    if not full_text:
        media = getattr(message, "media", None)
        if media:
            full_text = f"[{type(media).__name__}]"
    lightweight: dict[str, Any] = {
        "id": message.id,
        "date": message.date.isoformat() if getattr(message, "date", None) else None,
        "text": full_text,
        "sender_id": getattr(message, "sender_id", None),
    }
    reply_quote = extract_reply_quote(message)
    if reply_quote is not None:
        lightweight["reply_quote"] = reply_quote
    return lightweight


def _lightweight_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Build lightweight context dict from a result dict."""
    sender = result.get("sender")
    sender_id = sender.get("id") if isinstance(sender, dict) else None
    lightweight: dict[str, Any] = {
        "id": result.get("id"),
        "date": result.get("date"),
        "text": result.get("text"),
        "sender_id": sender_id,
    }
    if (reply_quote := result.get("reply_quote")) is not None:
        lightweight["reply_quote"] = reply_quote
    return lightweight


async def _enrich_with_context(
    client,
    entity,
    messages: list[dict[str, Any]],
    context: int,
    include_replies: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    """Enrich search results with surrounding context and optional reply threads.

    Adds a 'context' envelope to each result with:
    - before[]: N messages before each result (lightweight format)
    - after[]: N messages after each result (lightweight format)
    - reply_to: the message being replied to (lightweight format, or null)
    - replies[]: direct replies (if include_replies=True, max 5)

    Caps: max 500 IDs, max 20 reply thread fetches, 30s timeout budget.
    Partial failure: returns results without context on error.
    Returns: (messages, warning_or_none) — warning set when IDs were capped.
    """
    if not messages:
        return messages, None

    start_time = time.monotonic()
    is_forum = bool(getattr(entity, "forum", False))

    # Step 1: Collect all unique IDs needed
    all_ids: set[int] = set()
    result_ids: set[int] = set()
    reply_to_ids: set[int] = set()

    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue
        result_ids.add(msg_id)
        for offset in range(1, context + 1):
            neighbor_id = msg_id - offset
            if neighbor_id > 0:
                all_ids.add(neighbor_id)
            all_ids.add(msg_id + offset)
        rt = msg.get("reply_to_msg_id")
        if rt:
            reply_to_ids.add(rt)

    # Include reply_to for resolution
    all_ids.update(reply_to_ids)
    # Result IDs needed for reply count checking only when reply threads requested
    if include_replies:
        all_ids.update(result_ids)
    all_ids.discard(0)

    # Track original count before cap mutation for correct warning
    original_count = len(all_ids)
    warning = None

    # Cap total IDs — prioritize reply_to and result IDs over neighbors
    if original_count > _CONTEXT_MAX_IDS:
        neighbor_ids = all_ids - reply_to_ids - result_ids
        all_ids = reply_to_ids | result_ids
        remaining = _CONTEXT_MAX_IDS - len(all_ids)
        if remaining > 0:
            all_ids.update(list(neighbor_ids)[:remaining])
        warning = (
            f"Context enrichment: {original_count} unique message IDs exceeded "
            f"the {_CONTEXT_MAX_IDS} cap; some context may be missing."
        )
        logger.warning(
            "Context enrichment: capped IDs to %d (was %d)",
            _CONTEXT_MAX_IDS,
            original_count,
        )

    # Step 2: Batch-fetch all needed messages
    try:
        raw_messages = await _get_messages_by_ids_batched(client, entity, list(all_ids))
    except FloodWaitError as e:
        wait = getattr(e, "seconds", 0) or 0
        logger.warning("Context enrichment FloodWaitError: wait %ds", wait)
        return messages, None
    except Exception as e:
        logger.warning("Context enrichment fetch failed: %s", e)
        return messages, None

    fetched: dict[int, Any] = {}
    for m in raw_messages:
        if m:
            fetched[m.id] = m

    # Step 3: Build context envelopes
    timed_out = False

    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue

        # Check timeout before processing each result
        if time.monotonic() - start_time > _CONTEXT_TIMEOUT_BUDGET:
            logger.warning(
                "Context enrichment: timeout budget exceeded (%.1fs), stopping",
                time.monotonic() - start_time,
            )
            timed_out = True
            break

        msg_topic_id = msg.get("topic_id")
        ctx: dict[str, Any] = {}

        # Before messages (most recent first → oldest last)
        before = []
        for offset in range(1, context + 1):
            neighbor = fetched.get(msg_id - offset)
            if _is_valid_context_neighbor(neighbor, is_forum, msg_topic_id):
                before.append(_lightweight_from_raw(neighbor))
        if before:
            ctx["before"] = before

        # After messages (oldest first → most recent last)
        after = []
        for offset in range(1, context + 1):
            neighbor = fetched.get(msg_id + offset)
            if _is_valid_context_neighbor(neighbor, is_forum, msg_topic_id):
                after.append(_lightweight_from_raw(neighbor))
        if after:
            ctx["after"] = after

        # Reply-to message
        rt = msg.get("reply_to_msg_id")
        if rt and rt in fetched:
            ctx["reply_to"] = _lightweight_from_raw(fetched[rt])
        else:
            ctx["reply_to"] = None

        # Reply threads — collect for parallel execution below
        if include_replies:
            ctx["replies"] = []  # placeholder; populated after parallel fetch

        if ctx:
            msg["context"] = ctx

    # Step 4: Parallel reply thread fetches (skip when budget already exceeded)
    if include_replies and not timed_out:
        reply_tasks: list[tuple[int, int]] = []  # (msg_index, msg_id)
        for i, msg in enumerate(messages[:_CONTEXT_MAX_REPLY_FETCHES]):
            msg_id = msg.get("id")
            if msg_id:
                reply_tasks.append((i, msg_id))

        if reply_tasks:
            reply_start = time.monotonic()
            timeout_count = 0
            failure_count = 0
            flood_wait_count = 0

            async def _fetch_one_reply(idx: int, mid: int) -> tuple[int, list]:
                nonlocal timeout_count, failure_count, flood_wait_count
                try:
                    async with asyncio.timeout(_CONTEXT_PER_REPLY_TIMEOUT):
                        replies, _disc_meta = await _fetch_replies(
                            client,
                            entity,
                            mid,
                            _CONTEXT_REPLY_LIMIT,
                            query=None,
                            include_chat_entity=False,
                            thread_scope="auto",
                        )
                        return idx, [
                            _lightweight_from_result(r)
                            for r in replies[:_CONTEXT_REPLY_LIMIT]
                        ]
                except TimeoutError:
                    timeout_count += 1
                    logger.debug("Reply fetch timeout for msg %d", mid)
                    return idx, []
                except FloodWaitError as e:
                    flood_wait_count += 1
                    wait = getattr(e, "seconds", 0) or 0
                    logger.warning(
                        "Reply fetch FloodWaitError for msg %d: wait %ds",
                        mid,
                        wait,
                    )
                    return idx, []
                except Exception as e:
                    failure_count += 1
                    logger.debug("Reply fetch failed for msg %d: %s", mid, e)
                    return idx, []

            results_list = await asyncio.gather(
                *[_fetch_one_reply(i, mid) for i, mid in reply_tasks],
                return_exceptions=True,
            )

            reply_elapsed = time.monotonic() - reply_start
            gather_failures = sum(
                1 for result in results_list if isinstance(result, BaseException)
            )
            if timeout_count or failure_count or flood_wait_count or gather_failures:
                logger.warning(
                    "Reply threads: %d fetches in %.1fs — timeouts=%d failures=%d "
                    "flood_waits=%d gather_errors=%d",
                    len(reply_tasks),
                    reply_elapsed,
                    timeout_count,
                    failure_count,
                    flood_wait_count,
                    gather_failures,
                )
            else:
                logger.debug(
                    "Reply threads: %d fetches completed in %.1fs",
                    len(reply_tasks),
                    reply_elapsed,
                )

            for result in results_list:
                if isinstance(result, BaseException):
                    logger.debug("Reply gather exception: %s", result)
                    continue
                idx, replies_list = result
                if idx < len(messages) and "context" in messages[idx]:
                    messages[idx]["context"]["replies"] = replies_list

    if timed_out and not warning:
        warning = "Context enrichment: timed out; some results may lack context."

    return messages, warning
