from typing import Dict, Any, Optional, List
from loguru import logger
import time
import traceback
from ..client.connection import connection_pool
from ..config.logging import format_diagnostic_info

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

    async with connection_pool.acquire() as client:
        try:
            # Handle username format
            if isinstance(chat_id, str) and not chat_id.startswith('@'):
                chat_id = f"@{chat_id}"
                logger.debug(f"[{request_id}] Using username: {chat_id}")

            # Get chat entity
            chat = await client.get_entity(chat_id)

            # Send message
            sent_message = await client.send_message(
                entity=chat,
                message=message,
                reply_to=reply_to_msg_id,
                parse_mode=parse_mode
            )

            result = {
                "message_id": sent_message.id,
                "date": sent_message.date.isoformat(),
                "chat_id": chat.id if hasattr(chat, 'id') else str(chat_id),
                "chat_name": chat.title if hasattr(chat, 'title') else (
                    chat.username if hasattr(chat, 'username') else str(chat_id)
                ),
                "text": sent_message.text,
                "status": "sent"
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

async def list_dialogs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    List available Telegram dialogs (chats).

    Args:
        limit: Maximum number of dialogs to return
    """
    request_id = f"dialogs_{int(time.time()*1000)}"
    logger.debug(f"[{request_id}] Listing Telegram dialogs, limit: {limit}")

    async with connection_pool.acquire() as client:
        try:
            dialogs = []
            async for dialog in client.iter_dialogs(limit=limit):
                dialogs.append({
                    "id": dialog.id,
                    "name": dialog.name,
                    "type": str(dialog.entity.__class__.__name__),
                    "unread_count": dialog.unread_count
                })

            logger.info(f"[{request_id}] Found {len(dialogs)} dialogs")
            return dialogs

        except Exception as e:
            error_info = {
                "request_id": request_id,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                "params": {"limit": limit}
            }
            logger.error(f"[{request_id}] Error listing dialogs", extra={"diagnostic_info": format_diagnostic_info(error_info)})
            raise
