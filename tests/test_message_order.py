"""Ascending date-time order at the tool output boundary.

Owner order (2026-10-01): every message list a tool returns is ordered by
ascending date-time. These tests drive ``search_messages_impl`` — the shared
implementation behind both ``get_messages`` and ``search_messages_globally`` —
with newest-first fixtures and assert the payload comes back oldest-first
without changing which messages were selected.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.tools.search import search_messages_impl
from tests.conftest import make_mock_message


def _dated(msg_id: int, year: int, month: int = 1, day: int = 1):
    return make_mock_message(
        id=msg_id, text=f"message {msg_id}", date=datetime(year, month, day, tzinfo=UTC)
    )

async def _iter_newest_first(messages):
    for message in messages:
        yield message

def _search_mode_patches(func):
    """Patch the client/entity lookups the per-chat search path uses.

    Applied so the decorated function receives ``(mock_get_entity,
    mock_get_client)`` — the decorator closest to the function is the first
    argument.
    """
    targets = (
        "src.tools.search.search_mode.get_entity_by_id",
        "src.tools.search.search_mode.get_connected_client",
    )
    for target in targets:
        func = patch(target, new_callable=AsyncMock)(func)
    return func

class TestAscendingOrderThroughSearchImpl:
    """Order is applied at the shared boundary, for every mode."""

    @pytest.mark.asyncio
    @_search_mode_patches
    async def test_browse_returns_ascending_dates(self, mock_get_entity, mock_get_client):
        """Newest-first from Telethon comes back oldest-first."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_client.iter_messages = MagicMock(
            return_value=_iter_newest_first(
                [_dated(3, 2025), _dated(2, 2024), _dated(1, 2023)]
            )
        )
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(chat_id="me", limit=50)

        assert "error" not in result
        ids = [m["id"] for m in result["messages"]]
        assert ids == [1, 2, 3]
        dates = [m["date"] for m in result["messages"]]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    @_search_mode_patches
    async def test_window_membership_and_has_more_unchanged(
        self, mock_get_entity, mock_get_client
    ):
        """Still the NEWEST N messages — only their order changed."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_client.iter_messages = MagicMock(
            return_value=_iter_newest_first(
                [_dated(4, 2026), _dated(3, 2025), _dated(2, 2024), _dated(1, 2023)]
            )
        )
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(chat_id="me", limit=2)

        assert "error" not in result
        # The two newest (3, 4) are still the ones selected, now oldest-first.
        assert [m["id"] for m in result["messages"]] == [3, 4]
        assert result["has_more"] is True

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_message_ids_mode_returns_ascending_dates(self, mock_read):
        """message_ids mode no longer echoes request order."""
        mock_read.return_value = [
            {"id": 30, "date": "2025-01-01T00:00:00+00:00", "text": "c"},
            {"id": 10, "date": "2023-01-01T00:00:00+00:00", "text": "a"},
            {"id": 20, "date": "2024-01-01T00:00:00+00:00", "text": "b"},
        ]

        result = await search_messages_impl(
            chat_id="123", message_ids=[30, 10, 20]
        )

        assert [m["id"] for m in result["messages"]] == [10, 20, 30]
        assert result["has_more"] is False

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_message_ids_stubs_sort_last(self, mock_read):
        """Missing-id stubs carry no date, so they land after dated messages."""
        mock_read.return_value = [
            {"id": 99, "chat": {"id": 1}, "error": "Message not found or inaccessible"},
            {"id": 10, "date": "2023-01-01T00:00:00+00:00", "text": "a"},
        ]

        result = await search_messages_impl(chat_id="123", message_ids=[99, 10])

        assert [m["id"] for m in result["messages"]] == [10, 99]
        assert result["messages"][-1]["error"] == "Message not found or inaccessible"

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_single_operational_error_passes_through(self, mock_read):
        """An error envelope has no messages list and must not be reordered."""
        mock_read.return_value = [
            {"ok": False, "operation": "read_messages", "error": "boom"}
        ]

        result = await search_messages_impl(chat_id="123", message_ids=[1])

        assert result["ok"] is False
        assert result["error"] == "boom"
