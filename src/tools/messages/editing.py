"""Message editing functionality."""

from __future__ import annotations

import logging
from typing import Any, cast

from telethon.tl import functions

from src.client.connection import get_connected_client
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.rich_send import edit_rich_via_tl
from src.utils.datetime_parse import format_schedule_date, parse_schedule_date
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_send_edit_result, extract_topic_metadata

logger = logging.getLogger(__name__)


async def _refetch_scheduled_message(client: Any, entity: Any, message_id: int) -> Any:
    """Read one queued message back by id.

    ``client.edit_message`` returns ``None`` when it edits a *scheduled* message:
    Telegram answers with ``UpdateNewScheduledMessage`` alone, and Telethon's
    ``_get_response_message`` can only map that update back to the request
    through ``UpdateMessageID``/``random_id``, which ``messages.editMessage``
    never carries. ``messages.getMessages`` cannot see the queue either — only
    ``messages.getScheduledMessages`` addresses it.
    """
    input_peer = await client.get_input_entity(entity)
    result = await client(
        functions.messages.GetScheduledMessagesRequest(peer=input_peer, id=[message_id])
    )
    for message in getattr(result, "messages", None) or []:
        if getattr(message, "id", None) == message_id:
            return message
    raise RuntimeError(
        f"Telegram accepted the scheduled edit but message id={message_id} "
        "is no longer in the scheduled queue"
    )


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
            turn a delivered message into a scheduled one.
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

        rich_format = None
        if resolved_parse_mode == "rich":
            edited_message, rich_format = await edit_rich_via_tl(
                client,
                chat,
                message_id,
                new_text,
                schedule_date=schedule_timestamp,
            )
        else:
            edited_message = await client.edit_message(
                entity=chat,
                message=message_id,
                text=new_text,
                parse_mode=cast(Any, resolved_parse_mode or None),
                schedule=schedule_timestamp,
            )
            if edited_message is None:
                if schedule_timestamp is not None:
                    # Rescheduling answers with UpdateNewScheduledMessage only,
                    # which Telethon cannot map back to the request — read it
                    # from the scheduled queue instead.
                    edited_message = await _refetch_scheduled_message(
                        client, chat, message_id
                    )
                else:
                    raise RuntimeError(
                        f"Telegram returned no message for the edit of id={message_id}"
                    )

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
