from typing import Dict, Any, Optional, List
from loguru import logger
import time
import traceback
from ..client.connection import get_client
from ..config.logging import format_diagnostic_info
from src.utils.entity import build_entity_dict

async def send_message(
    chat_id: str,
    message: str,
    reply_to_msg_id: int = None,
    parse_mode: str = None
) -> Dict[str, Any]:
    """
    Send a message to a Telegram chat.

    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send
        reply_to_msg_id: ID of the message to reply to
        parse_mode: Parse mode ('markdown' or 'html')
    """
    request_id = f"send_msg_{int(time.time()*1000)}"
    logger.debug(
        f"[{request_id}] Sending message to chat",
        extra={
            "params": {
                "chat_id": chat_id,
                "message_length": len(message),
                "reply_to_msg_id": reply_to_msg_id,
                "parse_mode": parse_mode
            }
        }
    )

    client = await get_client()
    try:
        # Не модифицируем chat_id, передаём как есть
        chat = await client.get_entity(chat_id)

        # Send message
        sent_message = await client.send_message(
            entity=chat,
            message=message,
            reply_to=reply_to_msg_id,
            parse_mode=parse_mode
        )

        chat_dict = build_entity_dict(chat)
        sender_dict = build_entity_dict(getattr(sent_message, 'sender', None))
        result = {
            "message_id": sent_message.id,
            "date": sent_message.date.isoformat(),
            "chat": chat_dict,
            "text": sent_message.text,
            "status": "sent",
            "sender": sender_dict
        }

        logger.info(f"[{request_id}] Message sent successfully to chat {chat_id}")
        return result

    except Exception as e:
        error_info = {
            "request_id": request_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            },
            "params": {
                "chat_id": chat_id,
                "message_length": len(message),
                "reply_to_msg_id": reply_to_msg_id,
                "parse_mode": parse_mode
            }
        }
        logger.error(f"[{request_id}] Error sending message", extra={"diagnostic_info": format_diagnostic_info(error_info)})
        raise

async def list_dialogs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    List available Telegram dialogs (chats) with pagination.

    Args:
        limit: Maximum number of dialogs to return
        offset: Number of dialogs to skip (for pagination)
    """
    request_id = f"dialogs_{int(time.time()*1000)}"
    logger.debug(f"[{request_id}] Listing Telegram dialogs, limit: {limit}, offset: {offset}")

    client = await get_client()
    try:
        dialogs = []
        count = 0
        async for dialog in client.iter_dialogs():
            if count < offset:
                count += 1
                continue
            if len(dialogs) >= limit:
                break
            dialogs.append({
                "id": dialog.id,
                "name": dialog.name,
                "type": str(dialog.entity.__class__.__name__),
                "unread_count": dialog.unread_count
            })
            count += 1

        logger.info(f"[{request_id}] Found {len(dialogs)} dialogs (offset: {offset})")
        return dialogs

    except Exception as e:
        error_info = {
            "request_id": request_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            },
            "params": {"limit": limit, "offset": offset}
        }
        logger.error(f"[{request_id}] Error listing dialogs", extra={"diagnostic_info": format_diagnostic_info(error_info)})
        raise
