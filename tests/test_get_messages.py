"""
Tests for the unified get_messages tool and its various modes.

Tests cover:
- Parameter conflict validation
- Mode-specific functionality (search, browse, read by IDs, replies)
- Empty parameter edge cases
- Error handling for all modes
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.tools.search import search_messages_impl
from tests.conftest import make_mock_message


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
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
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
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_message_ids_rejects_date_filters(self, mock_read):
        """Should reject date filters when using message_ids."""
        mock_read.return_value = [{"id": 1, "text": "Message"}]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1],
            limit=100,
            min_date="2024-01-01",
        )

        assert "error" in result
        assert "not supported for message_ids mode" in result["error"]

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
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
    @patch("src.tools.search.core._handle_reply_mode", new_callable=AsyncMock)
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
    @patch("src.tools.search.core._handle_reply_mode", new_callable=AsyncMock)
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
    @patch("src.tools.search.core._handle_reply_mode", new_callable=AsyncMock)
    async def test_no_replies_empty_with_note(self, mock_handler):
        """Empty replies should return success with note, not error."""
        mock_handler.return_value = {
            "messages": [],
            "has_more": False,
            "reply_to_id": 100,
            "note": "No replies found for message 100",
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
        )

        assert result["messages"] == []
        assert "note" in result
        assert "error" not in result

    @pytest.mark.asyncio
    @patch("src.tools.search.core._handle_query_mode", new_callable=AsyncMock)
    async def test_empty_search_returns_note_not_error(self, mock_handler):
        """Empty search should return success with note (ADR 0012)."""
        mock_handler.return_value = {
            "messages": [],
            "has_more": False,
            "note": "No messages found matching query 'missing'",
        }

        result = await search_messages_impl(
            chat_id="me",
            query="missing",
            limit=10,
        )

        assert result["messages"] == []
        assert "note" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_invalid_chat_for_replies(self):
        """Should return error when chat_id missing for reply_to_id."""
        result = await search_messages_impl(
            reply_to_id=100,
        )

        assert "error" in result
        assert "chat_id is required" in result["error"]

    @pytest.mark.asyncio
    @patch("src.tools.search.core._handle_reply_mode", new_callable=AsyncMock)
    async def test_replies_accepts_min_date(self, mock_handler):
        """Should pass min_date to handler without error."""
        mock_handler.return_value = {
            "messages": [{"id": 1, "text": "Reply"}],
            "has_more": False,
            "reply_to_id": 100,
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
            min_date="2024-01-01",
            limit=50,
        )

        assert "error" not in result
        mock_handler.assert_called_once()
        assert mock_handler.call_args[1]["min_date"] == "2024-01-01"

    @pytest.mark.asyncio
    @patch("src.tools.search.core._handle_reply_mode", new_callable=AsyncMock)
    async def test_replies_accepts_max_date(self, mock_handler):
        """Should pass max_date to handler without error."""
        mock_handler.return_value = {
            "messages": [{"id": 1, "text": "Reply"}],
            "has_more": False,
            "reply_to_id": 100,
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
            max_date="2024-12-31",
            limit=50,
        )

        assert "error" not in result
        mock_handler.assert_called_once()
        assert mock_handler.call_args[1]["max_date"] == "2024-12-31"

    @pytest.mark.asyncio
    @patch("src.tools.search.core._handle_reply_mode", new_callable=AsyncMock)
    async def test_replies_accepts_date_range(self, mock_handler):
        """Should pass both min_date and max_date to handler without error."""
        mock_handler.return_value = {
            "messages": [{"id": 1, "text": "Reply"}],
            "has_more": False,
            "reply_to_id": 100,
        }

        result = await search_messages_impl(
            chat_id="-1001111111111",
            reply_to_id=100,
            min_date="2024-01-01",
            max_date="2024-12-31",
            limit=50,
        )

        assert "error" not in result
        mock_handler.assert_called_once()
        assert mock_handler.call_args[1]["min_date"] == "2024-01-01"
        assert mock_handler.call_args[1]["max_date"] == "2024-12-31"


class TestGetMessagesRepliesErrors:
    """Error paths for replies mode."""

    @pytest.mark.asyncio
    @patch("src.tools.search.replies.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.replies.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.replies._fetch_replies", new_callable=AsyncMock)
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
    @patch("src.tools.search.replies.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.replies.get_entity_by_id", new_callable=AsyncMock)
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
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
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


class TestGetMessagesChatFieldExclusion:
    """Test that chat field is excluded when chat_id is provided."""

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    async def test_global_search_includes_chat_field(self, mock_get_client):
        """Global search (no chat_id) should include chat in each message."""
        from telethon.tl.types import PeerUser

        mock_client = AsyncMock()
        mock_msg = make_mock_message(
            id=1,
            text="global search result",
            date=datetime.now(),
            peer_id=PeerUser(user_id=123),
        )

        mock_search_result = Mock()
        mock_search_result.messages = [mock_msg]
        mock_client.return_value = mock_search_result
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        mock_chat = Mock()
        mock_chat.id = 456
        mock_chat.title = "Some Chat"
        mock_chat.username = "somechat"
        mock_chat.broadcast = False

        async def mock_get_entity(peer):
            return mock_chat

        mock_get_client.return_value = mock_client

        with patch(
            "src.tools.search.search_generators.get_entity_by_id",
            side_effect=mock_get_entity,
        ):
            result = await search_messages_impl(
                chat_id=None,
                query="hello",
                limit=5,
            )

        if "messages" in result:
            for msg in result["messages"]:
                assert "chat" in msg, (
                    f"Expected chat field in global search result, got {msg.keys()}"
                )


class TestGetMessagesRepliesChatExclusion:
    """Test that replies mode excludes chat field."""

    @pytest.mark.asyncio
    @patch("src.tools.search.replies.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.replies.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.replies._fetch_replies", new_callable=AsyncMock)
    async def test_replies_mode_excludes_chat_field(
        self, mock_fetch_replies, mock_get_entity, mock_get_client
    ):
        """Replies mode should exclude chat from returned messages."""
        mock_get_client.return_value = AsyncMock()
        mock_entity = Mock()
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_fetch_replies.return_value = (
            [
                {"id": 10, "text": "reply 1"},  # no chat key
                {"id": 11, "text": "reply 2"},  # no chat key
            ],
            None,
        )

        result = await search_messages_impl(
            chat_id="testchat",
            reply_to_id=5,
            limit=10,
        )

        assert "messages" in result
        for msg in result["messages"]:
            assert "chat" not in msg


class TestReadMessagesByIdsChatExclusion:
    """Test that read_messages_by_ids excludes chat field."""

    @pytest.mark.asyncio
    @patch("src.tools.messages.reading.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.messages.reading.get_entity_by_id", new_callable=AsyncMock)
    async def test_read_messages_by_ids_excludes_chat_field(
        self, mock_get_entity, mock_get_client
    ):
        """read_messages_by_ids should exclude chat from returned messages."""
        from src.tools.messages.reading import read_messages_by_ids

        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Chat"
        mock_entity.username = "testchat"

        mock_get_entity.return_value = mock_entity

        mock_msg = make_mock_message(
            id=1,
            text="message text",
            date=datetime.now(),
        )

        mock_client = AsyncMock()
        mock_client.get_messages = AsyncMock(return_value=[mock_msg])
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_get_client.return_value = mock_client

        with patch(
            "src.tools.messages.reading.generate_telegram_links",
            new=AsyncMock(return_value={"message_links": ["https://t.me/testchat/1"]}),
        ):
            result = await read_messages_by_ids("testchat", [1])

        assert len(result) == 1
        assert "chat" not in result[0], (
            f"Expected no chat field, got {result[0].keys()}"
        )


class TestGetMessagesChatFieldIntegration:
    """Integration tests for chat field exclusion behavior."""

    @pytest.mark.asyncio
    @patch("src.tools.search.core.read_messages_by_ids", new_callable=AsyncMock)
    async def test_message_ids_mode_excludes_chat_field(self, mock_read):
        """message_ids mode should exclude chat from results."""
        mock_read.return_value = [
            {"id": 1, "text": "Message 1"},  # no chat
            {"id": 2, "text": "Message 2"},  # no chat
        ]

        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1, 2],
        )

        assert "messages" in result
        for msg in result["messages"]:
            assert "chat" not in msg, (
                f"Expected no chat in message_ids mode, got {msg.get('chat')}"
            )


class TestGetMessagesFromUser:
    """Test from_user parameter for sender filtering."""

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_from_user_passed_to_iter_messages(
        self, mock_get_entity, mock_get_client, mock_gen_get_entity
    ):
        """Should pass from_user to client.iter_messages for server-side filtering."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        # from_user resolves to a user entity via get_entity_by_id
        mock_user_entity = Mock()
        mock_user_entity.id = 456
        mock_gen_get_entity.return_value = mock_user_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        msg = make_mock_message(
            id=1, text="Hello", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter_messages_gen():
            yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        await search_messages_impl(
            chat_id="me",
            query="hello",
            from_user="alice",
            limit=10,
        )

        # Verify from_user was resolved and passed to iter_messages
        mock_gen_get_entity.assert_called_once_with("alice")
        mock_client.iter_messages.assert_called_once()
        call_kwargs = mock_client.iter_messages.call_args
        assert call_kwargs[1].get("from_user") is mock_user_entity

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_from_user_without_query(
        self, mock_get_entity, mock_get_client, mock_gen_get_entity
    ):
        """Should work with from_user only (browse mode with sender filter)."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_user_entity = Mock()
        mock_user_entity.id = 456
        mock_gen_get_entity.return_value = mock_user_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        msg = make_mock_message(
            id=1, text="Hello", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter_messages_gen():
            yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        await search_messages_impl(
            chat_id="me",
            from_user="alice",
            limit=10,
        )

        # Verify from_user was resolved and passed to iter_messages even without query
        mock_gen_get_entity.assert_called_once_with("alice")
        mock_client.iter_messages.assert_called_once()
        call_kwargs = mock_client.iter_messages.call_args
        assert call_kwargs[1].get("from_user") is mock_user_entity

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_from_user_with_query_and_date(
        self, mock_get_entity, mock_get_client, mock_gen_get_entity
    ):
        """Should combine from_user with query and date filters."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_user_entity = Mock()
        mock_user_entity.id = 456
        mock_gen_get_entity.return_value = mock_user_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        msg = make_mock_message(
            id=1, text="Hello", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter_messages_gen():
            yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query="hello",
            from_user="alice",
            min_date="2024-01-01",
            max_date="2024-12-31",
            limit=10,
        )

        assert "messages" in result
        mock_client.iter_messages.assert_called_once()
        call_kwargs = mock_client.iter_messages.call_args
        assert call_kwargs[1].get("from_user") is mock_user_entity

    @pytest.mark.asyncio
    async def test_from_user_with_message_ids_returns_error(self):
        """Should reject from_user with message_ids mode."""
        result = await search_messages_impl(
            chat_id="me",
            message_ids=[123],
            from_user="alice",
            limit=10,
        )
        assert "error" in result
        assert "from_user is not supported" in result["error"]
        assert "ids" in result["error"]

    @pytest.mark.asyncio
    async def test_from_user_with_reply_to_id_returns_error(self):
        """Should reject from_user with reply_to_id mode."""
        result = await search_messages_impl(
            chat_id="me",
            reply_to_id=456,
            from_user="alice",
            limit=10,
        )
        assert "error" in result
        assert "from_user is not supported" in result["error"]
        assert "reply" in result["error"]

    @pytest.mark.asyncio
    async def test_from_user_with_global_search_returns_error(self):
        """Should reject from_user without chat_id (global search)."""
        result = await search_messages_impl(
            query="hello",
            from_user="alice",
            limit=10,
        )
        assert "error" in result
        assert "from_user requires chat_id" in result["error"]

    @pytest.mark.asyncio
    async def test_from_user_empty_string_returns_error(self):
        """Should reject empty string from_user."""
        result = await search_messages_impl(
            chat_id="me",
            query="hello",
            from_user="",
            limit=10,
        )
        assert "error" in result
        assert "from_user must not be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_from_user_whitespace_only_returns_error(self):
        """Should reject whitespace-only from_user."""
        result = await search_messages_impl(
            chat_id="me",
            query="hello",
            from_user="   ",
            limit=10,
        )
        assert "error" in result
        assert "from_user must not be empty" in result["error"]


class TestGetMessagesDateFiltering:
    """Test min_date/max_date filtering for per-chat search."""

    @pytest.mark.asyncio
    async def test_invalid_min_date_returns_error(self):
        result = await search_messages_impl(
            chat_id="me",
            query="hi",
            min_date="not-iso",
            limit=10,
        )
        assert "error" in result
        assert result["operation"] == "get_messages"
        assert "Invalid min_date format" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_max_date_returns_error(self):
        result = await search_messages_impl(
            chat_id="me",
            query="hi",
            max_date="bogus",
            limit=10,
        )
        assert "error" in result
        assert "Invalid max_date format" in result["error"]

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_search_chat_respects_min_date(
        self, mock_get_entity, mock_get_client
    ):
        """Should filter out messages older than min_date."""
        from tests.conftest import make_mock_message

        # Set up entity mock
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        # Set up client mock with iter_messages
        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        # Create messages with different dates
        old_msg = make_mock_message(
            id=1, text="Old message", date=datetime(2023, 1, 1, tzinfo=UTC)
        )
        recent_msg = make_mock_message(
            id=2, text="Recent message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )
        future_msg = make_mock_message(
            id=3, text="Future message", date=datetime(2025, 1, 1, tzinfo=UTC)
        )

        # Return messages in order (newest to oldest when iterated)
        # iter_messages is an async iterator, so we need to return an async iterator
        async def mock_iter_messages_gen():
            for msg in [future_msg, recent_msg, old_msg]:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query="message",
            min_date="2024-01-01",
            limit=50,
        )

        assert "messages" in result
        # Should return 2 messages (2024 and 2025), not 2023
        assert len(result["messages"]) == 2
        msg_ids = {msg["id"] for msg in result["messages"]}
        assert 1 not in msg_ids  # Old message should be filtered
        assert 2 in msg_ids  # Recent message should be included
        assert 3 in msg_ids  # Future message should be included

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_search_chat_respects_max_date(
        self, mock_get_entity, mock_get_client
    ):
        """Should filter out messages newer than max_date."""
        from tests.conftest import make_mock_message

        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        old_msg = make_mock_message(
            id=1, text="Old message", date=datetime(2023, 1, 1, tzinfo=UTC)
        )
        recent_msg = make_mock_message(
            id=2, text="Recent message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )
        future_msg = make_mock_message(
            id=3, text="Future message", date=datetime(2025, 1, 1, tzinfo=UTC)
        )

        async def mock_iter_messages_gen():
            for msg in [future_msg, recent_msg, old_msg]:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query="message",
            max_date="2024-12-31",
            limit=50,
        )

        assert "messages" in result
        # Should return 2 messages (2023 and 2024), not 2025
        assert len(result["messages"]) == 2
        msg_ids = {msg["id"] for msg in result["messages"]}
        assert 3 not in msg_ids  # Future message should be filtered
        assert 2 in msg_ids  # Recent message should be included
        assert 1 in msg_ids  # Old message should be included

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_search_chat_respects_date_range(
        self, mock_get_entity, mock_get_client
    ):
        """Should filter to only messages within min_date and max_date range."""
        from tests.conftest import make_mock_message

        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        old_msg = make_mock_message(
            id=1, text="Old message", date=datetime(2023, 1, 1, tzinfo=UTC)
        )
        recent_msg = make_mock_message(
            id=2, text="Recent message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )
        future_msg = make_mock_message(
            id=3, text="Future message", date=datetime(2025, 1, 1, tzinfo=UTC)
        )

        async def mock_iter_messages_gen():
            for msg in [future_msg, recent_msg, old_msg]:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query="message",
            min_date="2024-01-01",
            max_date="2024-12-31",
            limit=50,
        )

        assert "messages" in result
        # Should return only 1 message (2024-06-15)
        assert len(result["messages"]) == 1
        assert result["messages"][0]["id"] == 2

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_search_chat_stops_at_min_date_boundary(
        self, mock_get_entity, mock_get_client
    ):
        """Should stop fetching when hitting min_date boundary (return, not continue)."""
        from tests.conftest import make_mock_message

        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        # Create 5 messages - only 2 should be returned after min_date filter
        msgs = [
            make_mock_message(
                id=5, text="Msg 2025", date=datetime(2025, 1, 1, tzinfo=UTC)
            ),
            make_mock_message(
                id=4,
                text="Msg mid 2024",
                date=datetime(2024, 6, 15, tzinfo=UTC),
            ),
            make_mock_message(
                id=3,
                text="Msg early 2024",
                date=datetime(2024, 1, 15, tzinfo=UTC),
            ),  # min boundary
            make_mock_message(
                id=2,
                text="Msg late 2023",
                date=datetime(2023, 12, 1, tzinfo=UTC),
            ),
            make_mock_message(
                id=1, text="Msg 2022", date=datetime(2022, 1, 1, tzinfo=UTC)
            ),
        ]

        async def mock_iter_messages_gen():
            for msg in msgs:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query="Msg",
            min_date="2024-01-01",
            limit=10,
        )

        assert "messages" in result
        # Should return 3 messages (2025, mid 2024, early 2024)
        # Should STOP at early 2024 (id=3) and NOT process late 2023 (id=2) or 2022 (id=1)
        assert len(result["messages"]) == 3
        msg_ids = {msg["id"] for msg in result["messages"]}
        assert msg_ids == {5, 4, 3}
        assert 2 not in msg_ids  # Should not have processed these
        assert 1 not in msg_ids

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_search_chat_handles_none_date(
        self, mock_get_entity, mock_get_client
    ):
        """Should pass through messages with None date (unknown date = don't filter)."""
        from tests.conftest import make_mock_message

        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        msg_with_date = make_mock_message(
            id=1, text="Dated message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )
        msg_no_date = make_mock_message(id=2, text="Unknown date", date=None)

        async def mock_iter_messages_gen():
            for msg in [msg_with_date, msg_no_date]:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query="message",
            min_date="2024-01-01",
            limit=50,
        )

        assert "messages" in result
        # Both messages should pass - None date is not filtered
        assert len(result["messages"]) == 2

    @pytest.mark.asyncio
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_browse_includes_service_message_in_date_window(
        self, mock_get_entity, mock_get_client
    ):
        """Recent Telegram service messages count as dialog activity but had no exportable text."""
        from tests.conftest import make_mock_message

        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_get_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))

        pin_action = MagicMock()
        pin_action.__class__.__name__ = "MessageActionPinMessage"
        service_msg = make_mock_message(
            id=99,
            text="",
            date=datetime(2024, 6, 20, tzinfo=UTC),
            media=None,
            action=pin_action,
        )
        service_msg.message = ""
        service_msg.caption = None
        service_msg.forward = None

        old_msg = make_mock_message(
            id=1, text="old", date=datetime(2020, 1, 1, tzinfo=UTC)
        )

        async def mock_iter_messages_gen():
            for msg in [service_msg, old_msg]:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter_messages_gen())
        mock_get_client.return_value = mock_client

        result = await search_messages_impl(
            chat_id="me",
            query=None,
            min_date="2024-06-01",
            limit=10,
        )

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0]["id"] == 99
        assert "[Service: PinMessage]" in (result["messages"][0].get("text") or "")


