from typing import Dict, Any, Optional, List
from loguru import logger
import time
import traceback
from ..client.connection import get_client
from ..config.logging import format_diagnostic_info
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.tools.links import generate_telegram_links
from src.utils.message_format import build_message_result

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
        chat = await get_entity_by_id(chat_id)
        if not chat:
            raise ValueError(f"Cannot find any entity corresponding to '{chat_id}'")

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


async def read_messages_by_ids(chat_id: str, message_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Read specific messages by their IDs from a given chat.

    Args:
        chat_id: Target chat identifier (username like '@channel', numeric ID, or '-100...' form)
        message_ids: List of message IDs to fetch

    Returns:
        List of message dictionaries consistent with search results format
    """
    request_id = f"read_msgs_{int(time.time()*1000)}"
    logger.debug(
        f"[{request_id}] Reading messages by IDs",
        extra={
            "params": {
                "chat_id": chat_id,
                "message_ids": message_ids,
            }
        }
    )

    if not message_ids or not isinstance(message_ids, list):
        raise ValueError("message_ids must be a non-empty list of integers")

    client = await get_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            raise ValueError(f"Cannot find any entity corresponding to '{chat_id}'")

        # Fetch messages (Telethon returns a list in the same order as requested ids)
        messages = await client.get_messages(entity, ids=message_ids)
        if not isinstance(messages, list):
            messages = [messages]

        # Pre-generate links for all requested messages
        try:
            links_info = await generate_telegram_links(chat_id, message_ids)
            message_links = links_info.get("message_links", []) or []
            id_to_link = {mid: message_links[idx] for idx, mid in enumerate(message_ids) if idx < len(message_links)}
        except Exception:
            id_to_link = {}

        chat_dict = build_entity_dict(entity)
        results: List[Dict[str, Any]] = []
        for idx, requested_id in enumerate(message_ids):
            msg = None
            # Telethon may return None for missing messages; map by index if lengths match, else search
            if idx < len(messages):
                candidate = messages[idx]
                if candidate is not None and getattr(candidate, 'id', None) == requested_id:
                    msg = candidate
                else:
                    # Fallback: try to find exact id in returned list
                    for m in messages:
                        if m is not None and getattr(m, 'id', None) == requested_id:
                            msg = m
                            break

            if not msg:
                results.append({
                    "id": requested_id,
                    "chat": chat_dict,
                    "error": "Message not found or inaccessible"
                })
                continue

            link = id_to_link.get(getattr(msg, 'id', requested_id))
            built = await build_message_result(client, msg, entity, link)
            results.append(built)

        logger.info(f"[{request_id}] Retrieved {len([r for r in results if 'error' not in r])} messages out of {len(message_ids)} requested")
        return results

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
                "message_ids": message_ids,
            }
        }
        logger.error(f"[{request_id}] Error reading messages by IDs", extra={"diagnostic_info": format_diagnostic_info(error_info)})
        raise
