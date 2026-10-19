"""Message sending functionality."""

from __future__ import annotations

import logging
from typing import Any

from src.client.connection import get_connected_client
from src.server_components.attachment_tickets import get_attachment_ticket
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.drafts import save_draft
from src.tools.messages.file_handling import (
    _calculate_file_count,
    force_document_for_file_list,
    is_own_attachment_url,
    prepare_files_for_send,
)
from src.tools.messages.rich_send import send_rich_via_tl
from src.tools.messages.security import _validate_file_paths
from src.utils.datetime_parse import format_schedule_date, parse_schedule_date
from src.utils.discussion import get_post_discussion_info
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_send_edit_result

logger = logging.getLogger(__name__)


def _extract_first_message(result):
    """Extract first message from result (handles both single message and album)."""
    return result[0] if isinstance(result, list) else result


async def _send_files_to_entity(
    client,
    entity,
    file_list: list[str],
    message: str,
    reply_to_msg_id: int | None,
    parse_mode: str | None,
    schedule_date: int | None = None,
):
    """
    Send files to an entity, handling both single and multiple files.

    Http(s) URLs are downloaded first (with .name from the URL) so Telethon does not
    mis-detect non-images as photos. force_document is set unless all names look like
    raster images, avoiding MediaInvalidError for HTML/session exports and similar.
    """
    prepared = await prepare_files_for_send(file_list)
    force_doc = force_document_for_file_list(file_list)
    file_arg = prepared[0] if len(prepared) == 1 else prepared

    result = await client.send_file(
        entity=entity,
        file=file_arg,
        caption=message or None,
        reply_to=reply_to_msg_id,
        parse_mode=parse_mode,
        force_document=force_doc,
        schedule=schedule_date,
    )
    return _extract_first_message(result)


