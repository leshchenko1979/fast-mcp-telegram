"""Tests for find_chats date filtering functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.contacts import (
    _dialog_in_date_range,
    _matches_dialog_query,
    _parse_iso_date,
    build_dialog_entity_dict,
)


# Fixtures for entity types
class MockUser:
    def __init__(self, id, first_name="", last_name="", username="", phone=""):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.phone = phone
        self.title = None


class MockChat:
    def __init__(self, id, title="", username=""):
        self.id = id
        self.title = title
        self.first_name = None
        self.last_name = None
        self.username = username
        self.phone = None


class MockDialog:
    def __init__(self, entity, date=None):
        self.entity = entity
        self.date = date


# ============== Helper Function Tests ==============


class TestParseIsoDate:
    """Tests for _parse_iso_date helper."""

    def test_valid_date(self):
        result = _parse_iso_date("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_valid_date_with_time(self):
        result = _parse_iso_date("2024-06-15T10:30:00")
        assert result is not None
        assert result.hour == 10
        assert result.minute == 30

    def test_valid_date_with_z_suffix(self):
        result = _parse_iso_date("2024-01-15T00:00:00Z")
        assert result is not None

    def test_invalid_date_returns_none(self):
        result = _parse_iso_date("not-a-date")
        assert result is None

    def test_none_returns_none(self):
        result = _parse_iso_date(None)
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_iso_date("")
        assert result is None


class TestMatchesDialogQuery:
    """Tests for _matches_dialog_query helper."""

    def test_no_query_matches_all(self):
        user = MockUser(1, first_name="John", last_name="Doe")
        assert _matches_dialog_query(user, "") is True

    def test_query_matches_title(self):
        chat = MockChat(1, title="Project Alpha")
        assert _matches_dialog_query(chat, "project") is True
        assert _matches_dialog_query(chat, "alpha") is True

    def test_query_matches_username(self):
        chat = MockChat(1, title="Chat", username="project_chat")
        assert _matches_dialog_query(chat, "project") is True

    def test_query_matches_first_name(self):
        user = MockUser(1, first_name="John", last_name="Doe")
        assert _matches_dialog_query(user, "john") is True

    def test_query_matches_last_name(self):
        user = MockUser(1, first_name="John", last_name="Doe")
        assert _matches_dialog_query(user, "doe") is True

    def test_query_matches_phone(self):
        user = MockUser(1, phone="+1234567890")
        assert _matches_dialog_query(user, "+123") is True

    def test_query_case_insensitive(self):
        chat = MockChat(1, title="Project Alpha")
        # query is already lowercased by caller
        assert _matches_dialog_query(chat, "project") is True
        assert _matches_dialog_query(chat, "alpha") is True

    def test_query_no_match(self):
        chat = MockChat(1, title="Project Alpha")
        assert _matches_dialog_query(chat, "xyz") is False

    def test_query_combined_fields(self):
        """Test that query matches across all fields."""
        user = MockUser(
            1,
            first_name="John",
            last_name="Doe",
            username="johndoe",
            phone="+1234567890",
        )
        assert _matches_dialog_query(user, "doe") is True
        assert _matches_dialog_query(user, "johndoe") is True
        assert _matches_dialog_query(user, "+123") is True


class TestDialogInDateRange:
    """Tests for _dialog_in_date_range helper."""

    @pytest.mark.asyncio
    async def test_dialog_date_in_range(self):
        dialog_date = datetime(2024, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        in_range, can_break = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
            max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
        )

        assert in_range is True
        assert can_break is False

    @pytest.mark.asyncio
    async def test_dialog_date_below_min_triggers_break(self):
        """When dialog is older than min_date, we can break early (sorted order)."""
        dialog_date = datetime(2023, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        in_range, can_break = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
            max_date_dt=None,
        )

        assert in_range is False
        assert can_break is True  # Can break because dialogs are sorted newest-first

    @pytest.mark.asyncio
    async def test_dialog_date_above_max_continues(self):
        """When dialog is newer than max_date, skip but don't break."""
        dialog_date = datetime(2025, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        in_range, can_break = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
            max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
        )

        assert in_range is False
        assert can_break is False  # Don't break, keep checking other dialogs

    @pytest.mark.asyncio
    async def test_no_date_no_break(self):
        """When dialog has no date, we can't break early."""
        dialog = MockDialog(MockUser(1), date=None)

        in_range, can_break = await _dialog_in_date_range(
            dialog.entity, None, None, min_date_dt=None, max_date_dt=None
        )

        assert in_range is True
        assert can_break is False

    @pytest.mark.asyncio
    async def test_no_date_with_fallback_passes(self):
        """When dialog has no date but fallback date is in range, include it."""
        dialog = MockDialog(MockUser(1), date=None)

        with patch(
            "src.tools.contacts._get_last_message_date", new_callable=AsyncMock
        ) as mock_fallback:
            # Return timezone-aware ISO string
            mock_fallback.return_value = "2024-06-15T00:00:00+00:00"

            in_range, can_break = await _dialog_in_date_range(
                dialog.entity,
                None,
                None,
                min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
                max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
            )

            assert in_range is True
            assert can_break is False

    @pytest.mark.asyncio
    async def test_no_date_with_fallback_below_min(self):
        """When fallback date is below min_date, skip without breaking."""
        dialog = MockDialog(MockUser(1), date=None)

        with patch(
            "src.tools.contacts._get_last_message_date", new_callable=AsyncMock
        ) as mock_fallback:
            mock_fallback.return_value = "2023-06-15T00:00:00+00:00"

            in_range, can_break = await _dialog_in_date_range(
                dialog.entity,
                None,
                None,
                min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
                max_date_dt=None,
            )

            assert in_range is False
            assert can_break is False  # Never break on fallback (not sorted)

    @pytest.mark.asyncio
    async def test_no_date_with_fallback_above_max(self):
        """When fallback date is above max_date, skip without breaking."""
        dialog = MockDialog(MockUser(1), date=None)

        with patch(
            "src.tools.contacts._get_last_message_date", new_callable=AsyncMock
        ) as mock_fallback:
            mock_fallback.return_value = "2025-06-15T00:00:00+00:00"

            in_range, can_break = await _dialog_in_date_range(
                dialog.entity,
                None,
                None,
                min_date_dt=None,
                max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
            )

            assert in_range is False
            assert can_break is False  # Never break on fallback