class TestGetMessagesContext:
    """Test context enrichment feature for search results."""

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    async def test_context_disabled_by_default(
        self,
        mock_sm_entity,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_enrich_entity,
        mock_batched,
    ):
        """context=0 should not add context envelope."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_sm_entity.return_value = mock_entity
        mock_gen_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity
        mock_enrich_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        msg = make_mock_message(
            id=500, text="result message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter():
            yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        result = await search_messages_impl(
            chat_id="me",
            query="result",
            limit=10,
            context=0,
        )

        assert "messages" in result
        if result["messages"]:
            assert "context" not in result["messages"][0]

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    async def test_context_adds_before_after(
        self,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_sm_entity,
        mock_batched,
    ):
        """context=2 should add before[] and after[] with neighbor messages."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_gen_entity.return_value = mock_entity
        mock_sm_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        # Search result: message 500
        result_msg = make_mock_message(
            id=500, text="found message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter():
            yield result_msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        # Neighbors for context (498, 499, 501, 502). Distinct dates so the
        # ascending-order policy is observable: ids ascend with time.
        def make_raw_msg(mid, text, minute):
            m = MagicMock()
            m.id = mid
            m.text = text
            m.message = text
            m.caption = None
            m.date = datetime(2024, 6, 15, 10, minute, tzinfo=UTC)
            m.sender_id = 42
            m.media = None
            m.reply_to = None
            m.reply_to_msg_id = None
            return m

        neighbors = [
            make_raw_msg(498, "before 2", 0),
            make_raw_msg(499, "before 1", 1),
            make_raw_msg(500, "found message", 2),
            make_raw_msg(501, "after 1", 3),
            make_raw_msg(502, "after 2", 4),
        ]
        mock_batched.return_value = neighbors

        result = await search_messages_impl(
            chat_id="me",
            query="found",
            limit=10,
            context=2,
        )

        assert "messages" in result
        assert len(result["messages"]) == 1
        ctx = result["messages"][0].get("context")
        assert ctx is not None
        assert "before" in ctx
        assert "after" in ctx
        assert len(ctx["before"]) == 2
        assert len(ctx["after"]) == 2
        # Both lists are ordered oldest-first
        assert ctx["before"][0]["id"] == 498
        assert ctx["before"][1]["id"] == 499
        assert ctx["after"][0]["id"] == 501
        assert ctx["after"][1]["id"] == 502

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    async def test_context_reply_to(
        self,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_sm_entity,
        mock_batched,
    ):
        """context should resolve reply_to_msg_id to lightweight message."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_gen_entity.return_value = mock_entity
        mock_sm_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        # Result message replies to msg 400
        result_msg = make_mock_message(
            id=500,
            text="reply message",
            date=datetime(2024, 6, 15, tzinfo=UTC),
            reply_to_msg_id=400,
        )

        async def mock_iter():
            yield result_msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        def make_raw_msg(mid, text):
            m = MagicMock()
            m.id = mid
            m.text = text
            m.message = text
            m.caption = None
            m.date = datetime(2024, 6, 15, tzinfo=UTC)
            m.sender_id = 42
            m.media = None
            m.reply_to = None
            m.reply_to_msg_id = None
            return m

        fetched = [
            make_raw_msg(400, "original message"),
            make_raw_msg(499, "neighbor before"),
            make_raw_msg(500, "reply message"),
            make_raw_msg(501, "neighbor after"),
        ]
        mock_batched.return_value = fetched

        result = await search_messages_impl(
            chat_id="me",
            query="reply",
            limit=10,
            context=1,
        )

        assert "messages" in result
        ctx = result["messages"][0].get("context")
        assert ctx is not None
        assert ctx["reply_to"] is not None
        assert ctx["reply_to"]["id"] == 400
        assert ctx["reply_to"]["text"] == "original message"

    @pytest.mark.asyncio
    @patch("src.tools.search.context_enrichment._fetch_replies", new_callable=AsyncMock)
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    async def test_context_reply_threads(
        self,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_sm_entity,
        mock_batched,
        mock_fetch_replies,
    ):
        """include_replies=True should fetch replies and attach them."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_gen_entity.return_value = mock_entity
        mock_sm_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        result_msg = make_mock_message(
            id=500, text="popular message", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter():
            yield result_msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        def make_raw_msg(mid, text):
            m = MagicMock()
            m.id = mid
            m.text = text
            m.message = text
            m.caption = None
            m.date = datetime(2024, 6, 15, tzinfo=UTC)
            m.sender_id = 42
            m.media = None
            m.reply_to = None
            m.reply_to_msg_id = None
            return m

        fetched = [
            make_raw_msg(500, "popular message"),
        ]
        mock_batched.return_value = fetched

        # Mock _fetch_replies returns (collected, discussion_metadata) tuple
        mock_fetch_replies.return_value = (
            [
                {
                    "id": 501,
                    "text": "reply 1",
                    "date": "2024-06-15T00:00:00",
                    "sender": {"id": 10},
                },
                {
                    "id": 502,
                    "text": "reply 2",
                    "date": "2024-06-15T00:01:00",
                    "sender": {"id": 11},
                },
            ],
            None,
        )

        result = await search_messages_impl(
            chat_id="me",
            query="popular",
            limit=10,
            context=0,
            include_replies=True,
        )

        assert "messages" in result
        ctx = result["messages"][0].get("context")
        assert ctx is not None
        assert "replies" in ctx
        assert len(ctx["replies"]) == 2
        assert ctx["replies"][0]["id"] == 501
        assert ctx["replies"][1]["id"] == 502

    @pytest.mark.asyncio
    @patch("src.tools.search.context_enrichment._fetch_replies", new_callable=AsyncMock)
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    async def test_context_reply_timeout_isolates_other_results(
        self, mock_batched, mock_fetch_replies
    ):
        """One reply fetch timeout should not block other reply threads."""
        from src.tools.search.context_enrichment import _enrich_with_context

        mock_entity = MagicMock()
        mock_entity.forum = False
        mock_client = MagicMock()

        async def fetch_side_effect(client, entity, mid, *args, **kwargs):
            if mid == 100:
                raise TimeoutError("slow")
            return (
                [{"id": 201, "text": "ok", "date": "2024-01-01", "sender": {"id": 1}}],
                None,
            )

        mock_fetch_replies.side_effect = fetch_side_effect
        mock_batched.return_value = []

        messages = [
            {"id": 100, "reply_to_msg_id": None},
            {"id": 200, "reply_to_msg_id": None},
        ]
        enriched, _warning = await _enrich_with_context(
            mock_client,
            mock_entity,
            messages,
            context=0,
            include_replies=True,
        )

        assert enriched[0]["context"]["replies"] == []
        assert len(enriched[1]["context"]["replies"]) == 1
        assert enriched[1]["context"]["replies"][0]["id"] == 201

    @pytest.mark.asyncio
    @patch("src.tools.search.context_enrichment._fetch_replies", new_callable=AsyncMock)
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.context_enrichment.time.monotonic")
    async def test_context_budget_timeout_skips_reply_fetches(
        self, mock_monotonic, mock_batched, mock_fetch_replies
    ):
        """When enrichment budget is exceeded, reply fetches are skipped."""
        from src.tools.search.context_enrichment import _enrich_with_context

        mock_entity = MagicMock()
        mock_entity.forum = False
        mock_client = MagicMock()
        mock_batched.return_value = []
        times = iter([0.0, 31.0])
        mock_monotonic.side_effect = lambda: next(times, 31.0)

        messages = [{"id": 100, "reply_to_msg_id": None}]
        enriched, warning = await _enrich_with_context(
            mock_client,
            mock_entity,
            messages,
            context=0,
            include_replies=True,
        )

        mock_fetch_replies.assert_not_called()
        assert warning is not None
        replies = enriched[0].get("context", {}).get("replies")
        assert replies is None or replies == []

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    async def test_context_partial_failure_returns_messages(
        self,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_sm_entity,
        mock_batched,
    ):
        """Enrichment failure should return messages without context (not lose results)."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_gen_entity.return_value = mock_entity
        mock_sm_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        result_msg = make_mock_message(
            id=500, text="result", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter():
            yield result_msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        # Make batched fetch fail
        mock_batched.side_effect = RuntimeError("API error")

        result = await search_messages_impl(
            chat_id="me",
            query="result",
            limit=10,
            context=2,
        )

        # Should still return the messages, just without context
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert "context" not in result["messages"][0]

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    async def test_context_flood_wait_returns_messages(
        self,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_sm_entity,
        mock_batched,
    ):
        """FloodWaitError during enrichment should return messages without context."""
        from telethon.errors import FloodWaitError

        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_gen_entity.return_value = mock_entity
        mock_sm_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        result_msg = make_mock_message(
            id=500, text="result", date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter():
            yield result_msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        # Make batched fetch raise FloodWaitError
        flood = FloodWaitError(request=None, capture=30)
        mock_batched.side_effect = flood

        result = await search_messages_impl(
            chat_id="me",
            query="result",
            limit=10,
            context=2,
        )

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert "context" not in result["messages"][0]

    @pytest.mark.asyncio
    @patch(
        "src.tools.search.context_enrichment._get_messages_by_ids_batched",
        new_callable=AsyncMock,
    )
    @patch("src.tools.search.search_mode.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_entity_by_id", new_callable=AsyncMock)
    @patch("src.tools.search.core.get_connected_client", new_callable=AsyncMock)
    @patch("src.tools.search.search_mode.get_connected_client", new_callable=AsyncMock)
    @patch(
        "src.tools.search.search_generators.get_entity_by_id", new_callable=AsyncMock
    )
    async def test_context_id_cap(
        self,
        mock_gen_entity,
        mock_sm_client,
        mock_core_client,
        mock_core_entity,
        mock_sm_entity,
        mock_batched,
    ):
        """Should cap total IDs at 500 when too many results with large context."""
        mock_entity = Mock()
        mock_entity.id = 123
        mock_entity.broadcast = False
        mock_entity.forum = False
        mock_gen_entity.return_value = mock_entity
        mock_sm_entity.return_value = mock_entity
        mock_core_entity.return_value = mock_entity

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=Mock(premium=False))
        mock_sm_client.return_value = mock_client
        mock_core_client.return_value = mock_client

        # Create 50 results to trigger ID cap with context=10
        result_msgs = []
        for i in range(50):
            result_msgs.append(
                make_mock_message(
                    id=100 + i * 100,
                    text=f"result {i}",
                    date=datetime(2024, 6, 15, tzinfo=UTC),
                )
            )

        async def mock_iter():
            for msg in result_msgs:
                yield msg

        mock_client.iter_messages = MagicMock(return_value=mock_iter())

        def make_raw_msg(mid, text):
            m = MagicMock()
            m.id = mid
            m.text = text
            m.message = text
            m.caption = None
            m.date = datetime(2024, 6, 15, tzinfo=UTC)
            m.sender_id = 42
            m.media = None
            m.reply_to = None
            m.reply_to_msg_id = None
            return m

        # Return enough neighbors to fill the cap
        all_neighbors = []
        for i in range(50):
            base = 100 + i * 100
            for offset in range(-10, 11):
                if offset != 0:
                    all_neighbors.append(
                        make_raw_msg(base + offset, f"neighbor {base + offset}")
                    )
            all_neighbors.append(make_raw_msg(base, f"result {i}"))

        mock_batched.return_value = all_neighbors

        result = await search_messages_impl(
            chat_id="me",
            query="result",
            limit=50,
            context=10,
        )

        assert "messages" in result
        # Verify enrichment was attempted (batched was called)
        mock_batched.assert_called_once()
        # The IDs passed should be capped
        called_ids = mock_batched.call_args[0][2]
        assert len(called_ids) <= 500


class TestGetMessagesContextHelpers:
    """Unit tests for context enrichment helper functions."""

    def test_extract_topic_id_from_message_with_reply_to_top_id(self):
        """Should extract topic_id from reply_to.reply_to_top_id."""
        from src.utils.message_format import extract_topic_metadata

        msg = MagicMock()
        msg.reply_to = MagicMock(
            reply_to_top_id=42, forum_topic=True, reply_to_msg_id=10
        )
        msg.reply_to_msg_id = None
        assert extract_topic_metadata(msg).get("topic_id") == 42

    def test_extract_topic_id_from_message_with_forum_topic(self):
        """Should extract topic_id from reply_to_msg_id when forum_topic=True."""
        from src.utils.message_format import extract_topic_metadata

        msg = MagicMock()
        msg.reply_to = MagicMock(
            reply_to_top_id=None, forum_topic=True, reply_to_msg_id=10
        )
        msg.reply_to_msg_id = None
        assert extract_topic_metadata(msg).get("topic_id") == 10

    def test_extract_topic_id_from_message_no_topic(self):
        """Should return None for non-forum messages."""
        from src.utils.message_format import extract_topic_metadata

        msg = MagicMock()
        msg.reply_to = MagicMock(
            reply_to_top_id=None, forum_topic=False, reply_to_msg_id=None
        )
        msg.reply_to_msg_id = None
        assert extract_topic_metadata(msg).get("topic_id") is None

    def test_extract_topic_id_from_message_no_reply_to(self):
        """Should return empty dict when reply_to is None."""
        from src.utils.message_format import extract_topic_metadata

        msg = MagicMock()
        msg.reply_to = None
        msg.reply_to_msg_id = None
        assert extract_topic_metadata(msg) == {}

    def test_is_valid_context_neighbor_filters_service_messages(self):
        """Should reject service messages (no displayable content)."""
        from src.tools.search.context_enrichment import _is_valid_context_neighbor

        msg = MagicMock()
        msg.text = None
        msg.message = None
        msg.caption = None
        msg.media = None
        msg.action = None
        msg.rich_message = None
        assert _is_valid_context_neighbor(msg, False, None) is False

    def test_is_valid_context_neighbor_accepts_text_messages(self):
        """Should accept messages with text content."""
        from src.tools.search.context_enrichment import _is_valid_context_neighbor

        msg = MagicMock()
        msg.text = "hello"
        msg.reply_to = None
        assert _is_valid_context_neighbor(msg, False, None) is True

    def test_is_valid_context_neighbor_forum_topic_mismatch(self):
        """Should reject neighbors from different forum topics."""
        from src.tools.search.context_enrichment import _is_valid_context_neighbor

        msg = MagicMock()
        msg.text = "other topic msg"
        msg.reply_to = MagicMock(
            reply_to_top_id=99, forum_topic=True, reply_to_msg_id=None
        )
        assert _is_valid_context_neighbor(msg, True, 42) is False

    def test_is_valid_context_neighbor_forum_topic_match(self):
        """Should accept neighbors from the same forum topic."""
        from src.tools.search.context_enrichment import _is_valid_context_neighbor

        msg = MagicMock()
        msg.text = "same topic msg"
        msg.reply_to = MagicMock(
            reply_to_top_id=42, forum_topic=True, reply_to_msg_id=None
        )
        assert _is_valid_context_neighbor(msg, True, 42) is True

    def test_lightweight_from_raw(self):
        """Should extract id, date, text, sender_id from raw message."""
        from src.tools.search.context_enrichment import _lightweight_from_raw

        msg = MagicMock()
        msg.id = 100
        msg.text = "hello world"
        msg.message = "hello world"
        msg.caption = None
        msg.date = datetime(2024, 6, 15, tzinfo=UTC)
        msg.sender_id = 42

        result = _lightweight_from_raw(msg)
        assert result == {
            "id": 100,
            "date": "2024-06-15T00:00:00+00:00",
            "text": "hello world",
            "sender_id": 42,
        }

    def test_lightweight_from_result(self):
        """Should extract id, date, text, sender_id from result dict."""
        from src.tools.search.context_enrichment import _lightweight_from_result

        result_dict = {
            "id": 100,
            "date": "2024-06-15T00:00:00",
            "text": "hello world",
            "sender": {"id": 42, "username": "alice"},
        }

        result = _lightweight_from_result(result_dict)
        assert result == {
            "id": 100,
            "date": "2024-06-15T00:00:00",
            "text": "hello world",
            "sender_id": 42,
        }

    def test_lightweight_from_result_no_sender(self):
        """Should handle None sender gracefully."""
        from src.tools.search.context_enrichment import _lightweight_from_result

        result_dict = {
            "id": 100,
            "date": "2024-06-15T00:00:00",
            "text": "hello",
            "sender": None,
        }

        result = _lightweight_from_result(result_dict)
        assert result["sender_id"] is None
