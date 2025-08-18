from typing import Dict, Any, Optional
from src.utils.entity import build_entity_dict, get_entity_by_id, _extract_forward_info


async def get_sender_info(client, message) -> Optional[Dict[str, Any]]:
    if hasattr(message, 'sender_id') and message.sender_id:
        try:
            sender = await get_entity_by_id(message.sender_id)
            if sender:
                return build_entity_dict(sender)
            return {"id": message.sender_id, "error": "Sender not found"}
        except Exception:
            return {"id": message.sender_id, "error": "Failed to retrieve sender"}
    return None


async def build_message_result(client, message, entity_or_chat, link: Optional[str]) -> Dict[str, Any]:
    sender = await get_sender_info(client, message)
    chat = build_entity_dict(entity_or_chat)
    forward_info = await _extract_forward_info(message)

    result: Dict[str, Any] = {
        "id": message.id,
        "date": message.date.isoformat() if getattr(message, 'date', None) else None,
        "chat": chat,
        "text": getattr(message, 'text', None) or getattr(message, 'message', None) or getattr(message, 'caption', None),
        "link": link,
        "sender": sender
    }

    reply_to_msg_id = getattr(message, 'reply_to_msg_id', None) or getattr(getattr(message, 'reply_to', None), 'reply_to_msg_id', None)
    if reply_to_msg_id is not None:
        result["reply_to_msg_id"] = reply_to_msg_id

    if hasattr(message, 'media') and message.media:
        result["media"] = message.media

    if forward_info is not None:
        result["forwarded_from"] = forward_info

    return result


