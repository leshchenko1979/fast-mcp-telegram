"""Send/edit Telegram Rich Messages via MTProto InputRichMessage*."""

from __future__ import annotations

import secrets
from typing import Any, Literal

from telethon.tl import functions, types

from src.tools.messages.core import detect_rich_dialect

RichFormat = Literal["html", "markdown"]


def build_input_rich_message(
    text: str, dialect: RichFormat
) -> types.TypeInputRichMessage:
    """Build InputRichMessageHTML or InputRichMessageMarkdown."""
    if dialect == "html":
        return types.InputRichMessageHTML(html=text)
    return types.InputRichMessageMarkdown(markdown=text)


async def _message_from_tl_result(
    client: Any, request: Any, result: Any, entity: Any
) -> Any:
    """Extract Message from Updates; refetch by id if private helper fails."""
    msg = client._get_response_message(request, result, entity)
    if msg is not None:
        return msg

    msg_id = None
    for update in getattr(result, "updates", None) or []:
        message = getattr(update, "message", None)
        if message is None:
            continue
        if isinstance(update, types.UpdateNewScheduledMessage):
            # ``_get_response_message`` already ran ``_finish_init`` on this
            # message. A queued message is invisible to ``messages.getMessages``
            # (only ``messages.getScheduledMessages`` reaches it), so return the
            # update's own message instead of trying to refetch it.
            return message
        if getattr(message, "id", None) is not None:
            msg_id = message.id
            break
    if msg_id is None:
        raise RuntimeError(
            "Telegram returned Updates without an extractable message for rich send/edit"
        )
    fetched = await client.get_messages(entity, ids=msg_id)
    if isinstance(fetched, list):
        fetched = fetched[0] if fetched else None
    if fetched is None:
        raise RuntimeError(f"Could not refetch rich message id={msg_id}")
    return fetched


async def send_rich_via_tl(
    client: Any,
    entity: Any,
    message: str,
    reply_to_msg_id: int | None = None,
    *,
    dialect: RichFormat | None = None,
    schedule_date: int | None = None,
) -> tuple[Any, RichFormat]:
    """Send a Rich Message; returns (Message, rich_format).

    ``schedule_date`` is a unix timestamp: when set, Telegram queues the message
    instead of delivering it now, and the returned Message carries the scheduled
    date rather than a delivery date.
    """
    resolved = dialect or detect_rich_dialect(message)
    input_peer = await client.get_input_entity(entity)
    reply_to = None
    if reply_to_msg_id is not None:
        reply_to = types.InputReplyToMessage(reply_to_msg_id=reply_to_msg_id)
    request = functions.messages.SendMessageRequest(
        peer=input_peer,
        message="",
        random_id=secrets.randbits(63),
        reply_to=reply_to,
        rich_message=build_input_rich_message(message, resolved),
        schedule_date=schedule_date,
    )
    result = await client(request)
    msg = await _message_from_tl_result(client, request, result, entity)
    return msg, resolved


async def edit_rich_via_tl(
    client: Any,
    entity: Any,
    message_id: int,
    new_text: str,
    *,
    dialect: RichFormat | None = None,
    schedule_date: int | None = None,
) -> tuple[Any, RichFormat]:
    """Edit a message to Rich Message content; returns (Message, rich_format).

    ``schedule_date`` reschedules an already-queued message instead of editing a
    delivered one.
    """
    resolved = dialect or detect_rich_dialect(new_text)
    input_peer = await client.get_input_entity(entity)
    request = functions.messages.EditMessageRequest(
        peer=input_peer,
        id=message_id,
        message="",
        rich_message=build_input_rich_message(new_text, resolved),
        schedule_date=schedule_date,
    )
    result = await client(request)
    msg = await _message_from_tl_result(client, request, result, entity)
    return msg, resolved
