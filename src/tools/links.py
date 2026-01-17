import logging
import traceback
from typing import Any

from src.client.connection import get_connected_client
from src.config.logging import format_diagnostic_info
from src.utils.entity import get_entity_by_id

logger = logging.getLogger(__name__)


def _normalize_channel_id(channel_id: str) -> str:
    """Normalize channel ID by removing -100 prefix for private channels."""
    return channel_id[4:] if channel_id.startswith("-100") else channel_id


def _build_query_string(
    thread_id: int | None = None,
    comment_id: int | None = None,
    media_timestamp: int | None = None,
) -> str:
    """Build query string for Telegram links."""
    query_params = []
    if thread_id:
        query_params.append(f"thread={thread_id}")
    if comment_id:
        query_params.append(f"comment={comment_id}")
    if media_timestamp:
        query_params.append(f"t={media_timestamp}")

    query_string = "&".join(query_params)
    return "?" + query_string if query_string else ""


async def _resolve_entity_for_links(
    chat_id: str,
    username: str | None = None,
    resolved_entity=None,
) -> tuple[bool, str | None, object | None]:
    """
    Resolve entity information for link generation.

    Returns (is_public, username, entity)
    """
    if resolved_entity is not None:
        entity = resolved_entity
    else:
        await get_connected_client()
        entity = await get_entity_by_id(chat_id)

        if entity is None and username:
            entity = await get_entity_by_id(username)

    real_username = None
    is_public = False

    if entity is not None and hasattr(entity, "username") and entity.username:
        real_username = entity.username
        is_public = True

    return is_public, real_username, entity


async def generate_telegram_links(
    chat_id: str,
    message_ids: list[int] | None = None,
    username: str | None = None,
    thread_id: int | None = None,
    comment_id: int | None = None,
    media_timestamp: int | None = None,
    resolved_entity=None,
) -> dict[str, Any]:
    """
    Generate various formats of Telegram links according to official spec.

    Args:
        chat_id: Chat identifier (numeric ID, username, or 'me')
        message_ids: List of message IDs to generate links for
        username: Optional username if different from chat_id
        thread_id: Forum thread ID for forum messages
        comment_id: Comment ID for comment links
        media_timestamp: Timestamp for media links
        resolved_entity: Pre-resolved entity object to avoid API calls

    Returns:
        Dict containing link information and metadata
    """
    logger.debug(
        "Generating Telegram links",
        extra={
            "params": {
                "chat_id": chat_id,
                "message_ids": message_ids,
                "username": username,
                "thread_id": thread_id,
                "comment_id": comment_id,
                "media_timestamp": media_timestamp,
            }
        },
    )

    try:
        # Resolve entity information
        is_public, real_username, entity = await _resolve_entity_for_links(
            chat_id, username, resolved_entity
        )

        result = {}
        query_string = _build_query_string(thread_id, comment_id, media_timestamp)

        # Generate chat links
        if is_public and real_username:
            clean_username = real_username.lstrip("@")
            result["public_chat_link"] = f"https://t.me/{clean_username}"
        elif entity is not None:
            channel_id = _normalize_channel_id(str(entity.id))
            result["private_chat_link"] = f"https://t.me/c/{channel_id}"
        else:
            result["note"] = "Cannot resolve chat entity. Check chat_id or username."

        # Generate message links
        if message_ids and ((is_public and real_username) or entity is not None):
            result["message_links"] = []
            for msg_id in message_ids:
                if is_public and real_username:
                    clean_username = real_username.lstrip("@")
                    if thread_id:
                        link = f"https://t.me/{clean_username}/{thread_id}/{msg_id}{query_string}"
                    else:
                        link = f"https://t.me/{clean_username}/{msg_id}{query_string}"
                else:
                    channel_id = _normalize_channel_id(str(entity.id))
                    if thread_id:
                        link = f"https://t.me/c/{channel_id}/{thread_id}/{msg_id}{query_string}"
                    else:
                        link = f"https://t.me/c/{channel_id}/{msg_id}{query_string}"
                result["message_links"].append(link)

        # Add default note if not set
        if "note" not in result:
            result["note"] = (
                "Private chat links only work for chat members. Public links work for anyone."
            )

        logger.info(f"Successfully generated Telegram links for chat_id: {chat_id}")
        return result

    except Exception as e:
        error_info = {
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
            "params": {
                "chat_id": chat_id,
                "message_ids": message_ids,
                "username": username,
                "thread_id": thread_id,
                "comment_id": comment_id,
                "media_timestamp": media_timestamp,
            },
        }
        logger.error(
            "Error generating Telegram links",
            extra={"diagnostic_info": format_diagnostic_info(error_info)},
        )
        raise
