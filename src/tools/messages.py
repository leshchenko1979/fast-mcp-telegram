from typing import Any

from loguru import logger
from telethon.tl.functions.contacts import DeleteContactsRequest, ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from src.client.connection import get_connected_client
from src.tools.links import generate_telegram_links
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_message_result, build_send_edit_result


async def send_message_impl(
    chat_id: str,
    message: str,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """
    Send a message to a Telegram chat.

    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send
        reply_to_msg_id: ID of the message to reply to
        parse_mode: Parse mode ('markdown' or 'html')
    """
    params = {
        "chat_id": chat_id,
        "message": message,
        "message_length": len(message),
        "reply_to_msg_id": reply_to_msg_id,
        "parse_mode": parse_mode,
        "has_reply": reply_to_msg_id is not None,
    }
    log_operation_start("Sending message to chat", params)

    client = await get_connected_client()
    try:
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

        # Send message
        sent_message = await client.send_message(
            entity=chat,
            message=message,
            reply_to=reply_to_msg_id,
            parse_mode=parse_mode,
        )

        result = build_send_edit_result(sent_message, chat, "sent")
        log_operation_success("Message sent", chat_id)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="send_message",
            error_message=f"Failed to send message: {e!s}",
            params=params,
            exception=e,
        )


async def edit_message_impl(
    chat_id: str, message_id: int, new_text: str, parse_mode: str | None = None
) -> dict[str, Any]:
    """
    Edit an existing message in a Telegram chat.

    Args:
        chat_id: The ID of the chat containing the message
        message_id: ID of the message to edit
        new_text: The new text content for the message
        parse_mode: Parse mode ('markdown' or 'html')
    """
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "new_text": new_text,
        "new_text_length": len(new_text),
        "parse_mode": parse_mode,
    }
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

        # Edit message
        edited_message = await client.edit_message(
            entity=chat, message=message_id, text=new_text, parse_mode=parse_mode
        )

        result = build_send_edit_result(edited_message, chat, "edited")
        log_operation_success("Message edited", chat_id)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="edit_message",
            error_message=f"Failed to edit message: {e!s}",
            params=params,
            exception=e,
        )


async def read_messages_by_ids(
    chat_id: str, message_ids: list[int]
) -> list[dict[str, Any]]:
    """
    Read specific messages by their IDs from a given chat.

    Args:
        chat_id: Target chat identifier (username like '@channel', numeric ID, or '-100...' form)
        message_ids: List of message IDs to fetch

    Returns:
        List of message dictionaries consistent with search results format
    """
    params = {
        "chat_id": chat_id,
        "message_ids": message_ids,
        "message_count": len(message_ids) if message_ids else 0,
    }
    log_operation_start("Reading messages by IDs", params)

    if not message_ids or not isinstance(message_ids, list):
        return [
            log_and_build_error(
                operation="read_messages",
                error_message="message_ids must be a non-empty list of integers",
                params=params,
                exception=ValueError(
                    "message_ids must be a non-empty list of integers"
                ),
            )
        ]

    client = await get_connected_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            return [
                log_and_build_error(
                    operation="read_messages",
                    error_message=f"Cannot find any entity corresponding to '{chat_id}'",
                    params=params,
                    exception=ValueError(
                        f"Cannot find any entity corresponding to '{chat_id}'"
                    ),
                )
            ]

        # Fetch messages (Telethon returns a list in the same order as requested ids)
        messages = await client.get_messages(entity, ids=message_ids)
        if not isinstance(messages, list):
            messages = [messages]

        # Pre-generate links for all requested messages
        try:
            links_info = await generate_telegram_links(chat_id, message_ids)
            message_links = links_info.get("message_links", []) or []
            id_to_link = {
                mid: message_links[idx]
                for idx, mid in enumerate(message_ids)
                if idx < len(message_links)
            }
        except Exception:
            id_to_link = {}

        chat_dict = build_entity_dict(entity)
        results: list[dict[str, Any]] = []
        for idx, requested_id in enumerate(message_ids):
            msg = None
            # Telethon may return None for missing messages; map by index if lengths match, else search
            if idx < len(messages):
                candidate = messages[idx]
                if (
                    candidate is not None
                    and getattr(candidate, "id", None) == requested_id
                ):
                    msg = candidate
                else:
                    # Fallback: try to find exact id in returned list
                    for m in messages:
                        if m is not None and getattr(m, "id", None) == requested_id:
                            msg = m
                            break

            if not msg:
                results.append(
                    {
                        "id": requested_id,
                        "chat": chat_dict,
                        "error": "Message not found or inaccessible",
                    }
                )
                continue

            link = id_to_link.get(getattr(msg, "id", requested_id))
            built = await build_message_result(client, msg, entity, link)
            results.append(built)

        successful_count = len([r for r in results if "error" not in r])
        log_operation_success(
            f"Retrieved {successful_count} messages out of {len(message_ids)} requested",
        )
        return results

    except Exception as e:
        error_response = log_and_build_error(
            operation="read_messages",
            error_message=f"Failed to read messages: {e!s}",
            params=params,
            exception=e,
        )
        return [error_response]


