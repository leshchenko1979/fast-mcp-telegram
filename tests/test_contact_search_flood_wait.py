"""Tests for FloodWaitError handling in contact_search module."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import FloodWaitError

from src.tools.chat_discovery.contact_search import search_contacts_native


@pytest.mark.asyncio
async def test_flood_wait_raises_flood_wait(caplog):
    """FloodWaitError should be logged and re-raised as FloodWaitError (not wrapped)."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    from telethon.tl.functions.contacts import SearchRequest

    mock_client.side_effect = FloodWaitError(
        SearchRequest(q="test", limit=10),
        capture=42,
    )

    with (
        caplog.at_level(logging.WARNING, logger="src.tools.chat_discovery.contact_search"),
        patch(
            "src.tools.chat_discovery.contact_search.get_connected_client",
            return_value=mock_client,
        ),
        pytest.raises(FloodWaitError),
    ):
        async for _ in search_contacts_native(query="test", limit=10):
            pass

    assert any(
        "FloodWait" in r.message and "42" in r.message
        for r in caplog.records
    ), "FloodWait warning should be logged with seconds"


@pytest.mark.asyncio
async def test_flood_wait_logs_hours(caplog):
    """Log message should include hours for easier human reading."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    from telethon.tl.functions.contacts import SearchRequest

    mock_client.side_effect = FloodWaitError(
        SearchRequest(q="test", limit=10),
        capture=3600,
    )

    with (
        caplog.at_level(logging.WARNING, logger="src.tools.chat_discovery.contact_search"),
        patch(
            "src.tools.chat_discovery.contact_search.get_connected_client",
            return_value=mock_client,
        ),
        pytest.raises(FloodWaitError),
    ):
        async for _ in search_contacts_native(query="test", limit=10):
            pass

    assert any(
        "1.0h" in r.message
        for r in caplog.records
    ), "Log should include hours for 3600s flood wait"
