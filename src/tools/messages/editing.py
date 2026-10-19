"""Message editing functionality."""

from __future__ import annotations

import logging
from typing import Any, cast

from src.client.connection import get_connected_client
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.drafts import save_draft
from src.tools.messages.rich_send import edit_rich_via_tl
from src.utils.datetime_parse import format_schedule_date, parse_schedule_date
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_send_edit_result, extract_topic_metadata

logger = logging.getLogger(__name__)


async def edit_message_impl(
    chat_id: str,
    message_id: int | None,
    new_text: str,
    parse_mode: str | None = None,
    schedule_date: str | None = None,
    save_as_draft: bool = False,
) -> dict[str, Any]:
    """
    Edit an existing message, reschedule a queued one, or replace the chat's draft.

    Args:
        chat_id: The ID of the chat containing the message
        message_id: ID of the message to edit. Optional only with
            ``save_as_draft=True``, because a draft has no message id.
        new_text: The new text content
        parse_mode: Parse mode ('markdown', 'html', 'auto', or 'rich')
        schedule_date: ISO 8601 instant. Reschedules an already-queued message
            (Telegram's ``messages.editMessage`` ``schedule_date``); it does not
            turn a delivered message into a scheduled one.
        save_as_draft: Replace the chat's draft with ``new_text`` instead of
            editing a message (empty ``new_text`` clears the draft). User sessions
            only — bot accounts cannot call ``messages.saveDraft``.
    """
    parse_mode = _normalize_parse_mode(parse_mode)
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "new_text": new_text,
        "new_text_length": len(new_text),
        "parse_mode": parse_mode,
        "schedule_date": schedule_date,
        "save_as_draft": save_as_draft,
    }

    resolved_parse_mode = parse_mode
    if parse_mode == "auto":
        resolved_parse_mode = detect_message_formatting(new_text)
        params["detected_parse_mode"] = resolved_parse_mode

    log_operation_start("Editing message in chat", params)

    if save_as_draft and schedule_date:
        return log_and_build_error(
            operation="edit_message",
            error_message=(
                "A draft cannot be scheduled: messages.saveDraft has no "
                "schedule_date field. Pass either schedule_date (reschedule a "
                "queued message) or save_as_draft (save for later), not both."
            ),
            params=params,
            exception=ValueError("draft_with_schedule"),
        )

    if save_as_draft and resolved_parse_mode == "rich":
        return log_and_build_error(
            operation="edit_message",
            error_message=(
                "save_as_draft=True cannot be combined with parse_mode='rich': "
                "messages.saveDraft has no rich_message field. Use classic "
                "parse_mode for the draft."
            ),
            params=params,
            exception=ValueError("draft_with_rich"),
        )

    if not save_as_draft and message_id is None:
        return log_and_build_error(
            operation="edit_message",
            error_message=(
                "message_id is required unless save_as_draft=True (a draft has "
                "no message id to address)."
            ),
            params=params,
            exception=ValueError("missing_message_id"),
        )

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

        if save_as_draft:
            draft_payload = await save_draft(client, chat, new_text)
            log_operation_success("Draft saved", chat_id)
            return draft_payload

        rich_format = None
        if resolved_parse_mode == "rich":
            edited_message, rich_format = await edit_rich_via_tl(
                client,
                chat,
                cast(int, message_id),
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
