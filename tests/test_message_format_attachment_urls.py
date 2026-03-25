"""Tests for HTTP attachment URL helpers in message_format."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.server_config import set_config
from src.utils import message_format as mf

FIXED_TICKET = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class DocumentAttributeAudio:
    def __init__(self, voice: bool = False):
        self.voice = voice


class DocumentAttributeVideo:
    def __init__(self, round_message: bool = False):
        self.round_message = round_message


class MessageMediaDocument:
    def __init__(self, document):
        self.document = document


class MessageMediaPhoto:
    pass


class DummyDocument:
    def __init__(self, attributes):
        self.attributes = attributes


def _message_with_document(attrs: list) -> MagicMock:
    m = MagicMock()
    m.id = 111
    m.media = MessageMediaDocument(DummyDocument(attrs))
    return m


def _message_photo() -> MagicMock:
    m = MagicMock()
    m.id = 222
    m.media = MessageMediaPhoto()
    return m


def test_message_supports_streaming_document_and_photo():
    plain = _message_with_document([])
    assert mf._message_supports_streaming_attachment(plain) is True
    assert mf._message_supports_streaming_attachment(_message_photo()) is True


def test_message_supports_streaming_rejects_voice_and_round_video():
    voice = _message_with_document([DocumentAttributeAudio(voice=True)])
    assert mf._message_supports_streaming_attachment(voice) is False
    rnd = _message_with_document([DocumentAttributeVideo(round_message=True)])
    assert mf._message_supports_streaming_attachment(rnd) is False


def test_message_supports_streaming_no_media():
    m = MagicMock()
    m.media = None
    assert mf._message_supports_streaming_attachment(m) is False


@pytest.mark.asyncio
async def test_maybe_no_url_when_stdio(stdio_config):
    stdio_config.domain = "files.example.test"
    set_config(stdio_config)
    media: dict = {"filename": "a.txt", "mime_type": "text/plain"}
    with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        await mf._maybe_set_attachment_download_url(
            media, _message_with_document([]), -100
        )
    assert "attachment_download_url" not in media
    mint_m.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_no_url_when_placeholder_domain(http_no_auth_config):
    http_no_auth_config.domain = "your-domain.com"
    set_config(http_no_auth_config)
    media: dict = {"filename": "a.txt", "mime_type": "text/plain"}
    with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        await mf._maybe_set_attachment_download_url(
            media, _message_with_document([]), -100
        )
    assert "attachment_download_url" not in media
    mint_m.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_no_url_when_chat_id_none(http_no_auth_config):
    http_no_auth_config.domain = "files.example.test"
    set_config(http_no_auth_config)
    media: dict = {"filename": "a.txt", "mime_type": "text/plain"}
    with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        await mf._maybe_set_attachment_download_url(
            media, _message_with_document([]), None
        )
    assert "attachment_download_url" not in media
    mint_m.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_no_url_for_voice(http_no_auth_config):
    http_no_auth_config.domain = "files.example.test"
    set_config(http_no_auth_config)
    media: dict = {"filename": "v.ogg", "mime_type": "audio/ogg"}
    with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        await mf._maybe_set_attachment_download_url(
            media, _message_with_document([DocumentAttributeAudio(voice=True)]), -50
        )
    assert "attachment_download_url" not in media
    mint_m.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_sets_url_and_mint_args_with_request_token(http_no_auth_config):
    http_no_auth_config.domain = "files.example.test"
    http_no_auth_config.session_name = "fallback-session"
    set_config(http_no_auth_config)
    msg = _message_with_document([])
    media: dict = {"filename": "report.pdf", "mime_type": "application/pdf"}

    with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        mint_m.return_value = FIXED_TICKET
        with patch.object(mf, "get_request_token", return_value="req-token-xyz"):
            await mf._maybe_set_attachment_download_url(media, msg, -999)

    assert (
        media["attachment_download_url"]
        == f"https://files.example.test/v1/attachments/{FIXED_TICKET}"
    )
    mint_m.assert_awaited_once_with(
        "req-token-xyz",
        -999,
        msg.id,
        filename="report.pdf",
        mime_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_maybe_falls_back_to_session_name_when_no_request_token(
    http_no_auth_config,
):
    http_no_auth_config.domain = "files.example.test"
    http_no_auth_config.session_name = "only-session"
    set_config(http_no_auth_config)
    msg = _message_photo()
    media: dict = {"filename": "p.jpg", "mime_type": "image/jpeg"}

    with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        mint_m.return_value = FIXED_TICKET
        with patch.object(mf, "get_request_token", return_value=None):
            await mf._maybe_set_attachment_download_url(media, msg, 321)

    assert (
        media["attachment_download_url"]
        == f"https://files.example.test/v1/attachments/{FIXED_TICKET}"
    )
    mint_m.assert_awaited_once_with(
        "only-session",
        321,
        msg.id,
        filename="p.jpg",
        mime_type="image/jpeg",
    )