# ============== build_dialog_entity_dict Tests ==============


class TestBuildDialogEntityDict:
    """Tests for build_dialog_entity_dict function."""

    def test_includes_last_activity_date(self):
        dialog_date = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
        dialog = MockDialog(MockUser(1, first_name="John"), date=dialog_date)

        result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["id"] == 1
        assert result["first_name"] == "John"
        assert result["last_activity_date"] is not None
        assert "2024-06-15" in result["last_activity_date"]

    def test_none_date_returns_null_last_activity(self):
        dialog = MockDialog(MockUser(1, first_name="John"), date=None)

        result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["last_activity_date"] is None

    def test_chat_with_title(self):
        dialog_date = datetime(2024, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockChat(1, title="Test Chat"), date=dialog_date)

        result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["title"] == "Test Chat"
        assert result["last_activity_date"] is not None

    def test_username_included(self):
        dialog_date = datetime(2024, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1, username="johndoe"), date=dialog_date)

        result = build_dialog_entity_dict(dialog, dialog.entity)

        assert result is not None
        assert result["username"] == "johndoe"


# ============== Integration Tests (simpler mocks) ==============


@pytest.mark.asyncio
async def test_find_chats_global_single_term_passes_through():
    """_find_chats_global passes through to _search_contacts_as_list."""
    with patch(
        "src.tools.contacts._search_contacts_as_list", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = [{"id": 1, "title": "Test"}]

        from src.tools.contacts import _find_chats_global

        result = await _find_chats_global("test", 10, None, None)

        mock_search.assert_called_once()
        assert "chats" in result
        assert len(result["chats"]) == 1


@pytest.mark.asyncio
async def test_search_dialogs_impl_respects_max_date():
    """Dialogs newer than max_date should be skipped."""
    # Dialog from 2025 (newer than max_date 2024)
    dialog = MockDialog(
        MockUser(1, first_name="Future"), date=datetime(2025, 6, 15, tzinfo=UTC)
    )

    async def mock_iter_dialogs():
        yield dialog

    mock_client = MagicMock()
    mock_client.iter_dialogs = mock_iter_dialogs

    with patch(
        "src.tools.contacts.get_connected_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.return_value = mock_client

        from src.tools.contacts import search_dialogs_impl

        results = []
        async for item in search_dialogs_impl(limit=10, max_date="2024-12-31"):
            results.append(item)

        # Should be skipped because 2025 > 2024
        assert not results


@pytest.mark.asyncio
async def test_search_dialogs_impl_respects_min_date_early_break():
    """Should break when hitting dialogs older than min_date.

    Note: iter_dialogs returns newest-first. So when we hit a dialog
    older than min_date, all subsequent dialogs will also be older.
    """
    # Dialogs from newest to oldest (iter_dialogs returns newest first)
    dialogs = [
        MockDialog(
            MockUser(3, first_name="Recent"), date=datetime(2024, 6, 15, tzinfo=UTC)
        ),
        MockDialog(
            MockUser(2, first_name="Old2"), date=datetime(2020, 2, 1, tzinfo=UTC)
        ),
        MockDialog(
            MockUser(1, first_name="Old1"), date=datetime(2020, 1, 1, tzinfo=UTC)
        ),
    ]

    async def mock_iter_dialogs():
        for d in dialogs:
            yield d

    mock_client = MagicMock()
    mock_client.iter_dialogs = mock_iter_dialogs

    with patch(
        "src.tools.contacts.get_connected_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.return_value = mock_client

        from src.tools.contacts import search_dialogs_impl

        results = []
        async for item in search_dialogs_impl(limit=10, min_date="2024-01-01"):
            results.append(item)

        # Should only get "Recent" (2024), then hit "Old2" which is below min_date
        # and break (since all subsequent are older)
        assert len(results) == 1
        assert results[0]["first_name"] == "Recent"
