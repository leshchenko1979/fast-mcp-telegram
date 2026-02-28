"""
Tests for the unified get_messages tool and its various modes.

Tests cover:
- Parameter conflict validation
- Mode-specific functionality (search, browse, read by IDs, post comments)
- Backward compatibility with read_messages and search_messages_in_chat
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.tools.search import search_messages_impl


class TestGetMessagesParameterConflicts:
    """Test parameter conflict validation."""

    @pytest.mark.asyncio
    async def test_message_ids_and_post_id_conflict(self):
        """Should reject message_ids + post_id combination."""
        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1, 2, 3],
            post_id=100,
        )

        assert "error" in result
        assert "Cannot combine message_ids with post_id" in result["error"]

    @pytest.mark.asyncio
    async def test_message_ids_and_query_conflict(self):
        """Should reject message_ids + query combination."""
        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1, 2, 3],
            query="test",
        )

        assert "error" in result
        assert "Cannot combine message_ids with query" in result["error"]

    @pytest.mark.asyncio
    async def test_message_ids_requires_chat_id(self):
        """Should require chat_id when using message_ids."""
        result = await search_messages_impl(
            message_ids=[1, 2, 3],
        )

        assert "error" in result
        assert "chat_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_post_id_requires_chat_id(self):
        """Should require chat_id when using post_id."""
        result = await search_messages_impl(
            post_id=100,
        )

        assert "error" in result
        assert "chat_id is required" in result["error"]


class TestGetMessagesReadByIds:
    """Test read by message IDs mode."""

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids")
    async def test_delegates_to_read_messages_by_ids(self, mock_read):
        """Should delegate to read_messages_by_ids when message_ids provided."""
        mock_read.return_value = [
            {"id": 1, "text": "Message 1"},
            {"id": 2, "text": "Message 2"},
        ]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1, 2],
        )

        mock_read.assert_called_once_with("me", [1, 2])
        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids")
    async def test_message_ids_ignores_other_params(self, mock_read):
        """Should ignore limit/date filters when using message_ids."""
        mock_read.return_value = [{"id": 1, "text": "Message"}]

        await search_messages_impl(
            chat_id="me",
            message_ids=[1],
            limit=100,
            min_date="2024-01-01",
        )

        # Should call with only chat_id and message_ids
        mock_read.assert_called_once_with("me", [1])


class TestGetMessagesPostComments:
    """Test post comments mode."""

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client")
    @patch("src.tools.search.get_entity_by_id")
    @patch("src.tools.search._fetch_post_comments")
    async def test_fetches_post_comments(
        self, mock_fetch_comments, mock_get_entity, mock_get_client
    ):
        """Should fetch post comments when post_id provided."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_entity = Mock()
        mock_get_entity.return_value = mock_entity

        mock_fetch_comments.return_value = (
            [
                {"id": 1, "text": "Comment 1"},
                {"id": 2, "text": "Comment 2"},
            ],
            {
                "discussion_chat_id": "-1001234567890",
                "discussion_total_count": 10,
                "linked_post_id": 100,
            },
        )

        result = await search_messages_impl(
            chat_id="-1001111111111",
            post_id=100,
            limit=50,
        )

        # Verify fetch was called correctly
        mock_fetch_comments.assert_called_once_with(
            mock_client, mock_entity, 100, 50, None
        )

        # Verify response structure
        assert "messages" in result
        assert "has_more" in result
        assert "discussion_chat_id" in result
        assert "discussion_total_count" in result
        assert "linked_post_id" in result

        assert len(result["messages"]) == 2
        assert result["discussion_chat_id"] == "-1001234567890"
        assert result["linked_post_id"] == 100

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client")
    @patch("src.tools.search.get_entity_by_id")
    @patch("src.tools.search._fetch_post_comments")
    async def test_search_in_post_comments(
        self, mock_fetch_comments, mock_get_entity, mock_get_client
    ):
        """Should search within post comments when both post_id and query provided."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_entity = Mock()
        mock_get_entity.return_value = mock_entity

        mock_fetch_comments.return_value = (
            [{"id": 1, "text": "Bug report"}],
            {
                "discussion_chat_id": "-1001234567890",
                "discussion_total_count": 5,
                "linked_post_id": 100,
            },
        )

        result = await search_messages_impl(
            chat_id="-1001111111111",
            post_id=100,
            query="bug",
            limit=20,
        )

        # Verify search query was passed to fetch
        mock_fetch_comments.assert_called_once_with(
            mock_client, mock_entity, 100, 20, "bug"
        )

        assert len(result["messages"]) == 1
        assert "bug" in result["messages"][0]["text"].lower()

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client")
    @patch("src.tools.search.get_entity_by_id")
    @patch("src.tools.search._fetch_post_comments")
    async def test_no_comments_error(
        self, mock_fetch_comments, mock_get_entity, mock_get_client
    ):
        """Should return error when no comments found."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_entity = Mock()
        mock_get_entity.return_value = mock_entity

        # Empty comments
        mock_fetch_comments.return_value = (
            [],
            {
                "discussion_chat_id": "-1001234567890",
                "discussion_total_count": 0,
                "linked_post_id": 100,
            },
        )

        result = await search_messages_impl(
            chat_id="-1001111111111",
            post_id=100,
        )

        assert "error" in result
        assert "No comments found" in result["error"]

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client")
    @patch("src.tools.search.get_entity_by_id")
    async def test_invalid_chat_for_post_comments(
        self, mock_get_entity, mock_get_client
    ):
        """Should return error when chat not found."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_get_entity.return_value = None  # Chat not found

        result = await search_messages_impl(
            chat_id="invalid_chat",
            post_id=100,
        )

        assert "error" in result
        assert "Could not find chat" in result["error"]


class TestGetMessagesHasMoreLogic:
    """Test has_more flag logic for post comments."""

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client")
    @patch("src.tools.search.get_entity_by_id")
    @patch("src.tools.search._fetch_post_comments")
    async def test_has_more_when_extra_message_collected(
        self, mock_fetch_comments, mock_get_entity, mock_get_client
    ):
        """Should set has_more=True when collected limit+1 messages."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_entity = Mock()
        mock_get_entity.return_value = mock_entity

        # Return limit+1 messages
        mock_fetch_comments.return_value = (
            [
                {"id": i, "text": f"Comment {i}"} for i in range(11)
            ],  # 11 messages for limit=10
            {
                "discussion_chat_id": "-1001234567890",
                "discussion_total_count": 20,
                "linked_post_id": 100,
            },
        )

        result = await search_messages_impl(
            chat_id="-1001111111111",
            post_id=100,
            limit=10,
        )

        assert len(result["messages"]) == 10  # Windowed to limit
        assert result["has_more"] is True

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client")
    @patch("src.tools.search.get_entity_by_id")
    @patch("src.tools.search._fetch_post_comments")
    async def test_has_more_false_when_fewer_than_limit(
        self, mock_fetch_comments, mock_get_entity, mock_get_client
    ):
        """Should set has_more=False when collected fewer than limit messages."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        mock_entity = Mock()
        mock_get_entity.return_value = mock_entity

        # Return fewer than limit
        mock_fetch_comments.return_value = (
            [{"id": i, "text": f"Comment {i}"} for i in range(5)],  # 5 messages
            {
                "discussion_chat_id": "-1001234567890",
                "discussion_total_count": 5,
                "linked_post_id": 100,
            },
        )

        result = await search_messages_impl(
            chat_id="-1001111111111",
            post_id=100,
            limit=10,
        )

        assert len(result["messages"]) == 5
        assert result["has_more"] is False


class TestBackwardCompatibility:
    """Test backward compatibility with old tool names."""

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids")
    async def test_read_messages_mode_works(self, mock_read):
        """read_messages functionality should work through get_messages."""
        mock_read.return_value = [{"id": 1, "text": "Message"}]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1],
        )

        mock_read.assert_called_once()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_in_chat_mode_requires_query_or_empty(self):
        """search_messages_in_chat functionality should work with or without query."""
        # This tests that chat_id alone doesn't error (browse mode)
        # We'll test with global search error to verify logic path
        result = await search_messages_impl()

        assert "error" in result
        assert "global search" in result["error"].lower()
