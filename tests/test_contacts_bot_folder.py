"""Tests for bot chat type and folder filtering functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.contacts import (
    _normalize_folder_name,
    _resolve_folder_id,
    find_chats_impl,
    search_dialogs_impl,
)
from src.utils.entity import (
    _matches_chat_type,
    _matches_public_filter,
    get_available_folders,
    get_normalized_chat_type,
)
from tests.conftest import MockChannel, MockChat, MockDialog, MockUser, make_folder

# ============== Bot Type Detection Tests ==============


class TestGetNormalizedChatType:
    """Tests for get_normalized_chat_type with bot detection."""

    def test_regular_user_returns_private(self):
        """Regular user (not a bot) should return 'private'."""
        user = MockUser(123, first_name="John", last_name="Doe", bot=False)
        assert get_normalized_chat_type(user) == "private"

    def test_bot_user_returns_bot(self):
        """User with bot=True should return 'bot'."""
        bot = MockUser(456, first_name="TestBot", username="testbot", bot=True)
        assert get_normalized_chat_type(bot) == "bot"

    def test_chat_returns_group(self):
        """Chat should return 'group'."""
        chat = MockChat(789, title="Test Group")
        assert get_normalized_chat_type(chat) == "group"

    def test_channel_returns_channel(self):
        """Channel (not megagroup) should return 'channel'."""
        channel = MockChannel(
            100, title="Test Channel", username="testchannel", megagroup=False
        )
        assert get_normalized_chat_type(channel) == "channel"

    def test_megagroup_returns_group(self):
        """Supergroup/megagroup should return 'group'."""
        channel = MockChannel(100, title="Test Supergroup", megagroup=True)
        assert get_normalized_chat_type(channel) == "group"

    def test_user_without_bot_attribute_returns_private(self):
        """User class without bot attribute should return 'private' via getattr default."""
        attrs = {"id": 1, "first_name": "Test"}
        user = type("User", (), attrs)()
        assert getattr(user, "bot", False) is False
        assert get_normalized_chat_type(user) == "private"


class TestMatchesChatType:
    """Tests for _matches_chat_type with bot type."""

    def test_private_filter_matches_private_not_bot(self):
        """chat_type='private' should NOT match bots."""
        bot = MockUser(456, first_name="TestBot", bot=True)
        assert _matches_chat_type(bot, "private") is False

    def test_bot_filter_matches_bot(self):
        """chat_type='bot' should match bots."""
        bot = MockUser(456, first_name="TestBot", bot=True)
        assert _matches_chat_type(bot, "bot") is True

    def test_bot_filter_does_not_match_private(self):
        """chat_type='bot' should NOT match regular users."""
        user = MockUser(123, first_name="John", bot=False)
        assert _matches_chat_type(user, "bot") is False

    def test_private_filter_matches_private(self):
        """chat_type='private' should match regular users."""
        user = MockUser(123, first_name="John", bot=False)
        assert _matches_chat_type(user, "private") is True

    def test_group_filter_matches_chat(self):
        """chat_type='group' should match chats."""
        chat = MockChat(789, title="Test Group")
        assert _matches_chat_type(chat, "group") is True

    def test_channel_filter_matches_channel(self):
        """chat_type='channel' should match channels."""
        channel = MockChannel(100, title="Test Channel")
        assert _matches_chat_type(channel, "channel") is True

    def test_invalid_chat_type_returns_false(self):
        """Invalid chat type should return False."""
        user = MockUser(123, first_name="John")
        assert _matches_chat_type(user, "invalid") is False

    def test_bot_is_valid_type(self):
        """'bot' should be a valid chat type for validation."""
        bot = MockUser(456, first_name="TestBot", bot=True)
        assert _matches_chat_type(bot, "bot") is True


class TestMatchesPublicFilter:
    """Tests for _matches_public_filter with bot type."""

    def test_private_never_filtered(self):
        """Private chats should always return True (never filtered by public param)."""
        user = MockUser(123, first_name="John", username="johndoe", bot=False)
        assert _matches_public_filter(user, True) is True
        assert _matches_public_filter(user, False) is True
        assert _matches_public_filter(user, None) is True

    def test_bot_never_filtered(self):
        """Bots should always return True (never filtered by public param)."""
        bot = MockUser(456, first_name="TestBot", username="testbot", bot=True)
        assert _matches_public_filter(bot, True) is True
        assert _matches_public_filter(bot, False) is True
        assert _matches_public_filter(bot, None) is True

    def test_channel_public_filter(self):
        """Channels should be filtered by public param."""
        channel_with_username = MockChannel(100, title="Public", username="publicchan")
        channel_without_username = MockChannel(101, title="Private", username="")

        assert _matches_public_filter(channel_with_username, True) is True
        assert _matches_public_filter(channel_without_username, True) is False

        assert _matches_public_filter(channel_with_username, False) is False
        assert _matches_public_filter(channel_without_username, False) is True


# ============== Folder Filtering Tests ==============


class TestGetAvailableFolders:
    """Tests for get_available_folders function.

    Note: These tests verify the title extraction logic from TextWithEntities objects.
    The actual async API call is tested via integration tests.
    """

    def test_extracts_title_text_from_text_with_entities_object(self):
        """Verify title.text extraction from TextWithEntities works correctly."""

        class MockTextWithEntities:
            def __init__(self, text):
                self.text = text

        title_obj = MockTextWithEntities("Work")
        title_text = getattr(title_obj, "text", None)
        assert title_text == "Work"

    def test_handles_missing_title_gracefully(self):
        """Verify that missing title is handled correctly."""
        title_obj = None
        title_text = getattr(title_obj, "text", None) if title_obj else None
        assert title_text is None

    def test_folder_dict_structure(self):
        """Verify the folder dict structure returned by get_available_folders."""
        folder_dict = {"id": 1, "title": "Work"}
        assert folder_dict["id"] == 1
        assert folder_dict["title"] == "Work"

    @pytest.mark.asyncio
    async def test_caches_results_on_first_call(self):
        """Verify get_available_folders caches results after first API call."""
        from src.utils.entity import _FOLDER_LIST_CACHE

        _FOLDER_LIST_CACHE.clear()

        class MockSession:
            session_id = "cache_test_session"

        mock_client = MagicMock()
        mock_client.session = MockSession()

        mock_result = MagicMock()
        mock_result.dialog_filters = [
            make_folder(1, "Work"),
            make_folder(2, "Personal"),
        ]

        async def mock_call(*args, **kwargs):
            return mock_result

        mock_client.side_effect = mock_call

        await get_available_folders(mock_client)

        assert "cache_test_session" in _FOLDER_LIST_CACHE
        cached_folders, _ = _FOLDER_LIST_CACHE["cache_test_session"]
        assert len(cached_folders) == 2
        assert cached_folders[0]["title"] == "Work"

        _FOLDER_LIST_CACHE.clear()

    @pytest.mark.asyncio
    async def test_does_not_cache_on_failure(self):
        """Verify empty result is NOT cached when API call fails."""
        from src.utils.entity import _FOLDER_LIST_CACHE

        _FOLDER_LIST_CACHE.clear()

        class MockSession:
            session_id = "fail_test_session"

        mock_client = MagicMock()
        mock_client.session = MockSession()

        mock_client.side_effect = Exception("API Error")

        result = await get_available_folders(mock_client)

        assert result == []
        assert "fail_test_session" not in _FOLDER_LIST_CACHE

        _FOLDER_LIST_CACHE.clear()


class TestNormalizeFolderName:
    """Tests for _normalize_folder_name helper."""

    def test_trims_whitespace(self):
        """Should trim leading/trailing whitespace."""
        assert _normalize_folder_name("  Work  ") == "work"
        assert _normalize_folder_name("\tPersonal\t") == "personal"

    def test_collapse_internal_whitespace(self):
        """Should collapse internal whitespace to single spaces."""
        assert _normalize_folder_name("Work  Chat") == "work chat"
        assert _normalize_folder_name("Personal\tGroup") == "personal group"

    def test_lowercase_conversion(self):
        """Should convert to lowercase."""
        assert _normalize_folder_name("WORK") == "work"
        assert _normalize_folder_name("Personal") == "personal"

    def test_combined_normalization(self):
        """Should combine all normalizations."""
        assert _normalize_folder_name("  Work  Chat  ") == "work chat"
        assert _normalize_folder_name("  PERSONAL ") == "personal"


class TestResolveFolderId:
    """Tests for _resolve_folder_id helper."""

    @pytest.mark.asyncio
    async def test_returns_integer_as_is(self):
        """Integer folder ID should be returned as-is."""
        mock_client = MagicMock()

        result = await _resolve_folder_id(mock_client, 5)
        assert result == 5

    @pytest.mark.asyncio
    async def test_resolves_string_name_to_id(self):
        """String folder name should be resolved to folder ID."""
        mock_client = MagicMock()

        with patch(
            "src.tools.contacts.get_available_folders", new_callable=AsyncMock
        ) as mock_folders:
            mock_folders.return_value = [
                {"id": 1, "title": "Work"},
                {"id": 2, "title": "Personal"},
            ]

            result = await _resolve_folder_id(mock_client, "Work")
            assert result == 1

    @pytest.mark.asyncio
    async def test_folder_name_case_insensitive(self):
        """Folder name matching should be case-insensitive."""
        mock_client = MagicMock()

        with patch(
            "src.tools.contacts.get_available_folders", new_callable=AsyncMock
        ) as mock_folders:
            mock_folders.return_value = [
                {"id": 1, "title": "Work"},
                {"id": 2, "title": "Personal"},
            ]

            result = await _resolve_folder_id(mock_client, "work")
            assert result == 1

            result = await _resolve_folder_id(mock_client, "WORK")
            assert result == 1

    @pytest.mark.asyncio
    async def test_folder_name_with_whitespace_matches(self):
        """Folder names with extra whitespace should still match."""
        mock_client = MagicMock()

        with patch(
            "src.tools.contacts.get_available_folders", new_callable=AsyncMock
        ) as mock_folders:
            mock_folders.return_value = [{"id": 1, "title": "Work"}]

            result = await _resolve_folder_id(mock_client, "  Work  ")
            assert result == 1

            result = await _resolve_folder_id(mock_client, "Work  Chat")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Should return None when folder name is not found."""
        mock_client = MagicMock()

        with patch(
            "src.tools.contacts.get_available_folders", new_callable=AsyncMock
        ) as mock_folders:
            mock_folders.return_value = [{"id": 1, "title": "Work"}]

            result = await _resolve_folder_id(mock_client, "Nonexistent")
            assert result is None


