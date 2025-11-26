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
        "MessageMediaToDo",  # Todo lists
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

    # Handle Todo Lists
    elif media_cls == "MessageMediaToDo":
        todo_list = getattr(media, "todo", None)
        if todo_list:
            placeholder["type"] = "todo"
            # Extract title
            title_obj = getattr(todo_list, "title", None)
            if title_obj and hasattr(title_obj, "text"):
                placeholder["title"] = title_obj.text

            # Extract items
            items = getattr(todo_list, "list", [])
            if not isinstance(items, list):
                items = []
            placeholder["items"] = []
            for item in items:
                item_dict = {
                    "id": getattr(item, "id", 0),
                    "text": getattr(getattr(item, "title", None), "text", ""),
                    "completed": False,  # Will be updated if completions exist
                }
                placeholder["items"].append(item_dict)

            # Map completions to items
            completions = getattr(media, "completions", [])
            if not isinstance(completions, list):
                completions = []
            for completion in completions:
                item_id = getattr(completion, "id", None)
                completed_by = getattr(completion, "completed_by", None)
                completed_at = getattr(completion, "date", None)

                # Find the corresponding item and mark as completed
                for item in placeholder["items"]:
                    if item["id"] == item_id:
                        item["completed"] = True
                        if completed_by is not None:
                            item["completed_by"] = completed_by
                        if completed_at is not None:
                            item["completed_at"] = completed_at.isoformat()
                        break

    # Handle Polls
    elif media_cls == "MessageMediaPoll":
        poll = getattr(media, "poll", None)
        results = getattr(media, "results", None)
        if poll:
            placeholder["type"] = "poll"

            # Extract question
            question_obj = getattr(poll, "question", None)
            if question_obj and hasattr(question_obj, "text"):
                placeholder["question"] = question_obj.text

            # Extract options
            answers = getattr(poll, "answers", [])
            placeholder["options"] = []
            for answer in answers:
                option_dict = {
                    "text": getattr(getattr(answer, "text", None), "text", ""),
                    "voters": 0,  # Will be updated from results
                    "chosen": getattr(answer, "chosen", False),
                    "correct": getattr(answer, "correct", False),
                }
                placeholder["options"].append(option_dict)

            # Map vote counts from results
            if results and hasattr(results, "results"):
                result_counts = getattr(results, "results", [])
                for result in result_counts:
                    voters = getattr(result, "voters", 0)

                    # For simplicity, we'll map by index for now
                    # In a more sophisticated implementation, we'd match by option bytes
                    for option in placeholder["options"]:
                        if (
                            option["voters"] == 0
                        ):  # Simple mapping - first result to first option
                            option["voters"] = voters
                            break

            # Extract poll metadata
            placeholder["total_voters"] = (
                getattr(results, "total_voters", 0) if results else 0
            )
            placeholder["closed"] = getattr(poll, "closed", False)
            placeholder["public_voters"] = getattr(poll, "public_voters", True)
            placeholder["multiple_choice"] = getattr(poll, "multiple_choice", False)
            placeholder["quiz"] = getattr(poll, "quiz", False)

    else:
        # For other media types (photos, videos, etc.), try to get mime_type and size from media object
        mime_type = getattr(media, "mime_type", None)
        if mime_type:
            placeholder["mime_type"] = mime_type

        file_size = getattr(media, "size", None)
        if file_size is not None:
            placeholder["approx_size_bytes"] = file_size

    # Return None if no meaningful media metadata was extracted
    return placeholder if placeholder else None


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
        media_placeholder = _build_media_placeholder(message)
        if media_placeholder is not None:
            result["media"] = media_placeholder

    if forward_info is not None:
        result["forwarded_from"] = forward_info

    return result
