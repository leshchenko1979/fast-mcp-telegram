from typing import Dict, Any, Optional, List
from loguru import logger
import time
import traceback
from src.client.connection import get_connected_client
from src.config.logging import format_diagnostic_info
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.tools.links import generate_telegram_links
from src.utils.message_format import (
    build_message_result, 
    generate_request_id, 
    build_send_edit_result,
    log_operation_start,
    log_operation_success,
    log_operation_error
)

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
    request_id = generate_request_id("send_msg")
    params = {
        "chat_id": chat_id,
        "message_length": len(message),
        "reply_to_msg_id": reply_to_msg_id,
        "parse_mode": parse_mode
    }
    log_operation_start(request_id, "Sending message to chat", params)

    client = await get_connected_client()
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

        result = build_send_edit_result(sent_message, chat, "sent")
        log_operation_success(request_id, "Message sent", chat_id)
        return result

    except Exception as e:
        log_operation_error(request_id, "sending message", e, params)
        raise

async def edit_message(
    chat_id: str,
    message_id: int,
    new_text: str,
    parse_mode: str = None
) -> Dict[str, Any]:
    """
    Edit an existing message in a Telegram chat.

    Args:
        chat_id: The ID of the chat containing the message
        message_id: ID of the message to edit
        new_text: The new text content for the message
        parse_mode: Parse mode ('markdown' or 'html')
    """
    request_id = generate_request_id("edit_msg")
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "new_text_length": len(new_text),
        "parse_mode": parse_mode
    }
    log_operation_start(request_id, "Editing message in chat", params)

    client = await get_connected_client()
    try:
        chat = await get_entity_by_id(chat_id)
        if not chat:
            raise ValueError(f"Cannot find any entity corresponding to '{chat_id}'")

        # Edit message
        edited_message = await client.edit_message(
            entity=chat,
            message=message_id,
            text=new_text,
            parse_mode=parse_mode
        )

        result = build_send_edit_result(edited_message, chat, "edited")
        log_operation_success(request_id, "Message edited", chat_id)
        return result

    except Exception as e:
        log_operation_error(request_id, "editing message", e, params)
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
    request_id = generate_request_id("read_msgs")
    params = {
        "chat_id": chat_id,
        "message_ids": message_ids,
    }
    log_operation_start(request_id, "Reading messages by IDs", params)

    if not message_ids or not isinstance(message_ids, list):
        raise ValueError("message_ids must be a non-empty list of integers")

    client = await get_connected_client()
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

        successful_count = len([r for r in results if 'error' not in r])
        log_operation_success(request_id, f"Retrieved {successful_count} messages out of {len(message_ids)} requested")
        return results

    except Exception as e:
        log_operation_error(request_id, "reading messages by IDs", e, params)
        raise
