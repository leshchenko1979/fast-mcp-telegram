"""HTTP route to stream Telegram attachments using minted UUID tickets (no Bearer on GET)."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

from starlette.responses import Response, StreamingResponse

from src.client.connection import get_connected_client, set_request_token
from src.config.server_config import get_config
from src.server_components.attachment_tickets import get_attachment_ticket

logger = logging.getLogger(__name__)


def _content_disposition(filename: str | None) -> str:
    raw = (filename or "attachment").replace('"', "'")
    ascii_name = raw.encode("ascii", "replace").decode("ascii") or "attachment"
    encoded = quote(raw, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


async def handle_attachment_download(request: Any) -> Response | StreamingResponse:
    """Stream attachment bytes for a valid ticket. No Authorization header required."""
    ticket_id = request.path_params.get("ticket_id", "")
    ticket = await get_attachment_ticket(ticket_id)
    if ticket is None:
        return Response(status_code=404)

    set_request_token(ticket.session_token)

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

    # Telethon returns one Message when ids is int; list/TotalList when ids is a sequence.
    if raw is None:
        return Response(status_code=404)
    try:
        message = raw[0]
    except TypeError:
        message = raw
    except IndexError:
        return Response(status_code=404)
    if not getattr(message, "media", None):
        return Response(status_code=404)

    cfg = get_config()
    max_bytes = cfg.max_file_size_mb * 1024 * 1024

    mime = ticket.mime_type or "application/octet-stream"

    doc = getattr(message, "document", None)
    size_hint = int(getattr(doc, "size", 0) or 0) or None

    logger.debug(
        "attachment stream: start chat_id=%s message_id=%s bytes_expected=%s filename=%s",
        ticket.chat_id,
        ticket.message_id,
        size_hint,
        ticket.filename,
    )

    async def body():
        t0 = time.perf_counter()
        total = 0
        try:
            async for chunk in client.iter_download(message, limit=max_bytes):
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


def register_attachment_routes(mcp_app) -> None:
    mcp_app.custom_route("/v1/attachments/{ticket_id}", methods=["GET"])(
        handle_attachment_download
    )
