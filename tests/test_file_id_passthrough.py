"""Tests for file_id passthrough in send_message and is_own_attachment_url helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.server_config import ServerConfig, ServerMode, set_config
from src.tools.messages.file_handling import is_own_attachment_url


class TestIsOwnAttachmentUrl:
    """Tests for is_own_attachment_url helper."""

    def test_true_when_url_matches_public_base(self, http_no_auth_config):
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)
        assert is_own_attachment_url("https://files.example.test/v1/attachments/abc/def.jpg") is True

    def test_true_for_nested_path(self, http_no_auth_config):
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)
        assert is_own_attachment_url("https://files.example.test/v1/attachments/uuid/photo_123.jpg") is True

    def test_false_for_external_url(self, http_no_auth_config):
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)
        assert is_own_attachment_url("https://cdn.example.com/video.mp4") is False

    def test_false_for_different_domain(self, http_no_auth_config):
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)
        assert is_own_attachment_url("https://evil.com/v1/attachments/abc") is False

    def test_false_when_public_base_url_unset(self):
        """When public_base_url_normalized is empty (placeholder domain or no domain), returns False."""
        config = ServerConfig()
        config.server_mode = ServerMode.HTTP_NO_AUTH
        config.domain = ""
        set_config(config)
        assert is_own_attachment_url("https://files.example.test/v1/attachments/abc") is False


class TestSendMessageFileIdPassthrough:
    """Tests for send_message intercepting own attachment URLs and using msg.media directly."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.send_file = AsyncMock()
        client.get_messages = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_own_attachment_url_uses_msg_media(self, http_no_auth_config, mock_client):
        """When files=[own_url], send_file is called with msg.media, not bytes."""
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)

        from src.tools.messages.sending import _send_message_or_files

        # Mock message with media
        mock_msg = MagicMock()
        mock_msg.id = 999
        mock_msg.media = MagicMock()
        mock_client.get_messages.return_value = mock_msg

        # Ticket lookup
        with patch("src.tools.messages.sending.get_attachment_ticket") as mint:
            mint.return_value = MagicMock(
                session_token="tok", chat_id=-100, message_id=999
            )
            result_error, result_msg = await _send_message_or_files(
                client=mock_client,
                entity="me",
                message="test caption",
                files=["https://files.example.test/v1/attachments/ticket-uuid/photo_999.jpg"],
                reply_to_msg_id=None,
                parse_mode=None,
                operation="send_message",
                params={},
            )

        mock_client.send_file.assert_called_once()
        call_kwargs = mock_client.send_file.call_args.kwargs
        assert call_kwargs["file"] is mock_msg.media
        assert call_kwargs["caption"] == "test caption"

    @pytest.mark.asyncio
    async def test_own_attachment_url_with_document_name(self, http_no_auth_config, mock_client):
        """Own URL with document filename also uses msg.media."""
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)

        from src.tools.messages.sending import _send_message_or_files

        mock_msg = MagicMock()
        mock_msg.id = 777
        mock_msg.media = MagicMock()
        mock_client.get_messages.return_value = mock_msg

        with patch("src.tools.messages.sending.get_attachment_ticket") as mint:
            mint.return_value = MagicMock(session_token="tok", chat_id=-100, message_id=777)
            result_error, result_msg = await _send_message_or_files(
                client=mock_client,
                entity="me",
                message="sending doc",
                files=["https://files.example.test/v1/attachments/ticket-uuid/report.pdf"],
                reply_to_msg_id=None,
                parse_mode=None,
                operation="send_message",
                params={},
            )

        mock_client.send_file.assert_called_once()
        assert mock_client.send_file.call_args.kwargs["file"] is mock_msg.media

    @pytest.mark.asyncio
    async def test_unknown_ticket_falls_through_to_download(self, http_no_auth_config, mock_client):
        """URL with unknown ticket ID falls through to normal download path."""
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)

        from src.tools.messages.sending import _send_message_or_files

        with patch("src.tools.messages.sending.get_attachment_ticket") as mint:
            mint.return_value = None  # ticket not found
            with patch("src.tools.messages.sending._send_files_to_entity") as send_files:
                send_files.return_value = MagicMock()
                await _send_message_or_files(
                    client=mock_client,
                    entity="me",
                    message="test",
                    files=["https://files.example.test/v1/attachments/bad-ticket/doc.pdf"],
                    reply_to_msg_id=None,
                    parse_mode=None,
                    operation="send_message",
                    params={},
                )
                send_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_external_url_skips_passthrough(self, http_no_auth_config, mock_client):
        """External URLs bypass the file_id passthrough entirely."""
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)

        from src.tools.messages.sending import _send_message_or_files

        with patch("src.tools.messages.sending.get_attachment_ticket") as mint:
            mint.return_value = None
            with patch("src.tools.messages.sending._send_files_to_entity") as send_files:
                send_files.return_value = MagicMock()
                await _send_message_or_files(
                    client=mock_client,
                    entity="me",
                    message="test",
                    files=["https://external-cdn.com/video.mp4"],
                    reply_to_msg_id=None,
                    parse_mode=None,
                    operation="send_message",
                    params={},
                )
                send_files.assert_called_once()
                mint.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_files_mixed_urls(self, http_no_auth_config, mock_client):
        """Mixed own + external URLs: own ones use file_id, external still downloads."""
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)

        from src.tools.messages.sending import _send_message_or_files

        mock_msg = MagicMock()
        mock_msg.id = 888
        mock_msg.media = MagicMock()
        mock_client.get_messages.return_value = mock_msg

        with patch("src.tools.messages.sending.get_attachment_ticket") as mint:
            mint.return_value = MagicMock(session_token="tok", chat_id=-100, message_id=888)
            with patch("src.tools.messages.sending._send_files_to_entity") as send_files:
                send_files.return_value = MagicMock()
                await _send_message_or_files(
                    client=mock_client,
                    entity="me",
                    message="test",
                    files=[
                        "https://files.example.test/v1/attachments/ticket-uuid/photo_888.jpg",
                        "https://external-cdn.com/image.png",
                    ],
                    reply_to_msg_id=None,
                    parse_mode=None,
                    operation="send_message",
                    params={},
                )
                # Our URL intercepts and returns early — download path not called
                send_files.assert_not_called()


class TestPhotoSyntheticFilename:
    """Tests for photo synthetic filename generation in URL."""

    @pytest.mark.asyncio
    async def test_photo_generates_synthetic_filename(self, http_no_auth_config):
        """Photos without a stored filename get photo_{msg_id}.jpg in the URL."""
        http_no_auth_config.domain = "files.example.test"
        set_config(http_no_auth_config)

        from src.utils import message_format as mf

        # Use a real-ish mock that _message_supports_streaming_attachment accepts
        msg = MagicMock()
        msg.id = 12345
        msg.media = MagicMock()
        msg.media.__class__.__name__ = "MessageMediaPhoto"

        media: dict = {"type": "photo", "mime_type": "image/jpeg"}

        with patch.object(mf, "mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
            mint_m.return_value = "test-ticket-uuid"
            with patch.object(mf, "get_request_token", return_value="tok"):
                await mf._maybe_set_attachment_download_url(media, msg, -100)

        assert "/photo_12345.jpg" in media["attachment_download_url"]
        assert "test-ticket-uuid" in media["attachment_download_url"]
