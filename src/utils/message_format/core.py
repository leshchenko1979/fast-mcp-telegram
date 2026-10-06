"""Telegram message serialization for MCP tool responses."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.utils.entity import (
    _extract_forward_info,
    _forward_peer_id_and_type_label,
    build_entity_dict,
)

from .attachments import (
    _maybe_set_attachment_download_url,
    _maybe_set_rich_attachment_download_urls,
    build_rich_attachment_placeholders,
)
from .rich import RichMediaRef, flatten_rich_message


def _service_action_placeholder_text(message) -> str | None:
    """Short English label for Telegram service messages (Message.action set)."""
    action = getattr(message, "action", None)
    if action is None:
        return None
    cls_name = action.__class__.__name__
    prefix = "MessageAction"
    if cls_name.startswith(prefix) and len(cls_name) > len(prefix):
        tail = cls_name[len(prefix) :]
        return f"[Service: {tail}]"
    return f"[Service: {cls_name}]"


# Single source of truth for media-class handling. Every real telethon 1.45.0
# `MessageMedia*` class we render maps to the canonical `media.type` value it
# produces. `_KNOWN_MEDIA_CLASSES` is DERIVED from this table, so the display
# filter (`message_has_displayable_content`) and the formatter
# (`_build_media_placeholder`) can no longer disagree about which classes carry
# content -- the disagreement that made contact cards arrive as `media: null`
# (issue #159).
#
# Deliberately absent:
#   * `MessageMediaEmpty` -- carries nothing, must not pass the filter.
#   * `MessageMediaVoice` / `MessageMediaVideo` / `MessageMediaAudio` -- these
#     names do NOT exist in telethon 1.45.0. Voice notes and round videos are a
#     `MessageMediaDocument` distinguished by `DocumentAttributeAudio(voice=True)`
#     / `DocumentAttributeVideo(round_message=True)`.
_MEDIA_TYPES: dict[str, str] = {
    "MessageMediaPhoto": "photo",
    "MessageMediaDocument": "document",
    "MessageMediaWebPage": "webpage",
    "MessageMediaGeo": "geo",
    "MessageMediaGeoLive": "geo_live",
    "MessageMediaContact": "contact",
    "MessageMediaPoll": "poll",
    "MessageMediaDice": "dice",
    "MessageMediaVenue": "venue",
    "MessageMediaGame": "game",
    "MessageMediaInvoice": "invoice",
    "MessageMediaToDo": "todo",
    "MessageMediaStory": "story",
    "MessageMediaGiveaway": "giveaway",
    "MessageMediaGiveawayResults": "giveaway_results",
    "MessageMediaPaidMedia": "paid_media",
    "MessageMediaVideoStream": "video_stream",
    "MessageMediaUnsupported": "unsupported",
}

_KNOWN_MEDIA_CLASSES = frozenset(_MEDIA_TYPES)


def _document_voice_and_round_note_flags(document) -> tuple[bool, bool]:
    """Return (is_voice_message, is_round_video) from document attributes."""
    is_voice = False
    is_round_video = False
    for attr in getattr(document, "attributes", []) or []:
        ac = attr.__class__.__name__
        if ac == "DocumentAttributeAudio" and getattr(attr, "voice", False):
            is_voice = True
        elif ac == "DocumentAttributeVideo" and getattr(attr, "round_message", False):
            is_round_video = True
    return is_voice, is_round_video


def _has_any_media(message) -> bool:
    """Check if message contains any type of media content."""
    if not hasattr(message, "media") or message.media is None:
        return False
    return message.media.__class__.__name__ in _KNOWN_MEDIA_CLASSES


def message_has_displayable_content(message: Any) -> bool:
    """True when a Telethon message has text, media, rich content, or a service placeholder."""
    if not message:
        return False
    if getattr(message, "rich_message", None) is not None:
        return True
    if (
        getattr(message, "text", None)
        or getattr(message, "message", None)
        or getattr(message, "caption", None)
    ):
        return True
    if _has_any_media(message):
        return True
    return _service_action_placeholder_text(message) is not None


def _resolve_message_text(
    message: Any,
    *,
    rich_cache: tuple[str, list[RichMediaRef]] | None = None,
) -> str | None:
    """Plain or rich text for MCP output; rich flatten wins when non-empty."""
    if rich_cache is not None:
        flattened, _ = rich_cache
        if flattened:
            return flattened
    elif getattr(message, "rich_message", None) is not None:
        flattened, _ = flatten_rich_message(message.rich_message)
        if flattened:
            return flattened
    plain = (
        getattr(message, "text", None)
        or getattr(message, "message", None)
        or getattr(message, "caption", None)
    )
    if plain:
        return plain
    return _service_action_placeholder_text(message)


def _decode_callback_data(button) -> str:
    data = getattr(button, "data", None)
    return data.decode("utf-8", errors="replace") if data else ""


def _inline_button_extra_url(button) -> dict[str, Any]:
    return {"type": "url", "url": getattr(button, "url", "")}


def _inline_button_extra_callback(button) -> dict[str, Any]:
    return {"type": "callback_data", "data": _decode_callback_data(button)}


def _inline_button_extra_switch_inline(button) -> dict[str, Any]:
    return {"type": "switch_inline_query", "query": getattr(button, "query", "")}


def _inline_button_extra_switch_inline_same(button) -> dict[str, Any]:
    return {
        "type": "switch_inline_query_current_chat",
        "query": getattr(button, "query", ""),
    }


def _inline_button_extra_game(_button) -> dict[str, Any]:
    return {"type": "callback_game"}


def _inline_button_extra_buy(_button) -> dict[str, Any]:
    return {"type": "pay"}


def _inline_button_extra_user_profile(button) -> dict[str, Any]:
    return {"type": "user_profile", "user_id": getattr(button, "user_id", None)}


_INLINE_BUTTON_SERIALIZERS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "KeyboardButtonUrl": _inline_button_extra_url,
    "KeyboardButtonCallback": _inline_button_extra_callback,
    "KeyboardButtonSwitchInline": _inline_button_extra_switch_inline,
    "KeyboardButtonSwitchInlineSame": _inline_button_extra_switch_inline_same,
    "KeyboardButtonGame": _inline_button_extra_game,
    "KeyboardButtonBuy": _inline_button_extra_buy,
    "KeyboardButtonUserProfile": _inline_button_extra_user_profile,
}


def _extract_reply_markup(message) -> dict[str, Any] | None:
    """Extract and serialize reply markup from a message if present."""
    reply_markup = getattr(message, "reply_markup", None)
    if not reply_markup:
        return None

    markup_class = reply_markup.__class__.__name__

    if markup_class == "ReplyKeyboardMarkup":
        rows = []
        if hasattr(reply_markup, "rows"):
            for row in reply_markup.rows:
                row_buttons = []
                if hasattr(row, "buttons"):
                    row_buttons.extend(
                        {"text": getattr(button, "text", "")} for button in row.buttons
                    )
                rows.append(row_buttons)

        return {
            "type": "keyboard",
            "rows": rows,
            "resize": getattr(reply_markup, "resize", None),
            "single_use": getattr(reply_markup, "single_use", None),
            "selective": getattr(reply_markup, "selective", None),
            "persistent": getattr(reply_markup, "persistent", None),
            "placeholder": getattr(reply_markup, "placeholder", None),
        }

    if markup_class == "ReplyInlineMarkup":
        rows = []
        if hasattr(reply_markup, "rows"):
            for row in reply_markup.rows:
                row_buttons = []
                if hasattr(row, "buttons"):
                    for button in row.buttons:
                        text = getattr(button, "text", "")
                        btn_cls = button.__class__.__name__
                        serializer = _INLINE_BUTTON_SERIALIZERS.get(btn_cls)
                        extra = (
                            serializer(button) if serializer else {"type": "unknown"}
                        )
                        row_buttons.append({"text": text, **extra})
                rows.append(row_buttons)

        return {
            "type": "inline",
            "rows": rows,
        }

    if markup_class == "ReplyKeyboardForceReply":
        return {
            "type": "force_reply",
            "selective": getattr(reply_markup, "selective", None),
            "placeholder": getattr(reply_markup, "placeholder", None),
        }

    if markup_class == "ReplyKeyboardHide":
        return {
            "type": "hide",
            "selective": getattr(reply_markup, "selective", None),
        }

    return {
        "type": "unknown",
        "class": markup_class,
    }


def build_send_edit_result(
    message,
    chat,
    status: str,
    *,
    rich_format: str | None = None,
) -> dict[str, Any]:
    """Build a consistent result dictionary for send/edit operations."""
    chat_dict = build_entity_dict(chat)
    sender_dict = build_entity_dict(getattr(message, "sender", None))

    rich_message = getattr(message, "rich_message", None)
    rich_cache = (
        flatten_rich_message(rich_message) if rich_message is not None else None
    )
    text = _resolve_message_text(message, rich_cache=rich_cache)

    result: dict[str, Any] = {
        "message_id": message.id,
        "date": message.date.isoformat(),
        "text": text,
        "status": status,
    }

    if rich_message is not None:
        result["rich"] = True
    if rich_format is not None:
        result["rich_format"] = rich_format

    if chat_dict is not None:
        result["chat"] = chat_dict
    if sender_dict is not None:
        result["sender"] = sender_dict

    if status == "edited" and hasattr(message, "edit_date") and message.edit_date:
        result["edit_date"] = message.edit_date.isoformat()

    reply_markup = _extract_reply_markup(message)
    if reply_markup is not None:
        result["reply_markup"] = reply_markup

    return result


async def get_sender_info(message) -> dict[str, Any] | None:
    """Build sender entity dict from a Telethon message.

    Uses ``message.get_sender()`` which returns the sender cached by
    ``iter_messages`` — no extra Telegram API call in the common case.
    """
    if hasattr(message, "sender_id") and message.sender_id:
        try:
            sender = await message.get_sender()
            if sender:
                return build_entity_dict(sender)
            return {"id": message.sender_id, "error": "Sender not found"}
        except Exception:
            return {"id": message.sender_id, "error": "Failed to retrieve sender"}
    return None


def _document_duration_and_filename(document) -> tuple[int | None, str | None]:
    """Duration and filename from document.attributes (audio/video and filename attrs)."""
    duration = None
    filename = None
    for attr in getattr(document, "attributes", []) or []:
        ac = attr.__class__.__name__
        if ac in ("DocumentAttributeAudio", "DocumentAttributeVideo"):
            if hasattr(attr, "duration"):
                duration = attr.duration
        elif hasattr(attr, "file_name") and attr.file_name:
            filename = attr.file_name
    return duration, filename


def _apply_document_mime_and_size(placeholder: dict[str, Any], document) -> None:
    if mime_type := getattr(document, "mime_type", None):
        placeholder["mime_type"] = mime_type
    file_size = getattr(document, "size", None)
    if file_size is not None:
        placeholder["approx_size_bytes"] = file_size


def _fill_document_media_placeholder(placeholder: dict[str, Any], document) -> None:
    """Populate placeholder fields for MessageMediaDocument (voice note, round video, file)."""
    is_voice, is_round_video = _document_voice_and_round_note_flags(document)
    duration, filename = _document_duration_and_filename(document)
    if filename:
        placeholder["filename"] = filename
    if is_voice:
        placeholder["type"] = "voice"
    elif is_round_video:
        placeholder["type"] = "round_video"
    if (is_voice or is_round_video) and duration is not None:
        placeholder["duration_seconds"] = duration
    _apply_document_mime_and_size(placeholder, document)


def _todo_completed_by_to_int(completed_by) -> int | None:
    """Convert TL completed_by (int or Peer) to a plain Telegram id for JSON tool output."""
    if completed_by is None:
        return None
    if isinstance(completed_by, int):
        return completed_by
    peer_id, _label = _forward_peer_id_and_type_label(completed_by)
    return peer_id if isinstance(peer_id, int) else None


def _fill_todo_media_placeholder(placeholder: dict[str, Any], media, todo_list) -> None:
    """Populate placeholder fields for MessageMediaToDo."""
    placeholder["type"] = "todo"
    title_obj = getattr(todo_list, "title", None)
    if title_obj and hasattr(title_obj, "text"):
        placeholder["title"] = title_obj.text

    items = getattr(todo_list, "list", [])
    if not isinstance(items, list):
        items = []
    placeholder["items"] = []
    for item in items:
        item_dict = {
            "id": getattr(item, "id", 0),
            "text": getattr(getattr(item, "title", None), "text", ""),
            "completed": False,
        }
        placeholder["items"].append(item_dict)

    completions = getattr(media, "completions", [])
    if not isinstance(completions, list):
        completions = []
    for completion in completions:
        item_id = getattr(completion, "id", None)
        completed_by = getattr(completion, "completed_by", None)
        completed_at = getattr(completion, "date", None)

        for pl_item in placeholder["items"]:
            if pl_item["id"] == item_id:
                pl_item["completed"] = True
                if completed_by is not None:
                    cid = _todo_completed_by_to_int(completed_by)
                    if cid is not None:
                        pl_item["completed_by"] = cid
                if completed_at is not None:
                    pl_item["completed_at"] = completed_at.isoformat()
                break


def _fill_poll_media_placeholder(placeholder: dict[str, Any], poll, results) -> None:
    """Populate placeholder fields for MessageMediaPoll."""
    placeholder["type"] = "poll"

    question_obj = getattr(poll, "question", None)
    if question_obj and hasattr(question_obj, "text"):
        placeholder["question"] = question_obj.text

    answers = getattr(poll, "answers", [])
    placeholder["options"] = []
    for answer in answers:
        option_dict = {
            "text": getattr(getattr(answer, "text", None), "text", ""),
            "voters": 0,
            "chosen": getattr(answer, "chosen", False),
            "correct": getattr(answer, "correct", False),
        }
        placeholder["options"].append(option_dict)

    if results and hasattr(results, "results"):
        result_counts = getattr(results, "results", [])
        for result in result_counts:
            voters = getattr(result, "voters", 0)
            for option in placeholder["options"]:
                if option["voters"] == 0:
                    option["voters"] = voters
                    break

    placeholder["total_voters"] = getattr(results, "total_voters", 0) if results else 0
    placeholder["closed"] = getattr(poll, "closed", False)
    placeholder["public_voters"] = getattr(poll, "public_voters", True)
    placeholder["multiple_choice"] = getattr(poll, "multiple_choice", False)
    placeholder["quiz"] = getattr(poll, "quiz", False)


def _fill_geo_media_placeholder(placeholder: dict[str, Any], geo) -> None:
    """Add latitude/longitude from a MessageMediaGeo(Point) when present."""
    if not geo:
        return
    lat = getattr(geo, "lat", None)
    long = getattr(geo, "long", None)
    if lat is not None:
        placeholder["latitude"] = lat
    if long is not None:
        placeholder["longitude"] = long


def _build_media_placeholder(message) -> dict[str, Any] | None:
    """Return a lightweight, serializable media placeholder for LLM consumption.

    Avoids returning raw Telethon media objects which are large and not LLM-friendly.

    Every class in ``_KNOWN_MEDIA_CLASSES`` yields at least ``{"type": ...}``: a
    message that passes ``message_has_displayable_content()`` must never come back
    with an empty placeholder. That invariant is what keeps the filter and this
    formatter from contradicting each other (issue #159).
    """
    media = getattr(message, "media", None)
    if not media:
        return None

    class_name = media.__class__.__name__
    placeholder: dict[str, Any] = {}

    # Seed the canonical type from the table so every known class yields a
    # non-empty placeholder. MessageMediaDocument refines this to "voice" /
    # "round_video" inside the filler when the document says so.
    if type_name := _MEDIA_TYPES.get(class_name):
        placeholder["type"] = type_name

    match class_name:
        case "MessageMediaDocument":
            if document := getattr(media, "document", None):
                _fill_document_media_placeholder(placeholder, document)

        case "MessageMediaPhoto":
            ph = getattr(media, "photo", None)
            if (
                ph
                and getattr(ph, "sizes", None)
                and (
                    sized := [
                        s
                        for s in ph.sizes
                        if getattr(s, "size", None) is not None
                        and type(s).__name__ != "PhotoStrippedSize"
                    ]
                )
            ):
                largest = max(sized, key=lambda s: getattr(s, "size", 0))
                placeholder["approx_size_bytes"] = largest.size
            placeholder.setdefault("mime_type", "image/jpeg")

        case "MessageMediaToDo":
            if todo_list := getattr(media, "todo", None):
                _fill_todo_media_placeholder(placeholder, media, todo_list)

        case "MessageMediaPoll":
            poll = getattr(media, "poll", None)
            results = getattr(media, "results", None)
            if poll:
                _fill_poll_media_placeholder(placeholder, poll, results)

        case "MessageMediaContact":
            # Names only. `phone_number` and `vcard` are deliberately NOT
            # serialized: formatted output carries names, matching
            # `build_entity_dict()`, and phone data is stripped by default (#156).
            for key in ("first_name", "last_name", "user_id"):
                if (value := getattr(media, key, None)) is not None:
                    placeholder[key] = value

        case "MessageMediaGeo":
            _fill_geo_media_placeholder(placeholder, getattr(media, "geo", None))

        case "MessageMediaGeoLive":
            _fill_geo_media_placeholder(placeholder, getattr(media, "geo", None))
            if (period := getattr(media, "period", None)) is not None:
                placeholder["period_seconds"] = period

        case "MessageMediaVenue":
            for key in ("title", "address", "provider", "venue_id", "venue_type"):
                if (value := getattr(media, key, None)) is not None:
                    placeholder[key] = value
            _fill_geo_media_placeholder(placeholder, getattr(media, "geo", None))

        case "MessageMediaDice":
            for key in ("emoticon", "value"):
                if (value := getattr(media, key, None)) is not None:
                    placeholder[key] = value

        case "MessageMediaGame":
            game = getattr(media, "game", None)
            for key in ("title", "short_name"):
                if (value := getattr(game, key, None)) is not None:
                    placeholder[key] = value

        case "MessageMediaInvoice":
            for key in ("title", "description", "currency", "total_amount"):
                if (value := getattr(media, key, None)) is not None:
                    placeholder[key] = value

        case "MessageMediaWebPage":
            webpage = getattr(media, "webpage", None)
            for key in ("url", "display_url", "title", "site_name"):
                if (value := getattr(webpage, key, None)) is not None:
                    placeholder[key] = value

        case "MessageMediaPaidMedia":
            if (stars := getattr(media, "stars_amount", None)) is not None:
                placeholder["stars_amount"] = stars

        case "MessageMediaStory":
            if (story_id := getattr(media, "id", None)) is not None:
                placeholder["story_id"] = story_id

        case _:
            if mime_type := getattr(media, "mime_type", None):
                placeholder["mime_type"] = mime_type

            file_size = getattr(media, "size", None)
            if file_size is not None:
                placeholder["approx_size_bytes"] = file_size

    return placeholder or None


def extract_topic_metadata(message: Any) -> dict[str, Any]:
    """Extract topic_id from a Telegram message reply_to metadata."""
    reply_to = getattr(message, "reply_to", None)
    reply_to_msg_id = getattr(message, "reply_to_msg_id", None) or getattr(
        reply_to, "reply_to_msg_id", None
    )
    forum_topic = bool(getattr(reply_to, "forum_topic", False))
    reply_to_top_id = getattr(reply_to, "reply_to_top_id", None)
    topic_id = reply_to_top_id or (reply_to_msg_id if forum_topic else None)
    # Raw int here: this is an INTERNAL helper also consumed by the forum/thread
    # search path (SearchRequest.top_msg_id, GetForumTopicsByIDRequest), which
    # needs the int. Output stringification happens at the response boundary in
    # build_message_result.
    return {"topic_id": topic_id} if topic_id is not None else {}


async def build_message_result(
    message, entity_or_chat, link: str | None, include_chat_entity: bool = False
) -> dict[str, Any]:
    sender = await get_sender_info(message)
    chat = build_entity_dict(entity_or_chat)
    forward_info = await _extract_forward_info(message)

    rich_message = getattr(message, "rich_message", None)
    rich_cache = flatten_rich_message(rich_message) if rich_message is not None else None
    full_text = _resolve_message_text(message, rich_cache=rich_cache)

    result: dict[str, Any] = {
        "id": message.id,
        "date": message.date.isoformat() if getattr(message, "date", None) else None,
        "text": full_text,
        "link": link,
        "sender": sender,
    }

    if rich_message is not None:
        result["rich"] = True

    if include_chat_entity:
        result["chat"] = chat

    reply_to_msg_id = getattr(message, "reply_to_msg_id", None) or getattr(
        getattr(message, "reply_to", None), "reply_to_msg_id", None
    )
    if reply_to_msg_id is not None:
        result["reply_to_msg_id"] = reply_to_msg_id

    # Topic metadata: derived from reply_to.forum_topic (set on forum thread messages).
    result |= extract_topic_metadata(message)

    chat_id = chat.get("id") if chat else None

    if rich_cache is not None:
        _, media_refs = rich_cache
        rich_attachments = build_rich_attachment_placeholders(rich_message, media_refs)
        if rich_attachments:
            await _maybe_set_rich_attachment_download_urls(
                rich_attachments, message, chat_id
            )
            result["attachments"] = rich_attachments
            result["media"] = rich_attachments[0]

    if hasattr(message, "media") and message.media:
        media_placeholder = _build_media_placeholder(message)
        if media_placeholder is not None:
            result["media"] = media_placeholder
            await _maybe_set_attachment_download_url(
                result["media"], message, chat_id
            )

    if forward_info is not None:
        result["forwarded_from"] = forward_info

    reply_markup = _extract_reply_markup(message)
    if reply_markup is not None:
        result["reply_markup"] = reply_markup

    return result
