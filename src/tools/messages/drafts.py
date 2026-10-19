"""Telegram message drafts (``messages.saveDraft``).

A draft is server-side state: text the user started but did not send. It is keyed
by ``(peer, reply_to)`` — one draft per chat or per forum topic — so there is no
message id to address. Saving a draft is an upsert; saving an empty string clears
it.

Two server-side facts that shape this module:

* ``messages.saveDraft`` is a **user-session** method. Bot accounts cannot call it,
  so this path raises for a bot-authenticated session and the caller surfaces that.
* ``saveDraft`` has **no** ``schedule_date`` field. Drafts and scheduled messages
  are disjoint concepts; the callers reject the combination instead of pretending.
"""

from __future__ import annotations

import logging
from typing import Any

from telethon.tl import functions, types

from src.utils.entity import build_entity_dict

logger = logging.getLogger(__name__)


async def save_draft(
    client: Any,
    entity: Any,
    message: str,
    reply_to_msg_id: int | None = None,
) -> dict[str, Any]:
    """Save (or clear, when ``message`` is empty) the draft for one chat.

    Returns a result payload shaped like the send/edit results, with
    ``status`` of ``draft_saved`` or ``draft_cleared``. There is no message id or
    date to report — the draft is not a message yet.
    """
    input_peer = await client.get_input_entity(entity)

    reply_to = None
    if reply_to_msg_id is not None:
        reply_to = types.InputReplyToMessage(reply_to_msg_id=reply_to_msg_id)

    await client(
        functions.messages.SaveDraftRequest(
            peer=input_peer,
            message=message,
            reply_to=reply_to,
        )
    )

    is_clear = not message
    result: dict[str, Any] = {
        "status": "draft_cleared" if is_clear else "draft_saved",
        "draft_saved": True,
        "text": message,
    }

    chat_dict = build_entity_dict(entity)
    if chat_dict is not None:
        result["chat"] = chat_dict
    if reply_to_msg_id is not None:
        result["reply_to_id"] = reply_to_msg_id

    logger.debug(
        "Draft %s in chat %s",
        "cleared" if is_clear else f"saved ({len(message)} chars)",
        getattr(entity, "id", entity),
    )
    return result