async def send_message_to_phone_impl(
    phone_number: str,
    message: str,
    first_name: str = "Contact",
    last_name: str = "Name",
    remove_if_new: bool = False,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """
    Send a message to a phone number, handling both existing and new contacts safely.

    This function safely handles phone messaging by:
    1. Checking if the contact already exists
    2. Only creating a new contact if needed
    3. Sending the message
    4. Only removing the contact if it was newly created and remove_if_new=True

    Args:
        phone_number: The target phone number (with country code, e.g., "+1234567890")
        message: The text message to send
        first_name: First name for the contact (used only if creating new contact)
        last_name: Last name for the contact (used only if creating new contact)
        remove_if_new: Whether to remove the contact if it was newly created (default: False)
        reply_to_msg_id: ID of the message to reply to (optional)
        parse_mode: Parse mode for message formatting (optional)

    Returns:
        Dictionary with operation results consistent with send_message format, plus:
        - phone_number: The phone number that was messaged
        - contact_was_new: Whether a new contact was created during this operation
        - contact_removed: Whether the contact was removed (only if it was newly created)
    """
    params = {
        "phone_number": phone_number,
        "message": message,
        "message_length": len(message),
        "first_name": first_name,
        "last_name": last_name,
        "remove_if_new": remove_if_new,
        "reply_to_msg_id": reply_to_msg_id,
        "parse_mode": parse_mode,
        "has_reply": reply_to_msg_id is not None,
    }
    log_operation_start("Sending message to phone number", params)

    client = await get_connected_client()
    try:
        # Step 1: Check if contact already exists by trying to get entity
        contact_was_new = False
        user = None

        try:
            # Try to get existing contact by phone number
            user = await client.get_entity(phone_number)
            logger.debug(
                f"Contact {phone_number} already exists, using existing contact"
            )
        except Exception:
            # Contact doesn't exist, create new one
            logger.debug(f"Contact {phone_number} doesn't exist, creating new contact")
            contact = InputPhoneContact(
                client_id=0,
                phone=phone_number,
                first_name=first_name,
                last_name=last_name,
            )

            result = await client(ImportContactsRequest([contact]))

            if not result.users:
                error_msg = f"Failed to add contact. Phone number '{phone_number}' might not be registered on Telegram."
                return log_and_build_error(
                    operation="send_message_to_phone",
                    error_message=error_msg,
                    params=params,
                    exception=ValueError(error_msg),
                )

            user = result.users[0]
            contact_was_new = True
            logger.debug(f"Successfully created new contact for {phone_number}")

        # Step 2: Send the message
        sent_message = await client.send_message(
            entity=user,
            message=message,
            reply_to=reply_to_msg_id,
            parse_mode=parse_mode,
        )

        # Step 3: Remove the contact only if it was newly created and remove_if_new=True
        contact_removed = False
        if remove_if_new and contact_was_new:
            try:
                await client(DeleteContactsRequest(id=[user.id]))
                contact_removed = True
                logger.debug(
                    f"Newly created contact {phone_number} removed after sending message"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to remove newly created contact {phone_number}: {e}"
                )
        elif remove_if_new and not contact_was_new:
            logger.debug(
                f"Contact {phone_number} was existing, not removing (remove_if_new=True but contact was not new)"
            )

        # Build result using existing pattern
        result = build_send_edit_result(sent_message, user, "sent")

        # Add phone-specific information
        result.update(
            {
                "phone_number": phone_number,
                "contact_was_new": contact_was_new,
                "contact_removed": contact_removed,
            }
        )

        log_operation_success("Message sent to phone number", phone_number)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="send_message_to_phone",
            error_message=f"Failed to send message to phone number: {e!s}",
            params=params,
            exception=e,
        )
