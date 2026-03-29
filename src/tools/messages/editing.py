"""Message editing functionality."""

from __future__ import annotations

import logging
from typing import Any, cast

from src.client.connection import get_connected_client
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import _extract_topic_metadata, build_send_edit_result

logger = logging.getLogger(__name__)


async def edit_message_impl(
    chat_id: str,
    message_id: int,
    new_text: str,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """
    Edit an existing message in a Telegram chat.

    Args:
        chat_id: The ID of the chat containing the message
        message_id: ID of the message to edit
        new_text: The new text content for the message
        parse_mode: Parse mode ('markdown' or 'html')
    """
    parse_mode = _normalize_parse_mode(parse_mode)
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "new_text": new_text,
        "new_text_length": len(new_text),
        "parse_mode": parse_mode,
    }

    resolved_parse_mode = parse_mode
    if parse_mode == "auto":
        resolved_parse_mode = detect_message_formatting(new_text)
        params["detected_parse_mode"] = resolved_parse_mode

    log_operation_start("Editing message in chat", params)

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

        edited_message = await client.edit_message(
            entity=chat,
            message=message_id,
            text=new_text,
            parse_mode=cast(Any, resolved_parse_mode or None),
        )

        result = build_send_edit_result(edited_message, chat, "edited")
        result.update(_extract_topic_metadata(edited_message))

        log_operation_success("Message edited", chat_id)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="edit_message",
            error_message=f"Failed to edit message: {e!s}",
            params=params,
            exception=e,
        )
