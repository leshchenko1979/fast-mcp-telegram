"""Shared utilities for Telegram channel post discussion threads."""

import asyncio
from typing import Any

from telethon.tl.functions.messages import GetDiscussionMessageRequest

from src.utils.entity import compute_entity_identifier


async def get_post_discussion_info(
    client: Any, channel_entity: Any, post_id: int
) -> dict[str, Any]:
    """
    Get discussion group information for a channel post.

    Caller is responsible for logging errors to avoid double-logging.

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

        discussion_entity = await client.get_entity(discussion_peer)
        discussion_chat_id = compute_entity_identifier(discussion_entity)

        total_count = getattr(result, "count", None)
        if total_count is None and hasattr(discussion_msg, "replies"):
            total_count = getattr(discussion_msg.replies, "replies", None)

        return {
            "discussion_peer": discussion_entity,
            "discussion_chat_id": discussion_chat_id,
            "discussion_msg_id": discussion_msg.id,
            "discussion_total_count": total_count,
        }

    except asyncio.CancelledError:
        raise
    except Exception as e:
        raise ValueError(f"Cannot access discussion for post {post_id}: {e!s}") from e
