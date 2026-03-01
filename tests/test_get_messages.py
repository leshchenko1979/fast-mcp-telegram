"""
Tests for the unified get_messages tool and its various modes.

Tests cover:
- Parameter conflict validation
- Mode-specific functionality (search, browse, read by IDs, replies)
- Empty parameter edge cases
- Error handling for all modes
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.tools.search import search_messages_impl


class TestGetMessagesParameterConflicts:
    """Test parameter conflict validation."""

    @pytest.mark.asyncio
    async def test_message_ids_and_reply_to_id_conflict(self):
        """Should reject message_ids + reply_to_id combination."""
        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1, 2, 3],
            reply_to_id=100,
        )

        assert "error" in result
        assert "Cannot combine message_ids with reply_to_id" in result["error"]

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
    async def test_reply_to_id_requires_chat_id(self):
        """Should require chat_id when using reply_to_id."""
        result = await search_messages_impl(
            reply_to_id=100,
        )

        assert "error" in result
        assert "chat_id is required" in result["error"]


class TestGetMessagesReadByIds:
    """Test read by message IDs mode."""

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids", new_callable=AsyncMock)
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
        assert isinstance(result, dict)
        assert "messages" in result
        assert "has_more" in result
        assert len(result["messages"]) == 2
        assert result["has_more"] is False

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids", new_callable=AsyncMock)
    async def test_message_ids_ignores_other_params(self, mock_read):
        """Should ignore limit/date filters when using message_ids."""
        mock_read.return_value = [{"id": 1, "text": "Message"}]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1],
            limit=100,
            min_date="2024-01-01",
        )

        # Should call with only chat_id and message_ids
        mock_read.assert_called_once_with("me", [1])
        assert isinstance(result, dict)
        assert result["has_more"] is False

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids", new_callable=AsyncMock)
    async def test_returns_error_when_read_messages_by_ids_returns_error(
        self, mock_read
    ):
        """Should return raw error dict when read_messages_by_ids returns error."""
        mock_read.return_value = [{"error": "Message not found", "ok": False}]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[999],
        )

        mock_read.assert_called_once_with("me", [999])
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "Message not found"
        assert result["ok"] is False
        # Should NOT be wrapped in {"messages": ...}
        assert "messages" not in result


class TestGetMessagesReplies:
    """Test replies mode (post comments, forum topics, message replies)."""

    @pytest.mark.asyncio
    @patch("src.tools.search._handle_replies_mode", new_callable=AsyncMock)
    async def test_fetches_replies(self, mock_handler):
        """Should delegate to replies handler when reply_to_id provided."""
        mock_handler.return_value = {
            "messages": [
                {"id": 1, "text": "Reply 1"},
                {"id": 2, "text": "Reply 2"},
            ],
            "has_more": False,
            "reply_to_id": 100,
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
            limit=50,
        )

        # Verify handler was called correctly
        mock_handler.assert_called_once()
        call_args = mock_handler.call_args
        assert call_args[0][0] == "-1001111111111"  # chat_id
        assert call_args[0][1] == 100  # reply_to_id
        assert call_args[0][2] == 50  # limit
        assert call_args[0][3] is None  # query

        # Verify response structure
        assert "messages" in result
        assert "has_more" in result
        assert "reply_to_id" in result
        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    @patch("src.tools.search._handle_replies_mode", new_callable=AsyncMock)
    async def test_search_in_replies(self, mock_handler):
        """Should pass query to handler when both reply_to_id and query provided."""
        mock_handler.return_value = {
            "messages": [{"id": 1, "text": "Bug report"}],
            "has_more": False,
            "reply_to_id": 100,
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
            query="bug",
            limit=20,
        )

        # Verify query was passed
        call_args = mock_handler.call_args
        assert call_args[0][3] == "bug"  # query
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    @patch("src.tools.search._handle_replies_mode", new_callable=AsyncMock)
    async def test_no_replies_error(self, mock_handler):
        """Should return error when no replies found."""
        mock_handler.return_value = {
            "error": "No replies found for message 100",
            "ok": False,
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_chat_for_replies(self):
        """Should return error when chat_id missing for reply_to_id."""
        result = await search_messages_impl(
            reply_to_id=100,
        )

        assert "error" in result
        assert "chat_id is required" in result["error"]


class TestGetMessagesRepliesErrors:
    """Error paths for replies mode."""

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search._fetch_replies", new_callable=AsyncMock)
    async def test_fetch_replies_failure_returns_error(
        self, mock_fetch_replies, mock_get_entity, mock_get_client
    ):
        """Should return error when fetching replies raises."""
        mock_get_client.return_value = AsyncMock()
        mock_get_entity.return_value = Mock()
        mock_fetch_replies.side_effect = RuntimeError("network error")

        result = await search_messages_impl(
            chat_id="me",
            reply_to_id=123,
            limit=50,
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Failed to fetch replies" in result["error"]

    @pytest.mark.asyncio
    @patch("src.tools.search.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.get_entity_by_id", new_callable=AsyncMock)
    async def test_invalid_entity_for_replies(self, mock_get_entity, mock_get_client):
        """Should return error when entity not found."""
        mock_get_client.return_value = AsyncMock()
        mock_get_entity.return_value = None

        result = await search_messages_impl(
            chat_id="invalid_chat",
            reply_to_id=100,
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Could not find chat" in result["error"]


class TestGetMessagesSuccessPaths:
    """Test successful execution paths for different modes."""

    @pytest.mark.asyncio
    @patch("src.tools.search.read_messages_by_ids", new_callable=AsyncMock)
    async def test_message_ids_mode_success(self, mock_read):
        """message_ids mode should return unified dict format."""
        mock_read.return_value = [{"id": 1, "text": "Message"}]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1],
        )

        mock_read.assert_called_once()
        assert isinstance(result, dict)
        assert "messages" in result
        assert "has_more" in result
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_global_search_requires_query(self):
        """Global search without query should return error."""
        result = await search_messages_impl()

        assert "error" in result
        assert "global search" in result["error"].lower()
