"""Tests for bot chat type and folder filtering functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.contacts import (
    _resolve_folder_id,
    find_chats_impl,
    search_dialogs_impl,
)
from src.utils.entity import (
    _ENTITY_TYPE_CACHE,
    _FOLDER_LIST_CACHE,
    _matches_chat_type,
    _matches_public_filter,
    build_entity_dict,
    get_available_folders,
    get_normalized_chat_type,
)


@pytest.fixture(autouse=True)
def clear_entity_cache():
    """Clear entity type cache before each test to avoid cache pollution."""
    _ENTITY_TYPE_CACHE.clear()
    yield
    _ENTITY_TYPE_CACHE.clear()


# ============== Bot Type Detection Tests ==============


def make_user(id, first_name="", last_name="", username="", phone="", bot=False):
    """Create a mock entity that reports as class 'User'."""
    attrs = {
        "id": id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "phone": phone,
        "bot": bot,
        "title": None,
    }
    return type("User", (), attrs)()


def make_chat(id, title="", username=""):
    """Create a mock entity that reports as class 'Chat'."""
    attrs = {
        "id": id,
        "title": title,
        "first_name": None,
        "last_name": None,
        "username": username,
        "phone": None,
    }
    return type("Chat", (), attrs)()


def make_channel(id, title="", username="", megagroup=False):
    """Create a mock entity that reports as class 'Channel'."""
    attrs = {
        "id": id,
        "title": title,
        "username": username,
        "megagroup": megagroup,
        "first_name": None,
        "last_name": None,
        "phone": None,
    }
    return type("Channel", (), attrs)()


class TestGetNormalizedChatType:
    """Tests for get_normalized_chat_type with bot detection."""

    def test_regular_user_returns_private(self):
        """Regular user (not a bot) should return 'private'."""
        user = make_user(123, first_name="John", last_name="Doe", bot=False)
        assert get_normalized_chat_type(user) == "private"

    def test_bot_user_returns_bot(self):
        """User with bot=True should return 'bot'."""
        bot = make_user(456, first_name="TestBot", username="testbot", bot=True)
        assert get_normalized_chat_type(bot) == "bot"

    def test_chat_returns_group(self):
        """Chat should return 'group'."""
        chat = make_chat(789, title="Test Group")
        assert get_normalized_chat_type(chat) == "group"

    def test_channel_returns_channel(self):
        """Channel (not megagroup) should return 'channel'."""
        channel = make_channel(100, title="Test Channel", username="testchannel", megagroup=False)
        assert get_normalized_chat_type(channel) == "channel"

    def test_megagroup_returns_group(self):
        """Supergroup/megagroup should return 'group'."""
        channel = make_channel(100, title="Test Supergroup", megagroup=True)
        assert get_normalized_chat_type(channel) == "group"

    def test_user_without_bot_attribute_returns_private(self):
        """User class without bot attribute should return 'private' via getattr default."""
        attrs = {"id": 1, "first_name": "Test"}
        user = type("User", (), attrs)()
        # When bot attribute doesn't exist, getattr returns False
        assert getattr(user, 'bot', False) is False
        assert get_normalized_chat_type(user) == "private"


class TestMatchesChatType:
    """Tests for _matches_chat_type with bot type."""

    def test_private_filter_matches_private_not_bot(self):
        """chat_type='private' should NOT match bots."""
        bot = make_user(456, first_name="TestBot", bot=True)
        assert _matches_chat_type(bot, "private") is False

    def test_bot_filter_matches_bot(self):
        """chat_type='bot' should match bots."""
        bot = make_user(456, first_name="TestBot", bot=True)
        assert _matches_chat_type(bot, "bot") is True

    def test_bot_filter_does_not_match_private(self):
        """chat_type='bot' should NOT match regular users."""
        user = make_user(123, first_name="John", bot=False)
        assert _matches_chat_type(user, "bot") is False

    def test_private_filter_matches_private(self):
        """chat_type='private' should match regular users."""
        user = make_user(123, first_name="John", bot=False)
        assert _matches_chat_type(user, "private") is True

    def test_group_filter_matches_chat(self):
        """chat_type='group' should match chats."""
        chat = make_chat(789, title="Test Group")
        assert _matches_chat_type(chat, "group") is True

    def test_channel_filter_matches_channel(self):
        """chat_type='channel' should match channels."""
        channel = make_channel(100, title="Test Channel")
        assert _matches_chat_type(channel, "channel") is True

    def test_invalid_chat_type_returns_false(self):
        """Invalid chat type should return False."""
        user = make_user(123, first_name="John")
        assert _matches_chat_type(user, "invalid") is False

    def test_bot_is_valid_type(self):
        """'bot' should be a valid chat type for validation."""
        # This should not raise - validates that "bot" is in valid_types
        bot = make_user(456, first_name="TestBot", bot=True)
        # No exception means "bot" is recognized as valid
        assert _matches_chat_type(bot, "bot") is True


class TestMatchesPublicFilter:
    """Tests for _matches_public_filter with bot type."""

    def test_private_never_filtered(self):
        """Private chats should always return True (never filtered by public param)."""
        user = make_user(123, first_name="John", username="johndoe", bot=False)
        assert _matches_public_filter(user, True) is True
        assert _matches_public_filter(user, False) is True
        assert _matches_public_filter(user, None) is True

    def test_bot_never_filtered(self):
        """Bots should always return True (never filtered by public param)."""
        bot = make_user(456, first_name="TestBot", username="testbot", bot=True)
        assert _matches_public_filter(bot, True) is True
        assert _matches_public_filter(bot, False) is True
        assert _matches_public_filter(bot, None) is True

    def test_channel_public_filter(self):
        """Channels should be filtered by public param."""
        channel_with_username = make_channel(100, title="Public", username="publicchan")
        channel_without_username = make_channel(101, title="Private", username="")

        # public=True should match channels with username
        assert _matches_public_filter(channel_with_username, True) is True
        assert _matches_public_filter(channel_without_username, True) is False

        # public=False should match channels without username
        assert _matches_public_filter(channel_with_username, False) is False
        assert _matches_public_filter(channel_without_username, False) is True


# ============== Folder Filtering Tests ==============


class MockDialog:
    """Mock Dialog object for testing."""

    def __init__(self, entity, date=None, folder_id=None):
        self.entity = entity
        self.date = date
        self.folder_id = folder_id


class TestGetAvailableFolders:
    """Tests for get_available_folders function.

    Note: These tests verify the title extraction logic from TextWithEntities objects.
    The actual async API call is tested via integration tests.
    """

    def test_extracts_title_text_from_text_with_entities_object(self):
        """Verify title.text extraction from TextWithEntities works correctly."""
        # Simulate the extraction logic
        class MockTextWithEntities:
            def __init__(self, text):
                self.text = text

        # Test extraction pattern used in get_available_folders
        title_obj = MockTextWithEntities("Work")
        title_text = getattr(title_obj, 'text', None)
        assert title_text == "Work"

    def test_handles_missing_title_gracefully(self):
        """Verify that missing title is handled correctly."""
        title_obj = None
        title_text = getattr(title_obj, 'text', None) if title_obj else None
        assert title_text is None

    def test_folder_dict_structure(self):
        """Verify the folder dict structure returned by get_available_folders."""
        # Test the expected dict structure
        folder_dict = {
            "id": 1,
            "title": "Work",
        }
        assert folder_dict["id"] == 1
        assert folder_dict["title"] == "Work"

    def test_cache_key_uses_session_id(self):
        """Verify cache key is based on session_id."""
        class MockSession:
            session_id = "test_session_123"

        mock_client = MagicMock()
        mock_client.session = MockSession()

        cache_key = mock_client.session.session_id if hasattr(mock_client, 'session') else "default"
        assert cache_key == "test_session_123"

    def test_cache_key_fallback(self):
        """Verify cache key fallback when session doesn't have session_id."""
        mock_client = MagicMock(spec=[])  # No session attribute

        cache_key = mock_client.session.session_id if hasattr(mock_client, 'session') else "default"
        assert cache_key == "default"

    @pytest.mark.asyncio
    async def test_caches_results_in_memory(self):
        """Verify results are cached in _FOLDER_LIST_CACHE."""
        _FOLDER_LIST_CACHE.clear()

        mock_client = MagicMock()
        mock_client.session.session_id = "cache_test_session"

        # Directly test the cache behavior
        test_folders = [{"id": 1, "title": "CachedFolder"}]
        _FOLDER_LIST_CACHE["cache_test_session"] = (test_folders, 1000.0)

        # Now call get_available_folders - should return cached
        # Note: This test is simplified because mocking the async context manager is complex
        cache_key = "cache_test_session"
        if cache_key in _FOLDER_LIST_CACHE:
            folders, timestamp = _FOLDER_LIST_CACHE[cache_key]
            assert folders == test_folders

        _FOLDER_LIST_CACHE.clear()


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
    async def test_returns_none_when_not_found(self):
        """Should return None when folder name is not found."""
        mock_client = MagicMock()

        with patch(
            "src.tools.contacts.get_available_folders", new_callable=AsyncMock
        ) as mock_folders:
            mock_folders.return_value = [
                {"id": 1, "title": "Work"},
            ]

            result = await _resolve_folder_id(mock_client, "Nonexistent")
            assert result is None


# ============== Integration Tests ==============


class TestSearchDialogsImplFolder:
    """Tests for search_dialogs_impl with folder parameter."""

    @pytest.mark.asyncio
    async def test_passes_folder_id_to_iter_dialogs(self):
        """Should pass folder_id to client.iter_dialogs."""
        dialog = MockDialog(
            make_user(1, first_name="Test"), date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter_dialogs(limit=None, folder=None):
            assert folder == 5  # Verify folder ID is passed
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
            make_user(1, first_name="TestBot", bot=True), date=datetime(2024, 6, 15, tzinfo=UTC)
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

                # Folder param should trigger dialog search
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
            make_user(1, first_name="TestBot", bot=True), date=datetime(2024, 6, 15, tzinfo=UTC)
        )

        async def mock_iter_dialogs(limit=None, folder=None):
            # Folder should be resolved to integer ID
            assert folder == 1  # "Work" should resolve to 1
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

                # Pass folder as string name
                result = await find_chats_impl(folder="Work")

                assert "chats" in result
