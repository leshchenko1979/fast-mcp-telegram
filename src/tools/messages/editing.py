"""Message editing functionality."""

from __future__ import annotations

import logging
from typing import Any, cast

from telethon.errors import MessageEditTimeExpiredError, MessageIdInvalidError
from telethon.tl import functions

from src.client.connection import get_connected_client
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.rich_send import RichFormat, edit_rich_via_tl
from src.utils.datetime_parse import format_schedule_date, parse_schedule_date
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_send_edit_result, extract_topic_metadata

logger = logging.getLogger(__name__)


async def _find_queued_message(client: Any, entity: Any, message_id: int) -> Any | None:
    """Return the queued (scheduled) message with this id, or ``None``.

    ``messages.getMessages`` cannot see the scheduled queue; only
    ``messages.getScheduledMessages`` addresses it.
    """
    input_peer = await client.get_input_entity(entity)
    result = await client(
        functions.messages.GetScheduledMessagesRequest(peer=input_peer, id=[message_id])
    )
    for message in getattr(result, "messages", None) or []:
        if getattr(message, "id", None) == message_id:
            return message
    return None


def _queued_timestamp(message: Any) -> int | None:
    """Read a queued message's own ``schedule_date`` back as a unix timestamp."""
    date = getattr(message, "date", None)
    if date is None:
        return None
    return int(date.timestamp())


async def _refetch_scheduled_message(client: Any, entity: Any, message_id: int) -> Any:
    """Read one queued message back by id.

    ``client.edit_message`` returns ``None`` when it edits a *scheduled* message:
    Telegram answers with ``UpdateNewScheduledMessage`` alone, and Telethon's
    ``_get_response_message`` can only map that update back to the request
    through ``UpdateMessageID``/``random_id``, which ``messages.editMessage``
    never carries.
    """
    message = await _find_queued_message(client, entity, message_id)
    if message is None:
        raise RuntimeError(
            f"Telegram accepted the scheduled edit but message id={message_id} "
            "is no longer in the scheduled queue"
        )
    return message


async def _apply_edit(
    client: Any,
    chat: Any,
    message_id: int,
    new_text: str,
    resolved_parse_mode: str | None,
    schedule_timestamp: int | None,
) -> tuple[Any, RichFormat | None]:
    """Run one edit attempt and return ``(message, rich_format)``."""
    if resolved_parse_mode == "rich":
        return await edit_rich_via_tl(
            client,
            chat,
            message_id,
            new_text,
            schedule_date=schedule_timestamp,
        )

    edited_message = await client.edit_message(
        entity=chat,
        message=message_id,
        text=new_text,
        parse_mode=cast(Any, resolved_parse_mode or None),
        schedule=schedule_timestamp,
    )
    if edited_message is None:
        if schedule_timestamp is not None:
            # Rescheduling answers with UpdateNewScheduledMessage only, which
            # Telethon cannot map back to the request — read it from the
            # scheduled queue instead.
            edited_message = await _refetch_scheduled_message(client, chat, message_id)
        else:
            raise RuntimeError(
                f"Telegram returned no message for the edit of id={message_id}"
            )
    return edited_message, None


async def edit_message_impl(
    chat_id: str,
    message_id: int,
    new_text: str,
    parse_mode: str | None = None,
    schedule_date: str | None = None,
) -> dict[str, Any]:
    """
    Edit an existing message, or reschedule one that is still queued.

    Args:
        chat_id: The ID of the chat containing the message
        message_id: ID of the message to edit
        new_text: The new text content
        parse_mode: Parse mode ('markdown', 'html', 'auto', or 'rich')
        schedule_date: ISO 8601 instant. Reschedules an already-queued message
            (Telegram's ``messages.editMessage`` ``schedule_date``); it does not
            turn a delivered message into a scheduled one. When omitted, a
            queued message is still editable: its own date is read back from the
            scheduled queue and reused, so the text changes and the time does
            not.
    """
    parse_mode = _normalize_parse_mode(parse_mode)
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "new_text": new_text,
        "new_text_length": len(new_text),
        "parse_mode": parse_mode,
        "schedule_date": schedule_date,
    }

    resolved_parse_mode = parse_mode
    if parse_mode == "auto":
        resolved_parse_mode = detect_message_formatting(new_text)
        params["detected_parse_mode"] = resolved_parse_mode

    log_operation_start("Editing message in chat", params)

    try:
        schedule_timestamp = parse_schedule_date(schedule_date)
    except ValueError as e:
        return log_and_build_error(
            operation="edit_message",
            error_message=str(e),
            params=params,
            exception=e,
        )

    client = await get_connected_client()
    try:
        chat = await get_entity_by_id(chat_id)
        if not chat:
            return log_and_build_error(
                operation="edit_message",
                error_message=f"Cannot find chat with ID '{chat_id}'",
                params=params,
                exception=ValueError(
                    f"Cannot find any entity corresponding to '{chat_id}'"
                ),
            )

        try:
            edited_message, rich_format = await _apply_edit(
                client,
                chat,
                message_id,
                new_text,
                resolved_parse_mode,
                schedule_timestamp,
            )
        except MessageEditTimeExpiredError:
            # Telegram only searches *delivered* history when ``schedule_date``
            # is absent, so a queued id comes back as MESSAGE_EDIT_TIME_EXPIRED
            # — a lie, since nothing expired. Retry once against the queue's own
            # date: same instant, new text. A genuinely old delivered message
            # stays expired and re-raises below.
            if schedule_timestamp is not None:
                raise
            queued = await _find_queued_message(client, chat, message_id)
            queued_timestamp = _queued_timestamp(queued) if queued is not None else None
            if queued_timestamp is None:
                raise
            schedule_timestamp = queued_timestamp
            params["schedule_date"] = format_schedule_date(schedule_timestamp)
            params["schedule_date_source"] = "scheduled_queue"
            edited_message, rich_format = await _apply_edit(
                client,
                chat,
                message_id,
                new_text,
                resolved_parse_mode,
                schedule_timestamp,
            )
        except MessageIdInvalidError:
            # The reverse case: a delivered message cannot be un-sent. Telegram
            # says only "the specified message ID is invalid or you can't do
            # that operation on such message", which names neither cause.
            if schedule_timestamp is None:
                raise
            raise ValueError(
                f"Cannot reschedule message id={message_id}: only a queued "
                "(scheduled) message can be rescheduled. A delivered message "
                "cannot be un-sent, and an unknown id has nothing to move."
            ) from None

        status = "scheduled" if schedule_timestamp is not None else "edited"
        result = build_send_edit_result(
            edited_message, chat, status, rich_format=rich_format
        )
        if schedule_timestamp is not None:
            result["scheduled"] = True
            result["schedule_date"] = format_schedule_date(schedule_timestamp)
        result |= extract_topic_metadata(edited_message)

        log_operation_success(
            "Scheduled message rescheduled"
            if schedule_timestamp is not None
            else "Message edited",
            chat_id,
        )
        return result

    except Exception as e:
        return log_and_build_error(
            operation="edit_message",
            error_message=f"Failed to edit message: {e!s}",
            params=params,
            exception=e,
        )
