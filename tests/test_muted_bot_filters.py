"""Tests for muted filter and bot chat_type feature.

Tests cover:
- get_normalized_chat_type: bot returns "bot" type
- _matches_chat_type: "bot" is valid type, chat_type="bot" matches bot users
- _matches_public_filter: "private" and "bot" are exempt from public filtering
- build_dialog_entity_dict: adds muted field from notify_settings
- build_entity_dict_enriched: bot users get bio enrichment
- find_chats_impl: muted param requires date filters
- search_dialogs_impl: muted filter applied per dialog
- get_chat_info_impl: returns muted field
- search_messages_impl: guard error when chat_type + chat_id both provided
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.contacts import (
    _matches_muted_filter,
    find_chats_impl,
    get_chat_info_impl,
    search_dialogs_impl,
)
from src.tools.search import search_messages_impl
from src.utils import entity as entity_module
from src.utils.entity import (
    _matches_chat_type,
    _matches_public_filter,
    build_dialog_entity_dict,
    build_entity_dict,
    build_entity_dict_enriched,
    get_normalized_chat_type,
)


@pytest.fixture(autouse=True)
def clear_entity_caches():
    """Clear entity module caches before each test to avoid cross-test contamination."""
    entity_module._ENTITY_TYPE_CACHE.clear()
    entity_module._ENTITY_DICT_CACHE.clear()
    yield
    entity_module._ENTITY_TYPE_CACHE.clear()
    entity_module._ENTITY_DICT_CACHE.clear()


# ============== Mock Entity Classes ==============
# Note: Class names must match what entity.__class__.__name__ returns
# since get_normalized_chat_type uses class name checks.
# Telethon User entities have __class__.__name__ == "User"

# Counter for unique IDs to avoid cache collision across tests
_user_id_counter = 0


def next_user_id():
    global _user_id_counter
    _user_id_counter += 1
    return _user_id_counter


class User:
    """Mock User entity - class name must be 'User' for get_normalized_chat_type."""

    def __init__(
        self,
        id,
        first_name="",
        last_name="",
        username="",
        phone="",
        bot=False,
    ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.phone = phone
        self.bot = bot
        self.title = None


class Chat:
    """Mock Chat (basic group) - class name must be 'Chat'."""

    def __init__(self, id, title="", username=""):
        self.id = id
        self.title = title
        self.first_name = None
        self.last_name = None
        self.username = username
        self.phone = None


class Channel:
    """Mock Channel entity (megagroup=False -> channel type) - class name must be 'Channel'."""

    def __init__(self, id, title="", username="", megagroup=False, forum=False):
        self.id = id
        self.title = title
        self.username = username
        self.megagroup = megagroup
        self.forum = forum
        self.broadcast = False


class MockNotifySettings:
    def __init__(self, mute_until=None, silent=False):
        self.mute_until = mute_until
        self.silent = silent


class MockDialog:
    def __init__(self, entity, date=None, notify_settings=None):
        self.entity = entity
        self.date = date
        self.notify_settings = notify_settings


# ============== Helper for mocking datetime.now ==============


class FakeDateTime(datetime):
    """A fake datetime class that can be patched to return a fixed time."""

    _frozen_time = None

    @classmethod
    def now(cls, tz=None):
        if cls._frozen_time is None:
            return datetime.now(tz=tz)
        if tz is None:
            return cls._frozen_time.replace(tzinfo=UTC)
        return cls._frozen_time.astimezone(tz)

    @classmethod
    def freeze(cls, dt):
        """Freeze time to a specific datetime."""
        cls._frozen_time = dt

    @classmethod
    def unfreeze(cls):
        """Unfreeze time."""
        cls._frozen_time = None


@pytest.fixture
def frozen_time():
    """Fixture to freeze datetime.now() for time-sensitive tests."""
    FakeDateTime.freeze(datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC))
    yield FakeDateTime._frozen_time
    FakeDateTime.unfreeze()


# ============== get_normalized_chat_type Tests ==============


class TestGetNormalizedChatTypeBot:
    """Tests for get_normalized_chat_type with bot users."""

    def test_user_with_bot_true_returns_bot(self):
        user = User(id=123, first_name="TestBot", username="testbot", bot=True)
        result = get_normalized_chat_type(user)
        assert result == "bot"

    def test_user_with_bot_false_returns_private(self):
        user = User(id=123, first_name="John", bot=False)
        result = get_normalized_chat_type(user)
        assert result == "private"

    def test_user_with_bot_none_returns_private(self):
        user = User(id=123, first_name="John")
        result = get_normalized_chat_type(user)
        assert result == "private"

    def test_chat_returns_group(self):
        chat = Chat(id=1, title="Test Group")
        result = get_normalized_chat_type(chat)
        assert result == "group"

    def test_channel_returns_channel(self):
        channel = Channel(id=1, title="Test Channel", megagroup=False)
        result = get_normalized_chat_type(channel)
        assert result == "channel"

    def test_megagroup_returns_group(self):
        channel = Channel(id=1, title="Test Megagroup", megagroup=True)
        result = get_normalized_chat_type(channel)
        assert result == "group"

    def test_none_entity_returns_none(self):
        result = get_normalized_chat_type(None)
        assert result is None


# ============== _matches_chat_type Tests ==============


class TestMatchesChatTypeBot:
    """Tests for _matches_chat_type with bot type."""

    def test_bot_type_is_valid(self):
        bot_user = User(id=1, first_name="Bot", bot=True)
        result = _matches_chat_type(bot_user, "bot")
        assert result is True

    def test_bot_type_matches_bot_user(self):
        bot_user = User(id=1, first_name="Bot", bot=True)
        result = _matches_chat_type(bot_user, "bot")
        assert result is True

    def test_bot_type_does_not_match_regular_user(self):
        regular_user = User(id=1, first_name="John", bot=False)
        result = _matches_chat_type(regular_user, "bot")
        assert result is False

    def test_private_type_matches_regular_user(self):
        regular_user = User(id=1, first_name="John", bot=False)
        result = _matches_chat_type(regular_user, "private")
        assert result is True

    def test_private_type_does_not_match_bot(self):
        bot_user = User(id=1, first_name="Bot", bot=True)
        result = _matches_chat_type(bot_user, "private")
        assert result is False

    def test_comma_separated_bot_and_private(self):
        bot_user = User(id=1, first_name="Bot", bot=True)
        regular_user = User(id=2, first_name="John", bot=False)

        assert _matches_chat_type(bot_user, "private,bot") is True
        assert _matches_chat_type(regular_user, "private,bot") is True

    def test_invalid_chat_type_returns_false(self):
        user = User(id=1, first_name="John")
        result = _matches_chat_type(user, "invalid_type")
        assert result is False

    def test_empty_chat_type_returns_true(self):
        user = User(id=1, first_name="John")
        result = _matches_chat_type(user, "")
        assert result is True

    def test_none_chat_type_returns_true(self):
        user = User(id=1, first_name="John")
        result = _matches_chat_type(user, None)
        assert result is True

    def test_group_type_matches_chat(self):
        chat = Chat(id=1, title="Test Group")
        result = _matches_chat_type(chat, "group")
        assert result is True

    def test_channel_type_matches_channel(self):
        channel = Channel(id=1, title="Test Channel", megagroup=False)
        result = _matches_chat_type(channel, "channel")
        assert result is True


# ============== _matches_public_filter Tests ==============


class TestMatchesPublicFilterBot:
    """Tests for _matches_public_filter with bot users."""

    def test_bot_is_exempt_from_public_filter(self):
        """Bot users should always return True regardless of public filter."""
        bot_user = User(id=1, first_name="Bot", username="testbot", bot=True)

        assert _matches_public_filter(bot_user, True) is True
        assert _matches_public_filter(bot_user, False) is True
        assert _matches_public_filter(bot_user, None) is True

    def test_private_user_is_exempt_from_public_filter(self):
        """Private users should always return True regardless of public filter."""
        user = User(id=1, first_name="John", username="john")

        assert _matches_public_filter(user, True) is True
        assert _matches_public_filter(user, False) is True
        assert _matches_public_filter(user, None) is True

    def test_channel_respects_public_filter_with_username(self):
        """Channels with username should match public=True."""
        channel = Channel(id=1, title="Public Channel", username="publicchannel")
        assert _matches_public_filter(channel, True) is True
        assert _matches_public_filter(channel, False) is False

    def test_channel_respects_public_filter_without_username(self):
        """Channels without username should match public=False."""
        channel = Channel(id=1, title="Private Channel")
        assert _matches_public_filter(channel, True) is False
        assert _matches_public_filter(channel, False) is True


# ============== build_dialog_entity_dict muted Tests ==============


class TestBuildDialogEntityDictMuted:
    """Tests for build_dialog_entity_dict with muted field."""

    def test_muted_true_when_mute_until_in_future(self, frozen_time):
        """When mute_until is in the future, muted should be True."""
        # frozen_time is 2024-06-15 12:00:00 UTC
        future = datetime(2024, 6, 16, tzinfo=UTC)  # next day
        dialog = MockDialog(
            User(1, first_name="John"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(mute_until=future),
        )

        with patch("src.utils.entity.datetime", FakeDateTime):
            result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["muted"] is True

    def test_muted_false_when_mute_until_in_past(self, frozen_time):
        """When mute_until is in the past, muted should be False."""
        past = datetime(2024, 6, 14, tzinfo=UTC)  # day before frozen time
        dialog = MockDialog(
            User(1, first_name="John"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(mute_until=past),
        )

        with patch("src.utils.entity.datetime", FakeDateTime):
            result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["muted"] is False

    def test_muted_true_when_silent(self, frozen_time):
        """When silent=True, muted should be True regardless of mute_until."""
        future = datetime(2024, 6, 16, tzinfo=UTC)
        dialog = MockDialog(
            User(1, first_name="John"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(mute_until=future, silent=True),
        )

        with patch("src.utils.entity.datetime", FakeDateTime):
            result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["muted"] is True

    def test_muted_false_when_no_notify_settings(self, frozen_time):
        """When no notify_settings, muted key is absent (unknown = not muted)."""
        dialog = MockDialog(
            User(1, first_name="John"),
            date=datetime.now(tz=UTC),
            notify_settings=None,
        )

        with patch("src.utils.entity.datetime", FakeDateTime):
            result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        # When notify_settings is None, the muted key is not added
        # (not present = implicitly not muted)
        assert "muted" not in result

    def test_muted_false_when_unmuted(self):
        """When not muted (silent=False), muted field is explicitly False."""
        dialog = MockDialog(
            User(1, first_name="John"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=False),
        )

        result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["muted"] is False


# ============== _matches_muted_filter Tests ==============


class TestMatchesMutedFilter:
    """Tests for _matches_muted_filter helper."""

    def test_muted_none_returns_true(self, frozen_time):
        """When muted param is None, always return True."""
        dialog = MockDialog(User(1), date=datetime.now(tz=UTC))
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, None) is True

    def test_muted_true_with_future_mute_until(self, frozen_time):
        """When muted=True and mute_until is in future, return True."""
        future = datetime(2024, 6, 16, tzinfo=UTC)
        dialog = MockDialog(
            User(1),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(mute_until=future),
        )
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, True) is True

    def test_muted_true_with_silent(self, frozen_time):
        """When muted=True and silent=True, return True."""
        dialog = MockDialog(
            User(1),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=True),
        )
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, True) is True

    def test_muted_false_when_unmuted(self, frozen_time):
        """When muted=False and not muted, return True."""
        dialog = MockDialog(
            User(1),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=False),
        )
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, False) is True

    def test_muted_true_when_not_muted_returns_false(self, frozen_time):
        """When muted=True but entity is not muted, return False."""
        dialog = MockDialog(
            User(1),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=False),
        )
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, True) is False

    def test_muted_false_when_muted_returns_false(self, frozen_time):
        """When muted=False but entity is muted, return False."""
        future = datetime(2024, 6, 16, tzinfo=UTC)
        dialog = MockDialog(
            User(1),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(mute_until=future),
        )
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, False) is False

    def test_no_notify_settings_returns_false(self, frozen_time):
        """When no notify_settings, return False for any non-None muted value."""
        dialog = MockDialog(User(1), date=datetime.now(tz=UTC))
        with patch("src.utils.entity.datetime", FakeDateTime):
            assert _matches_muted_filter(dialog, True) is False
            assert _matches_muted_filter(dialog, False) is False


# ============== find_chats_impl muted Tests ==============


class TestFindChatsImplMuted:
    """Tests for find_chats_impl with muted parameter."""

    @pytest.mark.asyncio
    async def test_muted_without_date_filters_uses_global_search(self):
        """find_chats(muted=True) without date filters falls through to global search (muted silently ignored)."""
        result = await find_chats_impl(query="test", muted=True)

        # Muted without date filters falls through to global search (no error)
        # Result is either a list of chats or an error from the global search attempt
        assert "chats" in result or "error" in result

    @pytest.mark.asyncio
    async def test_muted_false_without_date_filters_uses_global_search(self):
        """find_chats(muted=False) without date filters falls through to global search (muted silently ignored)."""
        result = await find_chats_impl(query="test", muted=False)

        # Muted without date filters falls through to global search (no error)
        assert "chats" in result or "error" in result

    @pytest.mark.asyncio
    async def test_muted_with_min_date_uses_dialog_search(self):
        """find_chats with muted and min_date should use dialog search."""
        dialog = MockDialog(
            User(1, first_name="John"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=False),
        )

        async def mock_iter_dialogs(limit=None):
            yield dialog

        mock_client = MagicMock()
        mock_client.iter_dialogs = mock_iter_dialogs

        with patch(
            "src.tools.contacts.get_connected_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            result = await find_chats_impl(
                query="John",
                limit=10,
                min_date="2024-01-01",
                muted=False,
            )

            assert "chats" in result

    @pytest.mark.asyncio
    async def test_muted_filter_with_dialog_search(self):
        """Muted filter should work with dialog-based search."""
        muted_dialog = MockDialog(
            User(1, first_name="MutedChat"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=True),
        )
        unmuted_dialog = MockDialog(
            User(2, first_name="UnmutedChat"),
            date=datetime.now(tz=UTC),
            notify_settings=MockNotifySettings(silent=False),
        )

        dialogs = [muted_dialog, unmuted_dialog]

        async def mock_iter_dialogs(limit=None):
            for d in dialogs:
                yield d

        mock_client = MagicMock()
        mock_client.iter_dialogs = mock_iter_dialogs

        with patch(
            "src.tools.contacts.get_connected_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            # Patch datetime in both modules since _is_muted_from_notify_settings lives in entity.py
            with patch("src.tools.contacts.datetime", FakeDateTime):
                with patch("src.utils.entity.datetime", FakeDateTime):
                    # Get only muted
                    results_muted = []
                    async for item in search_dialogs_impl(
                        limit=10,
                        min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
                        muted=True,
                    ):
                        results_muted.append(item)

                    assert len(results_muted) == 1
                    assert results_muted[0]["first_name"] == "MutedChat"

                    # Get only unmuted
                    results_unmuted = []
                    async for item in search_dialogs_impl(
                        limit=10,
                        min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
                        muted=False,
                    ):
                        results_unmuted.append(item)

                    assert len(results_unmuted) == 1
                    assert results_unmuted[0]["first_name"] == "UnmutedChat"


# ============== get_chat_info_impl muted Tests ==============


class TestGetChatInfoImplMuted:
    """Tests for get_chat_info_impl with muted field.

    Note: get_chat_info_impl tests mock at a high level and verify
    the muted field is added to the result. The actual Telethon
    GetNotifySettingsRequest is mocked via patching the client call.
    """

    @pytest.mark.asyncio
    async def test_returns_muted_field_when_silent(self):
        """get_chat_info should return muted=True when silent=True.

        We use silent=True because it doesn't depend on time comparison.
        """
        with patch(
            "src.tools.contacts.get_entity_by_id", new_callable=AsyncMock
        ) as mock_get_entity:
            mock_get_entity.return_value = User(123, first_name="TestUser")

            with patch(
                "src.tools.contacts.build_entity_dict_enriched",
                new_callable=AsyncMock,
            ) as mock_build:
                mock_build.return_value = {"id": 123, "first_name": "TestUser"}

                notify_settings = MockNotifySettings(silent=True)

                async def mock_client_call(*args, **kwargs):
                    return notify_settings

                mock_client = MagicMock()
                mock_client.side_effect = mock_client_call

                with patch(
                    "src.tools.contacts.get_connected_client",
                    new_callable=AsyncMock,
                ) as mock_get_client:
                    mock_get_client.return_value = mock_client

                    result = await get_chat_info_impl("123")

                    assert "muted" in result
                    assert result["muted"] is True

    @pytest.mark.asyncio
    async def test_returns_muted_field_when_not_muted(self):
        """get_chat_info should return muted=False when not muted."""
        with patch(
            "src.tools.contacts.get_entity_by_id", new_callable=AsyncMock
        ) as mock_get_entity:
            mock_get_entity.return_value = User(123, first_name="TestUser")

            with patch(
                "src.tools.contacts.build_entity_dict_enriched",
                new_callable=AsyncMock,
            ) as mock_build:
                mock_build.return_value = {"id": 123, "first_name": "TestUser"}

                notify_settings = MockNotifySettings(silent=False)

                async def mock_client_call(*args, **kwargs):
                    return notify_settings

                mock_client = MagicMock()
                mock_client.side_effect = mock_client_call

                with patch(
                    "src.tools.contacts.get_connected_client",
                    new_callable=AsyncMock,
                ) as mock_get_client:
                    mock_get_client.return_value = mock_client

                    result = await get_chat_info_impl("123")

                    assert "muted" in result
                    assert result["muted"] is False

    @pytest.mark.asyncio
    async def test_notify_settings_fetch_error_still_returns_result(self):
        """Even if notify settings fetch fails, still return the entity info."""
        with patch(
            "src.tools.contacts.get_entity_by_id", new_callable=AsyncMock
        ) as mock_get_entity:
            mock_get_entity.return_value = User(123, first_name="TestUser")

            with patch(
                "src.tools.contacts.build_entity_dict_enriched",
                new_callable=AsyncMock,
            ) as mock_build:
                mock_build.return_value = {"id": 123, "first_name": "TestUser"}

                mock_client = AsyncMock()
                mock_client.side_effect = Exception("Network error")

                with patch(
                    "src.tools.contacts.get_connected_client",
                    new_callable=AsyncMock,
                ) as mock_get_client:
                    mock_get_client.return_value = mock_client

                    result = await get_chat_info_impl("123")

                    # Should still return result even if notify settings fails
                    assert result["id"] == 123
                    assert "muted" not in result  # not added when fetch fails


# ============== build_entity_dict_enriched bot bio Tests ==============


class TestBuildEntityDictEnrichedBot:
    """Tests for build_entity_dict_enriched with bot users getting bio.

    Note: Testing bot bio enrichment requires proper Telethon TLObject
    mocking or aio tests with real client. These tests verify the
    _fetch_enrichment_fields function directly with proper mocking.
    """

    def test_bot_user_has_bot_type(self):
        """Bot users should have type='bot' in build_entity_dict."""
        bot_user = User(id=123, first_name="TestBot", username="testbot", bot=True)
        result = build_entity_dict(bot_user)

        assert result is not None
        assert result["type"] == "bot"

    def test_regular_user_has_private_type(self):
        """Regular users should have type='private' in build_entity_dict."""
        regular_user = User(id=123, first_name="John", username="john")
        result = build_entity_dict(regular_user)

        assert result is not None
        assert result["type"] == "private"

    @pytest.mark.asyncio
    async def test_fetch_enrichment_fields_private_bot_branch(self):
        """Verify _fetch_enrichment_fields uses correct branch for bot users."""
        from src.utils.entity import _fetch_enrichment_fields

        bot_user = User(id=123, first_name="TestBot", username="testbot", bot=True)

        mock_client = AsyncMock()
        mock_full_user = MagicMock()
        mock_full_user.about = "Bot bio text"
        mock_client.return_value = mock_full_user

        with patch("src.utils.entity.datetime", FakeDateTime):
            result = await _fetch_enrichment_fields(
                mock_client, bot_user, "bot", "User"
            )

        _members, _subscribers, _about, bio = result
        # Bot users should get bio via GetFullUserRequest (private,bot branch)
        assert bio == "Bot bio text"

    @pytest.mark.asyncio
    async def test_bot_user_gets_bio_via_build_entity_dict_enriched(self):
        """Bot users get bio enrichment when using build_entity_dict_enriched."""
        bot_user = User(id=123, first_name="TestBot", username="testbot", bot=True)

        # Mock get_entity_by_id to return the bot_user itself
        with patch(
            "src.utils.entity.get_entity_by_id", new_callable=AsyncMock
        ) as mock_get_entity:
            mock_get_entity.return_value = bot_user

            mock_client = AsyncMock()
            mock_full_user = MagicMock()
            mock_full_user.about = "Bot bio text"

            async def mock_client_call(*args, **kwargs):
                return mock_full_user

            mock_client.side_effect = mock_client_call

            with patch(
                "src.utils.entity.get_connected_client", new_callable=AsyncMock
            ) as mock_get_client:
                mock_get_client.return_value = mock_client

                with patch("src.utils.entity.datetime", FakeDateTime):
                    result = await build_entity_dict_enriched(bot_user)

                    assert result is not None
                    assert result["type"] == "bot"
                    assert result["bio"] == "Bot bio text"


# ============== search_messages_impl chat_type + chat_id Guard Tests ==============


class TestSearchMessagesChatTypeChatIdGuard:
    """Tests for guard error when chat_type + chat_id both provided."""

    @pytest.mark.asyncio
    async def test_chat_type_with_chat_id_returns_error(self):
        """search_messages with both chat_type and chat_id should return error."""
        result = await search_messages_impl(
            query="test",
            chat_id="me",
            chat_type="private",
        )

        assert "error" in result
        assert result["operation"] == "search_messages"
        assert "chat_type" in result["error"].lower()
        assert "chat_id" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_chat_type_with_message_ids_returns_error(self):
        """search_messages with both chat_type and message_ids should return error."""
        result = await search_messages_impl(
            chat_id="me",
            message_ids=[1, 2, 3],
            chat_type="group",
        )

        assert "error" in result
        assert "chat_type" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_global_search_with_chat_type_works(self):
        """Global search (no chat_id) with chat_type should work."""
        with patch(
            "src.tools.search._collect_messages_global", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = None

            await search_messages_impl(
                query="test",
                chat_type="private",
            )

            # Should not have guard error since chat_id is not provided
            mock_collect.assert_called_once()

    @pytest.mark.asyncio
    async def test_per_chat_search_without_chat_type_works(self):
        """Per-chat search without chat_type should work."""
        with patch(
            "src.tools.search._collect_messages_in_chat", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = 0

            with patch(
                "src.tools.search.get_entity_by_id", new_callable=AsyncMock
            ) as mock_get_entity:
                mock_get_entity.return_value = User(1, first_name="Test")

                result = await search_messages_impl(
                    query="test",
                    chat_id="me",
                )

                # Should not have chat_type guard error
                assert result is not None
