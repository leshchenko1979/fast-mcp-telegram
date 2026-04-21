"""Message sending functionality."""

from __future__ import annotations

import logging
from typing import Any

from src.client.connection import get_connected_client
from src.server_components.attachment_tickets import get_attachment_ticket
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.file_handling import (
    _calculate_file_count,
    force_document_for_file_list,
    is_own_attachment_url,
    prepare_files_for_send,
)
from src.tools.messages.security import _validate_file_paths
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
    )
    return _extract_first_message(result)


async def _send_message_or_files(
    client,
    entity,
    message: str,
    files: str | list[str] | None,
    reply_to_msg_id: int | None,
    parse_mode: str | None,
    operation: str,
    params: dict[str, Any],
):
    """
    Send message with or without files to an entity.

    Handles validation and routing to appropriate send method.
    """
    effective_reply_to = reply_to_msg_id

    if files:
        file_list = files if isinstance(files, list) else [files]
        if own_urls := [f for f in file_list if is_own_attachment_url(f)]:
            for url in own_urls:
                ticket_id = url.rstrip("/").split("/")[-2]
                ticket = await get_attachment_ticket(ticket_id)
                if ticket:
                    msgs = await client.get_messages(
                        ticket.chat_id, ids=ticket.message_id
                    )
                    msg = msgs[0] if isinstance(msgs, list) else msgs
                    if msg and getattr(msg, "media", None):
                        result = await client.send_file(
                            entity=entity,
                            file=msg.media,
                            caption=message or None,
                            reply_to=reply_to_msg_id,
                            parse_mode=parse_mode,
                            force_document=force_document_for_file_list([url]),
                        )
                        return None, _extract_first_message(result)

        file_list, validation_error = _validate_file_paths(files, operation, params)
        if validation_error or file_list is None:
            return validation_error or {}, None

        sent_message = await _send_files_to_entity(
            client, entity, file_list, message, effective_reply_to, parse_mode
        )
        return None, sent_message

    sent_message = await client.send_message(
        entity=entity,
        message=message,
        reply_to=effective_reply_to,
        parse_mode=parse_mode,
    )
    return None, sent_message


def _extract_send_message_params(
    chat_id: str,
    message: str,
    reply_to_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
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
    }


async def send_message_impl(
    chat_id: str,
    message: str,
    reply_to_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
) -> dict[str, Any]:
    """
    Send a message to a Telegram chat, optionally with files.

    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send (becomes caption when files are provided)
        reply_to_id: ID of the message to reply to. For forum chats, pass topic root ID.
            For channel posts, automatically posts comment in discussion group.
        parse_mode: Parse mode ('markdown' or 'html')
        files: Single file or list of files. URLs (http/https) work in all server modes;
            local filesystem paths are only allowed in stdio mode (blocked for HTTP transports).
    """
    parse_mode = _normalize_parse_mode(parse_mode)
    resolved_parse_mode = parse_mode
    if resolved_parse_mode == "auto":
        resolved_parse_mode = detect_message_formatting(message)

    params = _extract_send_message_params(
        chat_id, message, reply_to_id, resolved_parse_mode, files
    )
    log_operation_start("Sending message to chat", params)

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
    )
    if error:
        return error

    result = build_send_edit_result(sent_message, effective_entity, "sent")
    log_operation_success("Message sent", params["chat_id"])
    return result
