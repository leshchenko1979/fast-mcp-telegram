from typing import Dict, Any, List, Union
from loguru import logger
import traceback
from ..config.logging import format_diagnostic_info

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

    Args:
        chat_id: The ID of the chat/channel or its username
        message_ids: Optional list of message IDs
        username: Optional username of the chat/channel (if known)
        thread_id: Optional topic/thread ID for forum messages
        comment_id: Optional comment message ID
        media_timestamp: Optional media timestamp in seconds

    Returns:
        Dict containing various formats of Telegram links:
        - private_chat_link: Link for private chats (requires membership)
        - public_chat_link: Link for public chats (if username is provided)
        - message_links: Links to specific messages (if message_ids provided)
        - join_link: Link to join the chat/channel (if applicable)
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

        # Add optional query parameters
        if thread_id:
            query_params.append(f"thread={thread_id}")
        if comment_id:
            query_params.append(f"comment={comment_id}")
        if media_timestamp:
            query_params.append(f"t={media_timestamp}")

        query_string = "&".join(query_params)
        if query_string:
            query_string = "?" + query_string

        # Handle public chats (with username)
        if username:
            clean_username = username.lstrip('@')
            result["public_chat_link"] = f"https://t.me/{clean_username}"

            if message_ids:
                result["message_links"] = []
                for msg_id in message_ids:
                    if thread_id:
                        # Format: t.me/username/thread_id/message_id?params
                        link = f"https://t.me/{clean_username}/{thread_id}/{msg_id}{query_string}"
                    else:
                        # Format: t.me/username/message_id?params
                        link = f"https://t.me/{clean_username}/{msg_id}{query_string}"
                    result["message_links"].append(link)

        # Handle private chats
        elif chat_id.isdigit():
            # For private chats, use c/channel_id format
            # Remove leading -100 for supergroups if present
            channel_id = chat_id[4:] if chat_id.startswith('-100') else chat_id
            result["private_chat_link"] = f"https://t.me/c/{channel_id}"

            if message_ids:
                result["message_links"] = []
                for msg_id in message_ids:
                    if thread_id:
                        # Format: t.me/c/channel_id/thread_id/message_id?params
                        link = f"https://t.me/c/{channel_id}/{thread_id}/{msg_id}{query_string}"
                    else:
                        # Format: t.me/c/channel_id/message_id?params
                        link = f"https://t.me/c/{channel_id}/{msg_id}{query_string}"
                    result["message_links"].append(link)

        # Add note about link accessibility
        result["note"] = "Private chat links only work for chat members. Public links work for anyone."

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
