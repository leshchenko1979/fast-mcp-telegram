from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from telethon.errors import RPCError
from telethon.tl.functions.messages import TranscribeAudioRequest

from src.client.connection import get_connected_client, get_request_token
from src.config.server_config import get_config
from src.server_components.attachment_tickets import mint_attachment_ticket
from src.utils.entity import _extract_forward_info, build_entity_dict, get_entity_by_id

logger = logging.getLogger(__name__)

_KNOWN_MEDIA_CLASSES = frozenset(
    {
        "MessageMediaPhoto",
        "MessageMediaDocument",
        "MessageMediaAudio",
        "MessageMediaVoice",
        "MessageMediaVideo",
        "MessageMediaWebPage",
        "MessageMediaGeo",
        "MessageMediaContact",
        "MessageMediaPoll",
        "MessageMediaDice",
        "MessageMediaVenue",
        "MessageMediaGame",
        "MessageMediaInvoice",
        "MessageMediaToDo",
        "MessageMediaUnsupported",
    }
)


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


def _message_supports_streaming_attachment(message) -> bool:
    """Whether attachment HTTP streaming is supported for this message (documents, photos)."""
    media = getattr(message, "media", None)
    if not media:
        return False
    media_cls = media.__class__.__name__
    if media_cls == "MessageMediaPhoto":
        return True
    if media_cls == "MessageMediaDocument":
        document = getattr(media, "document", None)
        if not document:
            return False
        is_voice, is_round_video = _document_voice_and_round_note_flags(document)
        return not (is_voice or is_round_video)
    return False


async def _maybe_set_attachment_download_url(
    media_dict: dict[str, Any],
    message,
    chat_id: int | None,
) -> None:
    """Set media['attachment_download_url'] when HTTP mode and DOMAIN resolves to a public origin."""
    if chat_id is None:
        return
    cfg = get_config()
    if cfg.transport != "http" or not cfg.public_base_url_normalized:
        return
    if not _message_supports_streaming_attachment(message):
        return

    session_token = get_request_token()
    if session_token is None:
        session_token = cfg.session_name

    filename = media_dict.get("filename")
    mime_type = media_dict.get("mime_type")
    tid = await mint_attachment_ticket(
        session_token,
        int(chat_id),
        int(message.id),
        filename=filename if isinstance(filename, str) else None,
        mime_type=mime_type if isinstance(mime_type, str) else None,
    )
    base = cfg.public_base_url_normalized
    media_dict["attachment_download_url"] = f"{base}/v1/attachments/{tid}"


def _has_any_media(message) -> bool:
    """Check if message contains any type of media content."""
    if not hasattr(message, "media") or message.media is None:
        return False
    return message.media.__class__.__name__ in _KNOWN_MEDIA_CLASSES


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

    if status == "edited" and hasattr(message, "edit_date") and message.edit_date:
        result["edit_date"] = message.edit_date.isoformat()

    reply_markup = _extract_reply_markup(message)
    if reply_markup is not None:
        result["reply_markup"] = reply_markup

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


def _first_document_attribute_duration(document) -> int | None:
    return next(
        (
            attr.duration
            for attr in getattr(document, "attributes", []) or []
            if hasattr(attr, "duration") and attr.duration is not None
        ),
        None,
    )


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
                    pl_item["completed_by"] = completed_by
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


def _build_media_placeholder(message) -> dict[str, Any] | None:
    """Return a lightweight, serializable media placeholder for LLM consumption.

    Avoids returning raw Telethon media objects which are large and not LLM-friendly.
    """
    media = getattr(message, "media", None)
    if not media:
        return None

    placeholder: dict[str, Any] = {}

    match media.__class__.__name__:
        case "MessageMediaDocument":
            if document := getattr(media, "document", None):
                _fill_document_media_placeholder(placeholder, document)

        case "MessageMediaPhoto":
            placeholder["type"] = "photo"
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

        case "MessageMediaVoice":
            placeholder["type"] = "voice"
            if document := getattr(media, "document", None):
                dur = _first_document_attribute_duration(document)
                if dur is not None:
                    placeholder["duration_seconds"] = dur

        case "MessageMediaToDo":
            if todo_list := getattr(media, "todo", None):
                _fill_todo_media_placeholder(placeholder, media, todo_list)

        case "MessageMediaPoll":
            poll = getattr(media, "poll", None)
            results = getattr(media, "results", None)
            if poll:
                _fill_poll_media_placeholder(placeholder, poll, results)

        case _:
            if mime_type := getattr(media, "mime_type", None):
                placeholder["mime_type"] = mime_type

            file_size = getattr(media, "size", None)
            if file_size is not None:
                placeholder["approx_size_bytes"] = file_size

    return placeholder or None