def validate_send_options(
    *,
    message: str,
    files: str | list[str] | None,
    parse_mode: str | None,
    schedule_date: str | None,
    save_as_draft: bool,
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    """Reject impossible option combinations before any network work.

    These checks used to live only in ``_send_message_or_files``, which runs
    after ``get_connected_client()`` — so an invalid combination still opened a
    client (and failed on a missing API_ID) instead of reporting the parameter
    error. Call this first; ``_send_message_or_files`` re-checks for its own
    direct callers.

    Returns the error dict when the combination is invalid, else ``None``.
    """
    if not save_as_draft:
        return None
    if files:
        return log_and_build_error(
            operation=operation,
            error_message=(
                "save_as_draft=True cannot be combined with files. "
                "Drafts are text-only here; send the file normally or "
                "drop save_as_draft."
            ),
            params=params,
            exception=ValueError("draft_with_files"),
        )
    if parse_mode == "rich":
        return log_and_build_error(
            operation=operation,
            error_message=(
                "save_as_draft=True cannot be combined with "
                "parse_mode='rich': messages.saveDraft has no rich_message "
                "field. Use classic parse_mode for the draft."
            ),
            params=params,
            exception=ValueError("draft_with_rich"),
        )
    if schedule_date is not None:
        return log_and_build_error(
            operation=operation,
            error_message=(
                "A draft cannot be scheduled: messages.saveDraft has no "
                "schedule_date field. Pass either schedule_date (queue a "
                "send) or save_as_draft (save for later), not both."
            ),
            params=params,
            exception=ValueError("draft_with_schedule"),
        )
    return None


async def _send_message_or_files(
    client,
    entity,
    message: str,
    files: str | list[str] | None,
    reply_to_msg_id: int | None,
    parse_mode: str | None,
    operation: str,
    params: dict[str, Any],
    schedule_date: int | None = None,
    save_as_draft: bool = False,
):
    """
    Send message with or without files to an entity.

    Handles validation and routing to the appropriate send method. Three exits
    carry the scheduling flag (text, files, rich) so a queued message is queued
    whichever path it takes.

    ``save_as_draft=True`` is a different operation, not a variant of send: it
    returns the already-built draft payload as the second tuple element instead of
    a Message, so callers must check for a ``dict`` before formatting it.
    """
    if save_as_draft:
        rejection = validate_send_options(
            message=message,
            files=files,
            parse_mode=parse_mode,
            schedule_date=schedule_date,
            save_as_draft=True,
            operation=operation,
            params=params,
        )
        if rejection is not None:
            return rejection, None
        draft_payload = await save_draft(client, entity, message, reply_to_msg_id)
        return None, draft_payload

    if parse_mode == "rich" and files:
        return (
            log_and_build_error(
                operation=operation,
                error_message=(
                    "parse_mode='rich' cannot be combined with files. "
                    "Send the Rich Message without files, or use classic "
                    "parse_mode (markdown/html/auto) with a caption."
                ),
                params=params,
                exception=ValueError("rich_parse_mode_with_files"),
            ),
            None,
        )

    if parse_mode == "rich":
        sent_message, rich_format = await send_rich_via_tl(
            client, entity, message, reply_to_msg_id, schedule_date=schedule_date
        )
        params["rich_format"] = rich_format
        return None, sent_message

    effective_reply_to = reply_to_msg_id

    if files:
        file_list = files if isinstance(files, list) else [files]
        if own_urls := [f for f in file_list if is_own_attachment_url(f)]:
            media_list = []
            for url in own_urls:
                ticket_id = url.rstrip("/").split("/")[-2]
                ticket = await get_attachment_ticket(ticket_id)
                if ticket:
                    msgs = await client.get_messages(
                        ticket.chat_id, ids=ticket.message_id
                    )
                    msg = msgs[0] if isinstance(msgs, list) else msgs
                    if msg and getattr(msg, "media", None):
                        media_list.append(msg.media)

            if media_list:
                force_doc = force_document_for_file_list(file_list)
                file_arg = media_list[0] if len(media_list) == 1 else media_list
                result = await client.send_file(
                    entity=entity,
                    file=file_arg,
                    caption=message or None,
                    reply_to=reply_to_msg_id,
                    parse_mode=parse_mode,
                    force_document=force_doc,
                    schedule=schedule_date,
                )
                return None, _extract_first_message(result)

        file_list, validation_error = _validate_file_paths(files, operation, params)
        if validation_error or file_list is None:
            return validation_error or {}, None

        sent_message = await _send_files_to_entity(
            client,
            entity,
            file_list,
            message,
            effective_reply_to,
            parse_mode,
            schedule_date,
        )
        return None, sent_message

    sent_message = await client.send_message(
        entity=entity,
        message=message,
        reply_to=effective_reply_to,
        parse_mode=parse_mode,
        schedule=schedule_date,
    )
    return None, sent_message


def _extract_send_message_params(
    chat_id: str,
    message: str,
    reply_to_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
    schedule_date: str | None = None,
    save_as_draft: bool = False,
) -> dict:
    """Extract params for send_message error handling and logging."""
    return {
        "chat_id": chat_id,
        "message": message,
        "message_length": len(message),
        "reply_to_id": reply_to_id,
        "parse_mode": parse_mode,
        "has_reply": reply_to_id is not None,
        "has_files": bool(files),
        "file_count": _calculate_file_count(files),
        "schedule_date": schedule_date,
        "save_as_draft": save_as_draft,
    }


async def send_message_impl(
    chat_id: str,
    message: str,
    reply_to_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
    schedule_date: str | None = None,
    save_as_draft: bool = False,
) -> dict[str, Any]:
    """
    Send a message to a Telegram chat, optionally with files, scheduled or as a draft.

    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send (becomes caption when files are provided)
        reply_to_id: ID of the message to reply to. For forum chats, pass topic root ID.
            For channel posts, automatically posts comment in discussion group.
        parse_mode: Parse mode ('markdown', 'html', 'auto', or 'rich')
        files: Single file or list of files. Supports three formats:
            - **data: URIs** (`data:<mime>;base64,<payload>`) — works in all server modes;
              ideal for remote deployments where local paths are unavailable.
            - **http(s) URLs** — downloaded server-side with security validation.
            - **Local filesystem paths** — only allowed in stdio mode.
        schedule_date: ISO 8601 instant at which Telegram should send the message
            (e.g. ``2026-10-20T09:00:00Z``). Must be in the future. When set the
            message is queued and the result carries ``status="scheduled"``.
        save_as_draft: Save the text as the chat's draft instead of sending it.
            An empty ``message`` clears the existing draft. User sessions only —
            bot accounts cannot call ``messages.saveDraft``. Cannot be combined
            with ``schedule_date``, ``files`` or ``parse_mode="rich"``.
    """
    parse_mode = _normalize_parse_mode(parse_mode)
    resolved_parse_mode = parse_mode
    if resolved_parse_mode == "auto":
        resolved_parse_mode = detect_message_formatting(message)

    params = _extract_send_message_params(
        chat_id,
        message,
        reply_to_id,
        resolved_parse_mode,
        files,
        schedule_date,
        save_as_draft,
    )
    log_operation_start("Sending message to chat", params)

    try:
        schedule_timestamp = parse_schedule_date(schedule_date)
    except ValueError as e:
        return log_and_build_error(
            operation="send_message",
            error_message=str(e),
            params=params,
            exception=e,
        )

    rejection = validate_send_options(
        message=message,
        files=files,
        parse_mode=resolved_parse_mode,
        schedule_date=schedule_date,
        save_as_draft=save_as_draft,
        operation="send_message",
        params=params,
    )
    if rejection is not None:
        return rejection

    client = await get_connected_client()
    chat = await get_entity_by_id(chat_id)
    if not chat:
        return log_and_build_error(
            operation="send_message",
            error_message=f"Cannot find chat with ID '{chat_id}'",
            params=params,
            exception=ValueError(
                f"Cannot find any entity corresponding to '{chat_id}'"
            ),
        )

    effective_entity = chat
    effective_reply_to_id = reply_to_id

    if reply_to_id is not None and hasattr(chat, "broadcast") and chat.broadcast:
        try:
            discussion_info = await get_post_discussion_info(client, chat, reply_to_id)
            effective_entity = discussion_info["discussion_peer"]
            effective_reply_to_id = discussion_info["discussion_msg_id"]
            params["chat_id"] = discussion_info["discussion_chat_id"]
            params["reply_to_id"] = effective_reply_to_id
            params["has_reply"] = True
            logger.debug(
                "Detected channel post with discussion, posting comment in discussion group"
            )
        except ValueError as e:
            return log_and_build_error(
                operation="send_message",
                error_message=str(e),
                params=params,
                exception=e,
            )

    error, sent_message = await _send_message_or_files(
        client,
        effective_entity,
        message,
        files,
        effective_reply_to_id,
        resolved_parse_mode,
        "send_message",
        params,
        schedule_date=schedule_timestamp,
        save_as_draft=save_as_draft,
    )
    if error:
        return error

    if isinstance(sent_message, dict):
        # Draft path: a draft is not a message, so the payload is already built.
        log_operation_success("Draft saved", params["chat_id"])
        return sent_message

    status = "scheduled" if schedule_timestamp is not None else "sent"
    result = build_send_edit_result(
        sent_message,
        effective_entity,
        status,
        rich_format=params.get("rich_format"),
    )
    if schedule_timestamp is not None:
        result["scheduled"] = True
        result["schedule_date"] = format_schedule_date(schedule_timestamp)

    log_operation_success(
        "Message scheduled" if schedule_timestamp is not None else "Message sent",
        params["chat_id"],
    )
    return result
