#!/usr/bin/env python3
"""
Unit tests for Telegram link generation functionality.

Tests the links.py module including link generation for public/private chats,
query parameter handling, entity resolution, and error cases.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tools.links import (
    _build_query_string,
    _normalize_channel_id,
    _resolve_entity_for_links,
    generate_telegram_links,
)


class TestNormalizeChannelId:
    """Test channel ID normalization."""

    def test_normalize_regular_channel_id(self):
        """Test normalizing regular channel IDs."""
        assert _normalize_channel_id("-1001234567890") == "1234567890"
        assert _normalize_channel_id("-1009876543210") == "9876543210"

    def test_normalize_non_channel_id(self):
        """Test IDs that don't need normalization."""
        assert _normalize_channel_id("1234567890") == "1234567890"
        assert _normalize_channel_id("me") == "me"
        assert _normalize_channel_id("@username") == "@username"

    def test_normalize_empty_string(self):
        """Test empty string handling."""
        assert _normalize_channel_id("") == ""


class TestBuildQueryString:
    """Test query string building."""

    def test_no_parameters(self):
        """Test with no query parameters."""
        assert _build_query_string() == ""

    def test_single_parameter(self):
        """Test with single query parameter."""
        assert _build_query_string(thread_id=123) == "?thread=123"
        assert _build_query_string(comment_id=456) == "?comment=456"
        assert _build_query_string(media_timestamp=789) == "?t=789"

    def test_multiple_parameters(self):
        """Test with multiple query parameters."""
        query = _build_query_string(thread_id=123, comment_id=456)
        assert query in ["?thread=123&comment=456", "?comment=456&thread=123"]

    def test_all_parameters(self):
        """Test with all query parameters."""
        query = _build_query_string(thread_id=123, comment_id=456, media_timestamp=789)
        # Check that all parameters are present
        assert "thread=123" in query
        assert "comment=456" in query
        assert "t=789" in query
        assert query.startswith("?")


class TestResolveEntityForLinks:
    """Test entity resolution for links."""

    @pytest.mark.asyncio
    async def test_resolve_public_entity(self, monkeypatch):
        """Test resolving a public entity with username."""
        # Mock the client and entity
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        mock_client = AsyncMock()
        monkeypatch.setattr(
            "src.tools.links.get_connected_client", AsyncMock(return_value=mock_client)
        )

        mock_get_entity = AsyncMock(return_value=mock_entity)
        monkeypatch.setattr("src.tools.links.get_entity_by_id", mock_get_entity)

        is_public, username, entity = await _resolve_entity_for_links("testchannel")

        assert is_public is True
        assert username == "testchannel"
        assert entity == mock_entity
        mock_get_entity.assert_called_once_with("testchannel")

    @pytest.mark.asyncio
    async def test_resolve_private_entity(self, monkeypatch):
        """Test resolving a private entity without username."""
        # Mock the client and entity
        mock_entity = MagicMock()
        mock_entity.username = None
        mock_entity.id = -1001234567890

        mock_client = AsyncMock()
        monkeypatch.setattr(
            "src.tools.links.get_connected_client", AsyncMock(return_value=mock_client)
        )

        mock_get_entity = AsyncMock(return_value=mock_entity)
        monkeypatch.setattr("src.tools.links.get_entity_by_id", mock_get_entity)

        is_public, username, entity = await _resolve_entity_for_links("-1001234567890")

        assert is_public is False
        assert username is None
        assert entity == mock_entity

    @pytest.mark.asyncio
    async def test_resolve_with_pre_resolved_entity(self, monkeypatch):
        """Test using pre-resolved entity to skip API calls."""
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        # Should not call get_connected_client or get_entity_by_id
        is_public, username, entity = await _resolve_entity_for_links(
            "testchannel", resolved_entity=mock_entity
        )

        assert is_public is True
        assert username == "testchannel"
        assert entity == mock_entity

    @pytest.mark.asyncio
    async def test_resolve_entity_not_found(self, monkeypatch):
        """Test handling when entity cannot be resolved."""
        mock_client = AsyncMock()
        monkeypatch.setattr(
            "src.tools.links.get_connected_client", AsyncMock(return_value=mock_client)
        )

        mock_get_entity = AsyncMock(return_value=None)
        monkeypatch.setattr("src.tools.links.get_entity_by_id", mock_get_entity)

        is_public, username, entity = await _resolve_entity_for_links("nonexistent")

        assert is_public is False
        assert username is None
        assert entity is None

    @pytest.mark.asyncio
    async def test_resolve_with_username_fallback(self, monkeypatch):
        """Test fallback to username when chat_id doesn't resolve."""
        # Mock the client and entities
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        mock_client = AsyncMock()
        monkeypatch.setattr(
            "src.tools.links.get_connected_client", AsyncMock(return_value=mock_client)
        )

        mock_get_entity = AsyncMock(
            side_effect=[None, mock_entity]
        )  # First call fails, second succeeds
        monkeypatch.setattr("src.tools.links.get_entity_by_id", mock_get_entity)

        is_public, username, entity = await _resolve_entity_for_links(
            "123456789", username="testchannel"
        )

        assert is_public is True
        assert username == "testchannel"
        assert entity == mock_entity
        assert mock_get_entity.call_count == 2