def _extract_topic_metadata(message: Any) -> dict[str, Any]:
    """Extract topic_id from a Telegram message reply_to metadata."""
    reply_to = getattr(message, "reply_to", None)
    reply_to_msg_id = getattr(message, "reply_to_msg_id", None) or getattr(
        reply_to, "reply_to_msg_id", None
    )
    forum_topic = bool(getattr(reply_to, "forum_topic", False))
    reply_to_top_id = getattr(reply_to, "reply_to_top_id", None)
    topic_id = reply_to_top_id or (reply_to_msg_id if forum_topic else None)
    return {"topic_id": topic_id} if topic_id is not None else {}


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

    # Topic metadata: derived from reply_to.forum_topic (set on forum thread messages).
    result |= _extract_topic_metadata(message)

    if hasattr(message, "media") and message.media:
        media_placeholder = _build_media_placeholder(message)
        if media_placeholder is not None:
            result["media"] = media_placeholder
            await _maybe_set_attachment_download_url(
                result["media"], message, chat.get("id") if chat else None
            )

    if forward_info is not None:
        result["forwarded_from"] = forward_info

    reply_markup = _extract_reply_markup(message)
    if reply_markup is not None:
        result["reply_markup"] = reply_markup

    return result


class PremiumRequiredError(Exception):
    """Exception raised when transcription fails due to non-premium account."""


async def _is_user_premium(client) -> bool:
    """Check if the current user has Telegram Premium."""
    try:
        me = await client.get_me()
        return bool(getattr(me, "premium", False))
    except Exception as e:
        logger.warning("Failed to check user premium status: %s", e)
        return False


async def _transcribe_single_voice_message(
    client, chat_entity, message_id: int
) -> str | None:
    """Transcribe a single voice message; poll when pending. Raises PremiumRequiredError if required."""
    try:
        result = await client(
            TranscribeAudioRequest(peer=chat_entity, msg_id=message_id)
        )

        if (
            hasattr(result, "text")
            and result.text
            and not getattr(result, "pending", False)
        ):
            return result.text

        if (
            hasattr(result, "pending")
            and result.pending
            and hasattr(result, "transcription_id")
        ):
            transcription_id = result.transcription_id
            logger.debug(
                "Transcription pending for message %s, polling for completion...",
                message_id,
            )

            max_attempts = 30
            for attempt in range(max_attempts):
                await asyncio.sleep(1)

                try:
                    poll_result = await client(
                        TranscribeAudioRequest(peer=chat_entity, msg_id=message_id)
                    )

                    if (
                        hasattr(poll_result, "transcription_id")
                        and poll_result.transcription_id == transcription_id
                    ):
                        if hasattr(poll_result, "pending") and poll_result.pending:
                            continue
                        if hasattr(poll_result, "text") and poll_result.text:
                            logger.debug(
                                "Transcription completed for message %s after %s polls",
                                message_id,
                                attempt + 1,
                            )
                            return poll_result.text
                        logger.warning(
                            "Unexpected transcription state for message %s", message_id
                        )
                        return None

                except Exception as poll_error:
                    logger.warning(
                        "Error polling transcription for message %s: %s",
                        message_id,
                        poll_error,
                    )
                    return None

            logger.warning(
                "Transcription polling timeout for message %s after %s attempts",
                message_id,
                max_attempts,
            )
            return None

        logger.debug("No transcription available for message %s", message_id)
        return None

    except RPCError as e:
        error_msg = str(e).lower()
        if "premium" in error_msg and "required" in error_msg:
            raise PremiumRequiredError(
                f"Premium account required for transcription: {e}"
            ) from None
        logger.warning("Transcription failed for message %s: %s", message_id, e)
        return None
    except Exception as e:
        logger.warning(
            "Unexpected error during transcription of message %s: %s",
            message_id,
            e,
        )
        return None


async def transcribe_voice_messages(
    messages: list[dict[str, Any]], chat_entity
) -> None:
    """Transcribe voice message dicts in parallel; TaskGroup cancels peers on PremiumRequiredError."""
    client = await get_connected_client()

    is_premium = await _is_user_premium(client)

    if not is_premium:
        logger.debug(
            "Skipping voice transcription - user does not have Telegram Premium"
        )
        return

    voice_messages = []
    for msg in messages:
        media = msg.get("media")
        has_voice_type = (
            media and isinstance(media, dict) and media.get("type") == "voice"
        )
        has_transcription = "transcription" in msg

        if has_voice_type and not has_transcription:
            voice_messages.append(msg)

    if not voice_messages:
        return

    logger.debug("Found %s voice messages to transcribe", len(voice_messages))

    async def transcribe_task(msg_dict: dict[str, Any]) -> None:
        message_id = msg_dict["id"]
        transcription = await _transcribe_single_voice_message(
            client, chat_entity, message_id
        )
        if transcription:
            msg_dict["transcription"] = transcription
            logger.debug(
                "Transcribed voice message %s: %s...",
                message_id,
                transcription[:50],
            )

    try:
        async with asyncio.TaskGroup() as tg:
            for msg_dict in voice_messages:
                tg.create_task(transcribe_task(msg_dict))
    except ExceptionGroup as eg:
        premium_errors = [
            e for e in eg.exceptions if isinstance(e, PremiumRequiredError)
        ]
        if premium_errors:
            logger.info(
                "Voice transcription cancelled - account lacks premium despite initial check"
            )
        else:
            raise
    except Exception as e:
        logger.warning("Voice transcription failed with unexpected error: %s", e)
