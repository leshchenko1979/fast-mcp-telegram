from typing import Dict, Any, Optional
import time
import traceback
from loguru import logger
from src.utils.entity import build_entity_dict, get_entity_by_id, _extract_forward_info
from ..config.logging import format_diagnostic_info


def generate_request_id(prefix: str) -> str:
    """Generate a unique request ID with timestamp."""
    return f"{prefix}_{int(time.time()*1000)}"


def build_send_edit_result(message, chat, status: str) -> Dict[str, Any]:
    """Build a consistent result dictionary for send/edit operations."""
    chat_dict = build_entity_dict(chat)
    sender_dict = build_entity_dict(getattr(message, 'sender', None))
    
    result = {
        "message_id": message.id,
        "date": message.date.isoformat(),
        "chat": chat_dict,
        "text": message.text,
        "status": status,
        "sender": sender_dict
    }
    
    # Add edit_date for edited messages
    if status == "edited" and hasattr(message, 'edit_date') and message.edit_date:
        result["edit_date"] = message.edit_date.isoformat()
    
    return result


def log_operation_start(request_id: str, operation: str, params: Dict[str, Any]):
    """Log the start of an operation with consistent format."""
    logger.debug(
        f"[{request_id}] {operation}",
        extra={"params": params}
    )


def log_operation_success(request_id: str, operation: str, chat_id: str = None):
    """Log successful completion of an operation."""
    if chat_id:
        logger.info(f"[{request_id}] {operation} successfully in chat {chat_id}")
    else:
        logger.info(f"[{request_id}] {operation} successfully")


def log_operation_error(request_id: str, operation: str, error: Exception, params: Dict[str, Any]):
    """Log operation errors with consistent format."""
    error_info = {
        "request_id": request_id,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc()
        },
        "params": params
    }
    logger.error(f"[{request_id}] Error {operation}", extra={"diagnostic_info": format_diagnostic_info(error_info)})


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