class TestGenerateTelegramLinks:
    """Test the main generate_telegram_links function."""

    @pytest.mark.asyncio
    async def test_public_chat_links(self, monkeypatch):
        """Test link generation for public chats."""
        # Mock the entity resolution
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(True, "testchannel", mock_entity)),
        )

        result = await generate_telegram_links("testchannel", [123, 456])

        assert "public_chat_link" in result
        assert result["public_chat_link"] == "https://t.me/testchannel"
        assert "message_links" in result
        assert len(result["message_links"]) == 2
        assert result["message_links"][0] == "https://t.me/testchannel/123"
        assert result["message_links"][1] == "https://t.me/testchannel/456"
        assert "note" in result

    @pytest.mark.asyncio
    async def test_private_chat_links(self, monkeypatch):
        """Test link generation for private chats."""
        # Mock the entity resolution
        mock_entity = MagicMock()
        mock_entity.username = None
        mock_entity.id = -1001234567890

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(False, None, mock_entity)),
        )

        result = await generate_telegram_links("-1001234567890", [789])

        assert "private_chat_link" in result
        assert result["private_chat_link"] == "https://t.me/c/1234567890"
        assert "message_links" in result
        assert len(result["message_links"]) == 1
        assert result["message_links"][0] == "https://t.me/c/1234567890/789"
        assert "note" in result

    @pytest.mark.asyncio
    async def test_public_chat_with_thread(self, monkeypatch):
        """Test public chat links with thread ID."""
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(True, "testchannel", mock_entity)),
        )

        result = await generate_telegram_links("testchannel", [123], thread_id=456)

        assert (
            result["message_links"][0] == "https://t.me/testchannel/456/123?thread=456"
        )

    @pytest.mark.asyncio
    async def test_private_chat_with_thread(self, monkeypatch):
        """Test private chat links with thread ID."""
        mock_entity = MagicMock()
        mock_entity.username = None
        mock_entity.id = -1001234567890

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(False, None, mock_entity)),
        )

        result = await generate_telegram_links("-1001234567890", [789], thread_id=999)

        assert (
            result["message_links"][0] == "https://t.me/c/1234567890/999/789?thread=999"
        )

    @pytest.mark.asyncio
    async def test_links_with_all_parameters(self, monkeypatch):
        """Test links with thread_id, comment_id, and media_timestamp."""
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(True, "testchannel", mock_entity)),
        )

        result = await generate_telegram_links(
            "testchannel", [123], thread_id=456, comment_id=789, media_timestamp=1000
        )

        link = result["message_links"][0]
        # Check that all parameters are present in query string
        assert "thread=456" in link
        assert "comment=789" in link
        assert "t=1000" in link
        assert link.startswith("https://t.me/testchannel/456/123?")

    @pytest.mark.asyncio
    async def test_no_message_ids(self, monkeypatch):
        """Test when no message IDs are provided."""
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(True, "testchannel", mock_entity)),
        )

        result = await generate_telegram_links("testchannel")

        assert "public_chat_link" in result
        assert "message_links" not in result
        assert "note" in result

    @pytest.mark.asyncio
    async def test_entity_resolution_failure(self, monkeypatch):
        """Test handling when entity cannot be resolved."""
        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(False, None, None)),
        )

        result = await generate_telegram_links("nonexistent", [123])

        assert "note" in result
        assert "Cannot resolve chat entity" in result["note"]
        assert "message_links" not in result

    @pytest.mark.asyncio
    async def test_with_resolved_entity(self, monkeypatch):
        """Test using pre-resolved entity for performance."""
        mock_entity = MagicMock()
        mock_entity.username = "testchannel"
        mock_entity.id = 123456789

        # Mock the entity resolution to return our pre-resolved entity
        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(True, "testchannel", mock_entity)),
        )

        result = await generate_telegram_links(
            "testchannel", [123], resolved_entity=mock_entity
        )

        assert "public_chat_link" in result
        assert result["message_links"][0] == "https://t.me/testchannel/123"

    @pytest.mark.asyncio
    async def test_username_normalization(self, monkeypatch):
        """Test that @ prefix is stripped from usernames."""
        mock_entity = MagicMock()
        mock_entity.username = "@testchannel"  # Username with @
        mock_entity.id = 123456789

        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(return_value=(True, "@testchannel", mock_entity)),
        )

        result = await generate_telegram_links("@testchannel", [123])

        # Should strip @ from link generation
        assert result["public_chat_link"] == "https://t.me/testchannel"
        assert result["message_links"][0] == "https://t.me/testchannel/123"

    @pytest.mark.asyncio
    async def test_error_handling(self, monkeypatch):
        """Test error handling in link generation."""
        # Mock entity resolution to raise an exception
        monkeypatch.setattr(
            "src.tools.links._resolve_entity_for_links",
            AsyncMock(side_effect=Exception("Test error")),
        )

        with pytest.raises(Exception) as exc_info:
            await generate_telegram_links("test", [123])

        assert "Test error" in str(exc_info.value)
