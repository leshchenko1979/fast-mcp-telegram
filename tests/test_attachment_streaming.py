"""Attachment ticket store and unauthenticated GET /v1/attachments/{ticket_id} streaming."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.server_components.attachment_routes import handle_attachment_download
from src.server_components.attachment_tickets import (
    clear_attachment_tickets_for_tests,
    get_attachment_ticket,
    mint_attachment_ticket,
)

pytestmark = pytest.mark.usefixtures("http_no_auth_config")


@pytest_asyncio.fixture(autouse=True)
async def _reset_tickets():
    await clear_attachment_tickets_for_tests()
    yield
    await clear_attachment_tickets_for_tests()


@pytest.mark.asyncio
async def test_mint_and_get_ticket_roundtrip():
    tid = await mint_attachment_ticket(
        "my-session-token",
        -1001234567890,
        99,
        filename="doc.pdf",
        mime_type="application/pdf",
    )
    got = await get_attachment_ticket(tid)
    assert got is not None
    assert got.session_token == "my-session-token"
    assert got.chat_id == -1001234567890
    assert got.message_id == 99
    assert got.filename == "doc.pdf"
    assert got.mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_expired_ticket_returns_none():
    tid = await mint_attachment_ticket("tok", 1, 1)
    assert await get_attachment_ticket(tid) is not None

    with patch(
        "src.server_components.attachment_tickets.time.time",
        return_value=__import__("time").time() + 10**9,
    ):
        assert await get_attachment_ticket(tid) is None


@pytest.mark.asyncio
async def test_unknown_ticket_returns_404():
    req = MagicMock()
    req.path_params = {"ticket_id": "00000000-0000-0000-0000-000000000001"}
    resp = await handle_attachment_download(req)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_without_authorization_header():
    tid = await mint_attachment_ticket(
        "sess-tok",
        -1001,
        7,
        filename="x.bin",
        mime_type="application/octet-stream",
    )

    class FakeMsg:
        media = object()

    class FakeClient:
        async def get_messages(self, chat_id, ids):
            assert chat_id == -1001
            assert ids == 7
            return [FakeMsg()]

        async def iter_download(self, *args, **kwargs):
            yield b"ab"
            yield b"cd"

    req = MagicMock()
    req.path_params = {"ticket_id": tid}

    with patch(
        "src.server_components.attachment_routes.get_connected_client",
        new=AsyncMock(return_value=FakeClient()),
    ):
        resp = await handle_attachment_download(req)

    assert resp.status_code == 200
    assert resp.media_type == "application/octet-stream"
    body = b""
    async for part in resp.body_iterator:
        body += part
    assert body == b"abcd"


@pytest.mark.asyncio
async def test_stream_when_get_messages_returns_single_message():
    """Telethon returns one Message when ids is a single int, not always a list."""
    tid = await mint_attachment_ticket(
        "sess-tok",
        -1001,
        7,
        filename="x.bin",
        mime_type="application/octet-stream",
    )

    class FakeMsg:
        media = object()

    class FakeClient:
        async def get_messages(self, chat_id, ids):
            assert chat_id == -1001
            assert ids == 7
            return FakeMsg()

        async def iter_download(self, *args, **kwargs):
            yield b"z"

    req = MagicMock()
    req.path_params = {"ticket_id": tid}

    with patch(
        "src.server_components.attachment_routes.get_connected_client",
        new=AsyncMock(return_value=FakeClient()),
    ):
        resp = await handle_attachment_download(req)

    assert resp.status_code == 200
    body = b""
    async for part in resp.body_iterator:
        body += part
    assert body == b"z"


@pytest.mark.asyncio
async def test_stream_when_get_messages_returns_empty_list():
    tid = await mint_attachment_ticket("sess-tok", -1001, 7)

    class FakeClient:
        async def get_messages(self, chat_id, ids):
            return []

    req = MagicMock()
    req.path_params = {"ticket_id": tid}

    with patch(
        "src.server_components.attachment_routes.get_connected_client",
        new=AsyncMock(return_value=FakeClient()),
    ):
        resp = await handle_attachment_download(req)

    assert resp.status_code == 404
