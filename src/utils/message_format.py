import time
from typing import Any

from src.utils.entity import _extract_forward_info, build_entity_dict, get_entity_by_id


def _has_any_media(message) -> bool:
    """Check if message contains any type of media content."""
    if not hasattr(message, "media") or message.media is None:
        return False

    media = message.media
    media_class = media.__class__.__name__

    # Check for all known media types
    return media_class in [
        "MessageMediaPhoto",  # Photos
        "MessageMediaDocument",  # Documents, files, audio, video files
        "MessageMediaAudio",  # Audio files
        "MessageMediaVoice",  # Voice messages
        "MessageMediaVideo",  # Videos
        "MessageMediaWebPage",  # Link previews
        "MessageMediaGeo",  # Location
        "MessageMediaContact",  # Contact cards
        "MessageMediaPoll",  # Polls
        "MessageMediaDice",  # Dice animations
        "MessageMediaVenue",  # Venue/location with name
        "MessageMediaGame",  # Games
        "MessageMediaInvoice",  # Payments/invoices
        "MessageMediaUnsupported",  # Unsupported media types
    ]


def build_send_edit_result(message, chat, status: str) -> dict[str, Any]:
    """Build a consistent result dictionary for send/edit operations."""
    chat_dict = build_entity_dict(chat)
    sender_dict = build_entity_dict(getattr(message, "sender", None))

    result = {
        "message_id": message.id,
        "date": message.date.isoformat(),
        "chat": chat_dict,
        "text": message.text,
        "status": status,
        "sender": sender_dict,
    }

    # Add edit_date for edited messages
    if status == "edited" and hasattr(message, "edit_date") and message.edit_date:
        result["edit_date"] = message.edit_date.isoformat()

    return result


async def get_sender_info(client, message) -> dict[str, Any] | None:
    if hasattr(message, "sender_id") and message.sender_id:
        try:
            sender = await get_entity_by_id(message.sender_id)
            if sender:
                return build_entity_dict(sender)
            return {"id": message.sender_id, "error": "Sender not found"}
        except Exception:
            return {"id": message.sender_id, "error": "Failed to retrieve sender"}
    return None


def _build_media_placeholder(message) -> dict[str, Any] | None:
    """Return a lightweight, serializable media placeholder for LLM consumption.

    Avoids returning raw Telethon media objects which are large and not LLM-friendly.
    """
    media = getattr(message, "media", None)
    if not media:
        return None

    placeholder: dict[str, Any] = {}

    media_cls = media.__class__.__name__

    # Extract document-specific information
    if media_cls == "MessageMediaDocument":
        document = getattr(media, "document", None)
        if document:
            # Get mime_type and file_size from document object
            mime_type = getattr(document, "mime_type", None)
            if mime_type:
                placeholder["mime_type"] = mime_type

            file_size = getattr(document, "size", None)
            if file_size is not None:
                placeholder["approx_size_bytes"] = file_size

            # Try to get filename from document attributes
            if hasattr(document, "attributes"):
                for attr in document.attributes:
                    if hasattr(attr, "file_name") and attr.file_name:
                        placeholder["filename"] = attr.file_name
                        break
    else:
        # For other media types (photos, videos, etc.), try to get mime_type and size from media object
        mime_type = getattr(media, "mime_type", None)
        if mime_type:
            placeholder["mime_type"] = mime_type

        file_size = getattr(media, "size", None)
        if file_size is not None:
            placeholder["approx_size_bytes"] = file_size

    return placeholder


async def build_message_result(
    client, message, entity_or_chat, link: str | None
) -> dict[str, Any]:
    sender = await get_sender_info(client, message)
    chat = build_entity_dict(entity_or_chat)
    forward_info = await _extract_forward_info(message)

    full_text = (
        getattr(message, "text", None)
        or getattr(message, "message", None)
        or getattr(message, "caption", None)
    )

    result: dict[str, Any] = {
        "id": message.id,
        "date": message.date.isoformat() if getattr(message, "date", None) else None,
        "chat": chat,
        "text": full_text,
        "link": link,
        "sender": sender,
    }

    reply_to_msg_id = getattr(message, "reply_to_msg_id", None) or getattr(
        getattr(message, "reply_to", None), "reply_to_msg_id", None
    )
    if reply_to_msg_id is not None:
        result["reply_to_msg_id"] = reply_to_msg_id

    if hasattr(message, "media") and message.media:
        result["media"] = _build_media_placeholder(message)

    if forward_info is not None:
        result["forwarded_from"] = forward_info

    return result
