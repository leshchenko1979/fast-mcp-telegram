from typing import Dict, Any, List, Union
from loguru import logger
import traceback
from ..config.logging import format_diagnostic_info
from ..client.connection import connection_pool

async def generate_telegram_links(
    chat_id: str,
    message_ids: List[int] = None,
    username: str = None,
    thread_id: int = None,
    comment_id: int = None,
    media_timestamp: int = None
) -> Dict[str, Any]:
    """
    Generate various formats of Telegram links according to official spec.
    Now: chat_id может быть как username, так и id. Username и публичность определяются внутри.
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
                "media_timestamp": media_timestamp
            }
        }
    )

    try:
        result = {}
        query_params = []

        if thread_id:
            query_params.append(f"thread={thread_id}")
        if comment_id:
            query_params.append(f"comment={comment_id}")
        if media_timestamp:
            query_params.append(f"t={media_timestamp}")

        query_string = "&".join(query_params)
        if query_string:
            query_string = "?" + query_string

        # --- Новый блок: определяем username и публичность ---
        real_username = None
        is_public = False
        entity = None
        async with connection_pool as client:
            try:
                entity = await client.get_entity(chat_id)
            except Exception as e:
                logger.warning(f"Could not get entity by chat_id: {e}")
            if entity is None and username:
                try:
                    entity = await client.get_entity(username)
                except Exception as e2:
                    logger.warning(f"Could not get entity by username: {e2}")
            if entity is not None and hasattr(entity, 'username') and entity.username:
                real_username = entity.username
                is_public = True

        # --- Генерация ссылок ---
        if is_public and real_username:
            clean_username = real_username.lstrip('@')
            result["public_chat_link"] = f"https://t.me/{clean_username}"
            if message_ids:
                result["message_links"] = []
                for msg_id in message_ids:
                    if thread_id:
                        link = f"https://t.me/{clean_username}/{thread_id}/{msg_id}{query_string}"
                    else:
                        link = f"https://t.me/{clean_username}/{msg_id}{query_string}"
                    result["message_links"].append(link)
        elif entity is not None:
            # Приватный чат
            channel_id = str(entity.id)
            if channel_id.startswith('-100'):
                channel_id = channel_id[4:]
            result["private_chat_link"] = f"https://t.me/c/{channel_id}"
            if message_ids:
                result["message_links"] = []
                for msg_id in message_ids:
                    if thread_id:
                        link = f"https://t.me/c/{channel_id}/{thread_id}/{msg_id}{query_string}"
                    else:
                        link = f"https://t.me/c/{channel_id}/{msg_id}{query_string}"
                    result["message_links"].append(link)
        else:
            result["note"] = "Cannot resolve chat entity. Check chat_id or username."

        result["note"] = result.get("note") or "Private chat links only work for chat members. Public links work for anyone."
        logger.info(f"Successfully generated Telegram links for chat_id: {chat_id}")
        return result

    except Exception as e:
        error_info = {
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            },
            "params": {
                "chat_id": chat_id,
                "message_ids": message_ids,
                "username": username,
                "thread_id": thread_id,
                "comment_id": comment_id,
                "media_timestamp": media_timestamp
            }
        }
        logger.error("Error generating Telegram links", extra={"diagnostic_info": format_diagnostic_info(error_info)})
        raise

def format_chat_link(chat_id: str, is_private: bool = False) -> str:
    """
    Format a chat link based on chat ID and type.

    For private chats: t.me/c/channel_id
    For public chats: t.me/username
    """
    if is_private:
        channel_id = chat_id[4:] if chat_id.startswith('-100') else chat_id
        return f"https://t.me/c/{channel_id}"
    return f"https://t.me/{chat_id.lstrip('@')}"

def format_message_link(
    chat_id: str,
    message_id: int,
    is_private: bool = False,
    thread_id: int = None,
    comment_id: int = None,
    media_timestamp: int = None
) -> str:
    """
    Format a message link based on chat ID and message ID.

    Supports thread_id for forum messages, comment_id for comments,
    and media_timestamp for media messages.
    """
    query_params = []
    if comment_id:
        query_params.append(f"comment={comment_id}")
    if media_timestamp:
        query_params.append(f"t={media_timestamp}")

    query_string = "&".join(query_params)
    if query_string:
        query_string = "?" + query_string

    if is_private:
        channel_id = chat_id[4:] if chat_id.startswith('-100') else chat_id
        if thread_id:
            return f"https://t.me/c/{channel_id}/{thread_id}/{message_id}{query_string}"
        return f"https://t.me/c/{channel_id}/{message_id}{query_string}"
    else:
        username = chat_id.lstrip('@')
        if thread_id:
            return f"https://t.me/{username}/{thread_id}/{message_id}{query_string}"
        return f"https://t.me/{username}/{message_id}{query_string}"
