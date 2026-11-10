"""HTTP route to stream Telegram attachments using minted UUID tickets (no Bearer on GET)."""

from __future__ import annotations

import logging
import time
from typing import Any, cast
from urllib.parse import quote

from starlette.responses import Response, StreamingResponse
from telethon.types import Message

from src.client.connection import get_connected_client, set_request_token
from src.config.server_config import cfg
from src.server_components.attachment_tickets import (
    AttachmentTicket,
    get_attachment_ticket,
)
from src.utils.message_format.attachments import largest_photo_size
from src.utils.message_format.rich import resolve_rich_media

logger = logging.getLogger(__name__)


def _content_disposition(filename: str | None) -> str:
    raw = (filename or "attachment").replace('"', "'")
    ascii_name = raw.encode("ascii", "replace").decode("ascii") or "attachment"
    encoded = quote(raw, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def _resolve_rich_download_target(
    message: Message, ticket: AttachmentTicket
) -> Any | None:
    """Resolve Photo/Document from message.rich_message by ticket rich_kind + rich_media_id."""
    rich_message = getattr(message, "rich_message", None)
    if rich_message is None or ticket.rich_kind is None or ticket.rich_media_id is None:
        return None
    if ticket.rich_kind not in ("photo", "document"):
        return None
    return resolve_rich_media(rich_message, ticket.rich_kind, ticket.rich_media_id)


def _resolve_download_target(message: Message, ticket: AttachmentTicket) -> Any | None:
    if ticket.rich_kind and ticket.rich_media_id is not None:
        return _resolve_rich_download_target(message, ticket)
    return getattr(message, "media", None)


def _media_size_hint_for_log(download_target: Any) -> int | None:
    """Approximate byte size from media object for debug logs."""
    if download_target is None:
        return None
    cls = download_target.__class__.__name__
    if cls == "Document":
        s = getattr(download_target, "size", None)
        return int(s) if s is not None else None
    if cls == "Photo":
        largest = largest_photo_size(download_target)
        return getattr(largest, "size", None) if largest else None
    doc = getattr(download_target, "document", None)
    if doc is not None:
        s = getattr(doc, "size", None)
        return int(s) if s is not None else None
    photo = getattr(download_target, "photo", None)
    if photo is not None:
        largest = largest_photo_size(photo)
        return getattr(largest, "size", None) if largest else None
    return None


async def handle_attachment_download(request: Any) -> Response | StreamingResponse:
    """Stream attachment bytes for a valid ticket. No Authorization header required."""
    ticket_id = request.path_params.get("ticket_id", "")
    ticket = await get_attachment_ticket(ticket_id)
    if ticket is None:
        return Response(status_code=404)

    set_request_token(ticket.session_token)
    try:
        try:
            client = await get_connected_client()
        except Exception as e:
            logger.warning("attachment stream: client unavailable: %s", e)
            return Response(status_code=503)

        try:
            raw = await client.get_messages(ticket.chat_id, ids=ticket.message_id)
        except Exception as e:
            logger.warning("attachment stream: get_messages failed: %s", e)
            return Response(status_code=502)

        if raw is None or (isinstance(raw, list) and len(raw) == 0):
            return Response(status_code=404)
        message = raw[0] if isinstance(raw, list) else raw
        message = cast("Message", message)

        download_target = _resolve_download_target(message, ticket)
        if download_target is None:
            return Response(status_code=404)

        config = cfg()
        max_bytes = config.max_file_size_mb * 1024 * 1024
        mime = ticket.mime_type or "application/octet-stream"
        size_hint = _media_size_hint_for_log(download_target)

        logger.debug(
            "attachment stream: start chat_id=%s message_id=%s rich=%s/%s bytes_expected=%s filename=%s",
            ticket.chat_id,
            ticket.message_id,
            ticket.rich_kind,
            ticket.rich_media_id,
            size_hint,
            ticket.filename,
        )

        async def body():
            t0 = time.perf_counter()
            total = 0
            try:
                async for chunk in client.iter_download(download_target):
                    if total + len(chunk) > max_bytes:
                        remaining = max_bytes - total
                        if remaining > 0:
                            yield chunk[:remaining]
                            total += remaining
                        break
                    total += len(chunk)
                    yield chunk
            except Exception as e:
                logger.warning("attachment stream: iter_download failed: %s", e)
                raise
            finally:
                elapsed = time.perf_counter() - t0
                logger.debug(
                    "attachment stream: end chat_id=%s message_id=%s bytes_sent=%s elapsed_s=%.2f",
                    ticket.chat_id,
                    ticket.message_id,
                    total,
                    elapsed,
                )

        headers = {
            "Content-Disposition": _content_disposition(ticket.filename),
            "Cache-Control": "private, no-store",
        }
        return StreamingResponse(
            body(),
            media_type=mime,
            headers=headers,
        )
    finally:
        set_request_token(None)


def register_attachment_routes(mcp_app) -> None:
    mcp_app.custom_route("/v1/attachments/{ticket_id}/{filename}", methods=["GET"])(
        handle_attachment_download
    )
