"""Phone number message sending functionality."""

from __future__ import annotations

import logging
from typing import Any, cast

from telethon.tl.functions.contacts import DeleteContactsRequest, ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from src.client.connection import get_connected_client
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.file_handling import _calculate_file_count
from src.tools.messages.sending import _send_message_or_files
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import (
    log_operation_start,
    log_operation_success,
    mask_phone_number_for_log,
)
from src.utils.message_format import build_send_edit_result

logger = logging.getLogger(__name__)


async def send_message_to_phone_impl(
    phone_number: str,
    message: str,
    first_name: str = "Contact",
    last_name: str = "Name",
    remove_if_new: bool = False,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
) -> dict[str, Any]:
    """
    Send a message to a phone number, handling both existing and new contacts safely.

    This function safely handles phone messaging by:
    1. Checking if the contact already exists
    2. Only creating a new contact if needed
    3. Sending the message (optionally with files)
    4. Only removing the contact if it was newly created and remove_if_new=True

    Args:
        phone_number: The target phone number (with country code, e.g., "+1234567890")
        message: The text message to send (becomes caption when files are provided)
        first_name: First name for the contact (used only if creating new contact)
        last_name: Last name for the contact (used only if creating new contact)
        remove_if_new: Whether to remove the contact if it was newly created (default: False)
        reply_to_msg_id: ID of the message to reply to (optional)
        parse_mode: Parse mode for message formatting (optional)
        files: Single file or list of files (URLs or local paths)

    Returns:
        Dictionary with operation results consistent with send_message format, plus:
        - phone_number: The phone number that was messaged
        - contact_was_new: Whether a new contact was created during this operation
        - contact_removed: Whether the contact was removed (only if it was newly created)
    """
    parse_mode = _normalize_parse_mode(parse_mode)
    resolved_parse_mode = parse_mode
    if resolved_parse_mode == "auto":
        resolved_parse_mode = detect_message_formatting(message)

    params = {
        "phone_number": phone_number,
        "message": message,
        "message_length": len(message),
        "first_name": first_name,
        "last_name": last_name,
        "remove_if_new": remove_if_new,
        "reply_to_msg_id": reply_to_msg_id,
        "parse_mode": resolved_parse_mode,
        "has_reply": reply_to_msg_id is not None,
        "has_files": bool(files),
        "file_count": _calculate_file_count(files),
    }
    if parse_mode == "auto":
        params["detected_parse_mode"] = resolved_parse_mode

    log_operation_start("Sending message to phone number", params)

    client = await get_connected_client()
    phone_for_log = mask_phone_number_for_log(phone_number)
    try:
        contact_was_new = False
        user = None

        try:
            user = await client.get_entity(phone_number)
            logger.debug(
                f"Contact {phone_for_log} already exists, using existing contact"
            )
        except Exception:
            logger.debug(f"Contact {phone_for_log} doesn't exist, creating new contact")
            contact = InputPhoneContact(
                client_id=0,
                phone=phone_number,
                first_name=first_name,
                last_name=last_name,
            )

            result = await client(ImportContactsRequest([contact]))

            if not result.users:
                error_msg = (
                    f"Failed to add contact. Phone number '{phone_for_log}' might not "
                    "be registered on Telegram."
                )
                return log_and_build_error(
                    operation="send_message_to_phone",
                    error_message=error_msg,
                    params=params,
                    exception=ValueError(error_msg),
                )

            user = result.users[0]
            contact_was_new = True
            logger.debug(f"Successfully created new contact for {phone_for_log}")

        error, sent_message = await _send_message_or_files(
            client,
            user,
            message,
            files,
            reply_to_msg_id,
            resolved_parse_mode,
            "send_message_to_phone",
            params,
        )
        if error:
            return error

        contact_removed = False
        if remove_if_new and contact_was_new:
            try:
                u = user[0] if isinstance(user, list) else user
                if hasattr(u, "access_hash") and hasattr(u, "id"):
                    await client(DeleteContactsRequest(id=cast(Any, [u])))
                contact_removed = True
                logger.debug(
                    f"Newly created contact {phone_for_log} removed after sending message"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to remove newly created contact {phone_for_log}: {e}"
                )
        elif remove_if_new:
            logger.debug(
                f"Contact {phone_for_log} was existing, not removing "
                "(remove_if_new=True but contact was not new)"
            )

        result = build_send_edit_result(sent_message, user, "sent")

        result.update(
            {
                "phone_number": phone_number,
                "contact_was_new": contact_was_new,
                "contact_removed": contact_removed,
            }
        )

        log_operation_success("Message sent to phone number", phone_for_log)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="send_message_to_phone",
            error_message=f"Failed to send message to phone number: {e!s}",
            params=params,
            exception=e,
        )
