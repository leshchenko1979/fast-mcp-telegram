import asyncio
import logging
from typing import Any

from telethon.errors import RPCError
from telethon.tl.functions.messages import TranscribeAudioRequest

from src.client.connection import get_connected_client
from src.utils.entity import _extract_forward_info, build_entity_dict, get_entity_by_id

logger = logging.getLogger(__name__)


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
            # Check if it's a voice message or round video via attributes
            is_voice = False
            is_round_video = False
            duration = None

            if hasattr(document, "attributes"):
                for attr in document.attributes:
                    attr_cls = attr.__class__.__name__
                    if attr_cls == "DocumentAttributeAudio":
                        if getattr(attr, "voice", False):
                            is_voice = True
                        if hasattr(attr, "duration"):
                            duration = attr.duration
                    elif attr_cls == "DocumentAttributeVideo":
                        if getattr(attr, "round_message", False):
                            is_round_video = True
                        if hasattr(attr, "duration"):
                            duration = attr.duration
                    elif hasattr(attr, "file_name") and attr.file_name:
                        placeholder["filename"] = attr.file_name

            if is_voice:
                placeholder["type"] = "voice"
                if duration is not None:
                    placeholder["duration_seconds"] = duration

            elif is_round_video:
                placeholder["type"] = "round_video"
                if duration is not None:
                    placeholder["duration_seconds"] = duration

            # Get mime_type and file_size from document object
            mime_type = getattr(document, "mime_type", None)
            if mime_type:
                placeholder["mime_type"] = mime_type

            file_size = getattr(document, "size", None)
            if file_size is not None:
                placeholder["approx_size_bytes"] = file_size

    # Handle Voice Messages
    elif media_cls == "MessageMediaVoice":
        placeholder["type"] = "voice"
        # Extract duration from the document
        document = getattr(media, "document", None)
        if document and hasattr(document, "attributes"):
            # Duration is stored in document attributes
            for attr in document.attributes:
                if hasattr(attr, "duration") and attr.duration is not None:
                    placeholder["duration_seconds"] = attr.duration
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


class PremiumRequiredError(Exception):
    """Exception raised when transcription fails due to non-premium account."""


async def _is_user_premium(client) -> bool:
    """Check if the current user has Telegram Premium."""
    try:
        me = await client.get_me()
        return bool(getattr(me, "premium", False))
    except Exception as e:
        logger.warning(f"Failed to check user premium status: {e}")
        return False


async def _transcribe_single_voice_message(
    client, chat_entity, message_id: int
) -> str | None:
    """
    Transcribe a single voice message.

    Returns the transcription text, or raises PremiumRequiredError if account lacks premium.
    Returns None if transcription fails for other reasons.

    If transcription is pending, polls until completion.
    """
    try:
        result = await client(
            TranscribeAudioRequest(peer=chat_entity, msg_id=message_id)
        )

        # If transcription is already complete, return it
        if (
            hasattr(result, "text")
            and result.text
            and not getattr(result, "pending", False)
        ):
            return result.text

        # If transcription is pending, poll until it's ready
        if (
            hasattr(result, "pending")
            and result.pending
            and hasattr(result, "transcription_id")
        ):
            transcription_id = result.transcription_id
            logger.debug(
                f"Transcription pending for message {message_id}, polling for completion..."
            )

            # Poll for completion (up to 30 seconds with 1-second intervals)
            max_attempts = 30
            for attempt in range(max_attempts):
                await asyncio.sleep(1)  # Wait 1 second between polls

                try:
                    # Poll by calling transcribeAudio again with the same parameters
                    poll_result = await client(
                        TranscribeAudioRequest(peer=chat_entity, msg_id=message_id)
                    )

                    # Check if this is the same transcription (matching transcription_id)
                    if (
                        hasattr(poll_result, "transcription_id")
                        and poll_result.transcription_id == transcription_id
                    ):
                        if hasattr(poll_result, "pending") and poll_result.pending:
                            # Still pending, continue polling
                            continue
                        if hasattr(poll_result, "text") and poll_result.text:
                            # Transcription completed
                            logger.debug(
                                f"Transcription completed for message {message_id} after {attempt + 1} polls"
                            )
                            return poll_result.text
                        # Unexpected state
                        logger.warning(
                            f"Unexpected transcription state for message {message_id}"
                        )
                        return None

                except Exception as poll_error:
                    logger.warning(
                        f"Error polling transcription for message {message_id}: {poll_error}"
                    )
                    return None

            # Timeout after max attempts
            logger.warning(
                f"Transcription polling timeout for message {message_id} after {max_attempts} attempts"
            )
            return None

        # No transcription available
        logger.debug(f"No transcription available for message {message_id}")
        return None

    except RPCError as e:
        error_msg = str(e).lower()
        if "premium" in error_msg and "required" in error_msg:
            raise PremiumRequiredError(
                f"Premium account required for transcription: {e}"
            ) from None
        logger.warning(f"Transcription failed for message {message_id}: {e}")
        return None
    except Exception as e:
        logger.warning(
            f"Unexpected error during transcription of message {message_id}: {e}"
        )
        return None


async def transcribe_voice_messages(
    messages: list[dict[str, Any]], chat_entity
) -> None:
    """
    Transcribe voice messages in the results list for premium accounts.

    Args:
        messages: List of message result dictionaries
        chat_entity: The chat entity containing the messages

    This function:
    - Checks if the user has Telegram Premium before attempting transcription
    - Runs transcriptions in parallel using asyncio.TaskGroup
    - Cancels all transcription tasks if any fails with PremiumRequiredError
    - Updates message results with transcription text when available
    """

    client = await get_connected_client()

    # Check if user has premium before attempting transcription
    is_premium = await _is_user_premium(client)

    if not is_premium:
        logger.debug(
            "Skipping voice transcription - user does not have Telegram Premium"
        )
        return

    # Find voice messages that need transcription
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

    logger.debug(f"Found {len(voice_messages)} voice messages to transcribe")

    async def transcribe_task(msg_dict: dict[str, Any]):
        """Transcribe a single voice message and update the result dict."""
        message_id = msg_dict["id"]
        transcription = await _transcribe_single_voice_message(
            client, chat_entity, message_id
        )
        if transcription:
            msg_dict["transcription"] = transcription
            logger.debug(
                f"Transcribed voice message {message_id}: {transcription[:50]}..."
            )

    # Run transcriptions in parallel with cancellation on premium requirement
    try:
        async with asyncio.TaskGroup() as tg:
            for msg_dict in voice_messages:
                tg.create_task(transcribe_task(msg_dict))
    except ExceptionGroup as eg:
        # Check if it's a PremiumRequiredError group
        premium_errors = [
            e for e in eg.exceptions if isinstance(e, PremiumRequiredError)
        ]
        if premium_errors:
            # One or more transcriptions failed due to non-premium account
            # This shouldn't happen if we checked premium status correctly, but handle it gracefully
            logger.info(
                "Voice transcription cancelled - account lacks premium despite initial check"
            )
            # All other transcription tasks are automatically cancelled by TaskGroup
        else:
            # Re-raise non-premium related exception groups
            raise
    except Exception as e:
        logger.warning(f"Voice transcription failed with unexpected error: {e}")
        # Continue without transcription rather than failing the entire operation
