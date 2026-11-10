"""Tests for missing/deleted message id handling in message_ids mode."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.tools.messages.reading import read_messages_by_ids
from src.tools.search import search_messages_impl
from src.tools.search.forum_replies import _get_messages_by_ids_batched
from src.utils.message_format import message_has_displayable_content
from tests.conftest import make_mock_message


def _make_message_empty(msg_id: int):
    empty = MagicMock()
    empty.__class__.__name__ = "MessageEmpty"
    empty.id = msg_id
    empty.text = None
    empty.message = None
    empty.caption = None
    empty.media = None
    empty.action = None
    empty.rich_message = None
    return empty


def _stub_client(mock_entity, get_messages_return):
    mock_entity.id = 3627148483
    mock_entity.title = "OC Dev"
    mock_client = AsyncMock()
    mock_client.get_messages = AsyncMock(return_value=get_messages_return)
    mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
    return mock_client


class TestMessageIdsMissingStubs:
    """Per-id stubs stay under messages[]; operational errors stay top-level."""

    @pytest.mark.asyncio
    @patch("src.tools.messages.reading.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.messages.reading.get_entity_by_id", new_callable=AsyncMock)
    async def test_single_missing_returns_stub_in_list(
        self, mock_get_entity, mock_get_client
    ):
        mock_entity = Mock()
        mock_get_entity.return_value = mock_entity
        mock_get_client.return_value = _stub_client(mock_entity, [None])

        with patch(
            "src.tools.messages.reading.generate_telegram_links",
            new=AsyncMock(return_value={"message_links": []}),
        ):
            result = await read_messages_by_ids("3627148483", [12658])

        assert len(result) == 1
        assert result[0]["id"] == 12658
        assert result[0]["error"] == "Message not found or inaccessible"
        assert "chat" in result[0]
        assert result[0].get("ok") is not False

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_single_missing_stub_wrapped_in_messages_envelope(self, mock_read):
        mock_read.return_value = [
            {
                "id": 12658,
                "chat": {"id": 1, "title": "OC Dev"},
                "error": "Message not found or inaccessible",
            }
        ]

        result = await search_messages_impl(chat_id="3627148483", message_ids=[12658])

        assert "messages" in result
        assert result["has_more"] is False
        assert len(result["messages"]) == 1
        assert result["messages"][0]["error"] == "Message not found or inaccessible"
        assert "error" not in result or result.get("ok") is not False

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_operational_ok_false_still_top_level(self, mock_read):
        mock_read.return_value = [{"error": "Message not found", "ok": False}]

        result = await search_messages_impl(chat_id="me", message_ids=[999])

        assert result["ok"] is False
        assert result["error"] == "Message not found"
        assert "messages" not in result

    @pytest.mark.asyncio
    @patch("src.tools.messages.reading.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.messages.reading.get_entity_by_id", new_callable=AsyncMock)
    async def test_mix_present_and_missing(self, mock_get_entity, mock_get_client):
        mock_entity = Mock()
        present = make_mock_message(id=12661, text="found", date=datetime.now())
        mock_get_entity.return_value = mock_entity
        mock_get_client.return_value = _stub_client(mock_entity, [present, None])

        with patch(
            "src.tools.messages.reading.generate_telegram_links",
            new=AsyncMock(
                return_value={"message_links": ["https://t.me/c/3627148483/12661"]}
            ),
        ):
            result = await read_messages_by_ids("3627148483", [12661, 12658])

        assert len(result) == 2
        assert "error" not in result[0]
        assert result[0]["text"] == "found"
        assert result[1]["id"] == 12658
        assert result[1]["error"] == "Message not found or inaccessible"

    @pytest.mark.asyncio
    @patch("src.tools.messages.reading.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.messages.reading.get_entity_by_id", new_callable=AsyncMock)
    async def test_message_empty_returns_stub(self, mock_get_entity, mock_get_client):
        mock_entity = Mock()
        empty = _make_message_empty(12659)
        mock_get_entity.return_value = mock_entity
        mock_get_client.return_value = _stub_client(mock_entity, [empty])

        with patch(
            "src.tools.messages.reading.generate_telegram_links",
            new=AsyncMock(return_value={"message_links": []}),
        ):
            result = await read_messages_by_ids("3627148483", [12659])

        assert len(result) == 1
        assert result[0]["id"] == 12659
        assert result[0]["error"] == "Message not found or inaccessible"

    @pytest.mark.asyncio
    @patch("src.tools.messages.reading.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.messages.reading.get_entity_by_id", new_callable=AsyncMock)
    async def test_media_only_message_not_stubbed(
        self, mock_get_entity, mock_get_client
    ):
        mock_entity = Mock()
        photo_msg = make_mock_message(id=99, text=None, date=datetime.now())
        photo_msg.media = MagicMock()
        photo_msg.media.__class__.__name__ = "MessageMediaPhoto"
        mock_get_entity.return_value = mock_entity
        mock_get_client.return_value = _stub_client(mock_entity, [photo_msg])

        with (
            patch(
                "src.tools.messages.reading.generate_telegram_links",
                new=AsyncMock(
                    return_value={"message_links": ["https://t.me/c/3627148483/99"]}
                ),
            ),
            patch(
                "src.tools.messages.reading.build_message_result",
                new=AsyncMock(return_value={"id": 99, "text": None, "media": {}}),
            ),
        ):
            result = await read_messages_by_ids("3627148483", [99])

        assert len(result) == 1
        assert "error" not in result[0]
        assert result[0]["id"] == 99


@pytest.mark.asyncio
async def test_ids_batched_omits_none_and_non_displayable():
    """Internal batched fetch skips deleted gaps without error dicts."""
    entity = Mock()
    present = make_mock_message(id=1, text="ok", date=datetime.now())
    empty = _make_message_empty(2)

    client = AsyncMock()
    client.get_messages = AsyncMock(return_value=[present, None, empty])

    loaded = await _get_messages_by_ids_batched(client, entity, [1, 2, 3])

    assert loaded == [present]
    assert not message_has_displayable_content(None)
    assert not message_has_displayable_content(empty)
