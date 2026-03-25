"""In-memory attachment download tickets (UUID → session + message locator)."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

from src.config.server_config import get_config


@dataclass(frozen=True)
class AttachmentTicket:
    """Server-side record for streaming one message's media without Bearer on GET."""

    session_token: str
    chat_id: int
    message_id: int
    expires_at: float
    filename: str | None
    mime_type: str | None


_tickets: dict[str, AttachmentTicket] = {}
_lock = asyncio.Lock()


def _prune_expired_unlocked() -> None:
    now = time.time()
    dead = [k for k, v in _tickets.items() if v.expires_at <= now]
    for k in dead:
        del _tickets[k]


async def mint_attachment_ticket(
    session_token: str,
    chat_id: int,
    message_id: int,
    *,
    filename: str | None = None,
    mime_type: str | None = None,
) -> str:
    """Create a ticket; returns UUID string. Multi-use until expiry."""
    cfg = get_config()
    tid = str(uuid.uuid4())
    expires_at = time.time() + float(cfg.attachment_ticket_ttl_seconds)
    rec = AttachmentTicket(
        session_token=session_token,
        chat_id=int(chat_id),
        message_id=int(message_id),
        expires_at=expires_at,
        filename=filename,
        mime_type=mime_type,
    )
    async with _lock:
        _prune_expired_unlocked()
        _tickets[tid] = rec
    return tid


async def get_attachment_ticket(ticket_id: str) -> AttachmentTicket | None:
    """Return ticket if present and not expired."""
    async with _lock:
        _prune_expired_unlocked()
        rec = _tickets.get(ticket_id)
        if rec is None:
            return None
        if rec.expires_at <= time.time():
            del _tickets[ticket_id]
            return None
        return rec


async def clear_attachment_tickets_for_tests() -> None:
    """Reset store (tests only)."""
    async with _lock:
        _tickets.clear()