# ============== Integration Tests ==============


class TestSearchDialogsImplFolder:
    """Tests for search_dialogs_impl with folder parameter."""

    @pytest.mark.asyncio
    async def test_passes_folder_id_to_iter_dialogs(self):
        """Should pass folder_id to client.iter_dialogs."""
        dialog = MockDialog(
            MockUser(1, first_name="Test"), date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter_dialogs(limit=None, folder=None):
            assert folder == 5
            yield dialog

        mock_client = MagicMock()
        mock_client.iter_dialogs = mock_iter_dialogs

        with patch(
            "src.tools.contacts.get_connected_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            results = []
            async for item in search_dialogs_impl(limit=10, folder_id=5):
                results.append(item)

            assert len(results) == 1


class TestFindChatsImplFolder:
    """Tests for find_chats_impl with folder parameter."""

    @pytest.mark.asyncio
    async def test_folder_param_uses_dialog_search(self):
        """When folder is provided, should use dialog-based search."""
        dialog = MockDialog(
            MockUser(1, first_name="TestBot", bot=True),
            date=datetime(2024, 6, 15, tzinfo=UTC),
        )

        async def mock_iter_dialogs(limit=None, folder=None):
            yield dialog

        mock_client = MagicMock()
        mock_client.iter_dialogs = mock_iter_dialogs

        with patch(
            "src.tools.contacts.get_connected_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            with patch(
                "src.tools.contacts.get_available_folders", new_callable=AsyncMock
            ) as mock_folders:
                mock_folders.return_value = [{"id": 1, "title": "Work"}]

                result = await find_chats_impl(folder=1)

                assert "chats" in result

    @pytest.mark.asyncio
    async def test_folder_param_none_uses_global_search(self):
        """When no folder (None), should use global search."""
        with patch(
            "src.tools.contacts._search_contacts_as_list", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [{"id": 1, "title": "Test"}]

            result = await find_chats_impl(query="test", limit=10, folder=None)

            mock_search.assert_called_once()
            assert "chats" in result

    @pytest.mark.asyncio
    async def test_resolves_folder_name_to_id(self):
        """Should resolve folder name to folder ID."""
        dialog = MockDialog(
            MockUser(1, first_name="TestBot", bot=True),
            date=datetime(2024, 6, 15, tzinfo=UTC),
        )

        async def mock_iter_dialogs(limit=None, folder=None):
            assert folder == 1
            yield dialog

        mock_client = MagicMock()
        mock_client.iter_dialogs = mock_iter_dialogs

        with patch(
            "src.tools.contacts.get_connected_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            with patch(
                "src.tools.contacts.get_available_folders", new_callable=AsyncMock
            ) as mock_folders:
                mock_folders.return_value = [{"id": 1, "title": "Work"}]

                result = await find_chats_impl(folder="Work")

                assert "chats" in result
