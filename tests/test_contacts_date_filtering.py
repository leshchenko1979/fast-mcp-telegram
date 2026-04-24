"""Tests for find_chats date filtering functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.contacts import (
    _dialog_in_date_range,
    _find_chats_global,
    _matches_dialog_query,
    _parse_iso_date,
    build_dialog_entity_dict,
    find_chats_impl,
)
from tests.conftest import MockChat, MockDialog, MockUser, make_user

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

        result = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
            max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_dialog_date_below_min_excluded(self):
        """When dialog is older than min_date, it should be excluded."""
        dialog_date = datetime(2023, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        result = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
            max_date_dt=None,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_dialog_date_above_max_excluded(self):
        """When dialog is newer than max_date, it should be excluded."""
        dialog_date = datetime(2025, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        result = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
            max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_no_date_included(self):
        """When dialog has no date, it should be included (no date filtering applied)."""
        dialog = MockDialog(MockUser(1), date=None)

        result = await _dialog_in_date_range(
            dialog.entity, None, None, min_date_dt=None, max_date_dt=None
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_no_date_with_fallback_in_range(self):
        """When dialog has no date but fallback date is in range, include it."""
        dialog = MockDialog(MockUser(1), date=None)

        with patch(
            "src.tools.contacts._get_last_message_date", new_callable=AsyncMock
        ) as mock_fallback:
            mock_fallback.return_value = "2024-06-15T00:00:00+00:00"

            result = await _dialog_in_date_range(
                dialog.entity,
                None,
                None,
                min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
                max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_no_date_with_fallback_below_min(self):
        """When fallback date is below min_date, exclude it."""
        dialog = MockDialog(MockUser(1), date=None)

        with patch(
            "src.tools.contacts._get_last_message_date", new_callable=AsyncMock
        ) as mock_fallback:
            mock_fallback.return_value = "2023-06-15T00:00:00+00:00"

            result = await _dialog_in_date_range(
                dialog.entity,
                None,
                None,
                min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
                max_date_dt=None,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_no_date_with_fallback_above_max(self):
        """When fallback date is above max_date, exclude it."""
        dialog = MockDialog(MockUser(1), date=None)

        with patch(
            "src.tools.contacts._get_last_message_date", new_callable=AsyncMock
        ) as mock_fallback:
            mock_fallback.return_value = "2025-06-15T00:00:00+00:00"

            result = await _dialog_in_date_range(
                dialog.entity,
                None,
                None,
                min_date_dt=None,
                max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_dialog_date_only_no_bounds(self):
        """dialog_date is set but both bounds are None -> dialog-only search, no date filtering."""
        dialog_date = datetime(2024, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        result = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=None,
            max_date_dt=None,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_dialog_date_on_max_boundary_inclusive(self):
        """dialog_date exactly on max boundary should be included (inclusive)."""
        max_date_dt = datetime(2024, 6, 15, tzinfo=UTC)
        dialog_date = datetime(2024, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        result = await _dialog_in_date_range(
            dialog.entity,
            None,
            dialog_date,
            min_date_dt=None,
            max_date_dt=max_date_dt,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_naive_dialog_date_against_aware_bounds(self):
        """Test that naive dialog_date (like Telethon returns) works against aware bounds.

        This is a regression test for the bug where Telethon's iter_dialogs()
        returns timezone-naive datetimes, but _parse_iso_date() returns timezone-aware
        datetimes. Comparing them raised TypeError.
        """
        naive_dialog_date = datetime(2024, 6, 15, 10, 30, 0)
        dialog = MockDialog(MockUser(1), date=naive_dialog_date)

        min_date_dt = datetime(2024, 1, 1, tzinfo=UTC)
        max_date_dt = datetime(2024, 12, 31, tzinfo=UTC)

        result = await _dialog_in_date_range(
            dialog.entity,
            None,
            naive_dialog_date,
            min_date_dt=min_date_dt,
            max_date_dt=max_date_dt,
        )

        assert result is True


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

    def test_base_entity_returns_none(self):
        """When build_entity_dict returns None, build_dialog_entity_dict returns None."""
        dialog_date = datetime(2024, 6, 15, tzinfo=UTC)
        dialog = MockDialog(MockUser(1), date=dialog_date)

        with patch("src.utils.entity.build_entity_dict", return_value=None):
            result = build_dialog_entity_dict(dialog, dialog.entity)
            assert result is None

    def test_isoformat_exception_handled(self):
        """When dialog.date.isoformat() raises, last_activity_date should be None."""

        class BadDate:
            def isoformat(self):
                raise ValueError("bad date")

        dialog = MockDialog(MockUser(1), date=BadDate())
        result = build_dialog_entity_dict(dialog, dialog.entity)
        assert result is not None
        assert result["last_activity_date"] is None


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
    dialog = MockDialog(
        MockUser(1, first_name="Future"), date=datetime(2025, 6, 15, tzinfo=UTC)
    )

    async def mock_iter_dialogs(limit=None, folder=None):
        yield dialog

    mock_client = MagicMock()
    mock_client.iter_dialogs = mock_iter_dialogs

    with patch(
        "src.tools.contacts.get_connected_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.return_value = mock_client

        from src.tools.contacts import search_dialogs_impl

        results = []
        async for item in search_dialogs_impl(
            limit=10,
            max_date_dt=datetime(2024, 12, 31, tzinfo=UTC),
        ):
            results.append(item)

        assert not results


@pytest.mark.asyncio
async def test_search_dialogs_impl_respects_min_date():
    """Should return only dialogs within min_date range.

    Note: The early break optimization was removed because pinned chats
    can break chronological ordering.
    """
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

    async def mock_iter_dialogs(limit=None, folder=None):
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
        async for item in search_dialogs_impl(
            limit=10,
            min_date_dt=datetime(2024, 1, 1, tzinfo=UTC),
        ):
            results.append(item)

        assert len(results) == 1
        assert results[0]["first_name"] == "Recent"


@pytest.mark.asyncio
async def test_find_chats_impl_without_date_filters_uses_global():
    """When no date filters are provided, find_chats_impl should use _find_chats_global."""
    with patch(
        "src.tools.contacts._search_contacts_as_list", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = [{"id": 1, "title": "Test"}]

        result = await find_chats_impl(query="test", limit=10)

        mock_search.assert_called_once()
        assert "chats" in result
        assert len(result["chats"]) == 1


@pytest.mark.asyncio
async def test_find_chats_impl_with_date_filters_uses_dialog_search():
    """When any date filter is provided, find_chats_impl should use _find_chats_by_dialogs."""
    dialog = MockDialog(
        MockUser(1, first_name="John"), date=datetime(2024, 6, 15, tzinfo=UTC)
    )

    async def mock_iter_dialogs(limit=None, folder=None):
        yield dialog

    mock_client = MagicMock()
    mock_client.iter_dialogs = mock_iter_dialogs

    with patch(
        "src.tools.contacts.get_connected_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.return_value = mock_client

        result = await find_chats_impl(query="John", limit=10, min_date="2024-01-01")

        assert "chats" in result
        assert len(result["chats"]) == 1


@pytest.mark.asyncio
async def test_find_chats_impl_date_filter_no_results_returns_error():
    """When date filters find nothing, should return structured error."""

    async def mock_iter_dialogs(limit=None, folder=None):
        if False:
            yield

    mock_client = MagicMock()
    mock_client.iter_dialogs = mock_iter_dialogs

    with patch(
        "src.tools.contacts.get_connected_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.return_value = mock_client

        result = await find_chats_impl(
            query="NoMatch", limit=10, min_date="2099-01-01", max_date="2099-12-31"
        )

        assert "error" in result
        assert result["operation"] == "find_chats"
        assert "No chats found" in result["error"]


@pytest.mark.asyncio
async def test_find_chats_impl_invalid_min_date_returns_error():
    """When min_date is invalid, should return structured error."""
    result = await find_chats_impl(query="test", limit=10, min_date="invalid-date")

    assert "error" in result
    assert result["operation"] == "find_chats"
    assert "Invalid min_date format" in result["error"]
    assert "invalid-date" in result["error"]


@pytest.mark.asyncio
async def test_find_chats_impl_invalid_max_date_returns_error():
    """When max_date is invalid, should return structured error."""
    result = await find_chats_impl(query="test", limit=10, max_date="not-a-date")

    assert "error" in result
    assert result["operation"] == "find_chats"
    assert "Invalid max_date format" in result["error"]
    assert "not-a-date" in result["error"]


@pytest.mark.asyncio
async def test_find_chats_global_multi_term_merges_results():
    """Multi-term global search should merge and deduplicate results round-robin."""

    async def mock_gen_1():
        yield {"id": 1, "title": "Chat Alpha"}
        yield {"id": 2, "title": "Chat Beta"}

    async def mock_gen_2():
        yield {"id": 2, "title": "Chat Beta"}
        yield {"id": 3, "title": "Chat Gamma"}

    with patch(
        "src.tools.contacts.search_contacts_native",
        new=MagicMock(side_effect=[mock_gen_1(), mock_gen_2()]),
    ):
        result = await _find_chats_global("alpha,beta", 10, None, None)

        assert "chats" in result
        assert len(result["chats"]) == 3
        ids = {chat["id"] for chat in result["chats"]}
        assert ids == {1, 2, 3}


@pytest.mark.asyncio
async def test_find_chats_global_multi_term_no_results_returns_error():
    """Multi-term global search with no results should return structured error."""

    async def mock_gen_empty():
        return

    with patch(
        "src.tools.contacts.search_contacts_native",
        new=MagicMock(side_effect=[mock_gen_empty(), mock_gen_empty()]),
    ):
        result = await _find_chats_global("nonexistent1,nonexistent2", 10, None, None)

        assert "error" in result
        assert result["operation"] == "search_contacts_multi"
        assert "No contacts found" in result["error"]


# ============== _find_chats_by_include_peers date filtering tests ==============


@pytest.mark.asyncio
async def test_find_chats_by_include_peers_respects_min_date():
    """min_date filter should exclude peers with last_activity below the threshold.

    This is a regression test for the bug where _find_chats_by_include_peers
    received min_date/max_date parameters but never applied them.
    """
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, MagicMock

    from telethon.tl.types import InputPeerUser

    from src.tools.contacts import _find_chats_by_include_peers

    # Two users with different last_activity dates
    user_new = make_user(1, first_name="NewUser")
    user_old = make_user(2, first_name="OldUser")

    # Mock client that resolves entities and returns GetPeerDialogsResponse
    # For await client(GetPeerDialogsRequest(...)) to work, client must be AsyncMock
    mock_result = MagicMock()
    mock_result.dialogs = [
        MagicMock(peer=MagicMock(user_id=1)),
        MagicMock(peer=MagicMock(user_id=2)),
    ]
    mock_result.messages = [
        MagicMock(date=datetime(2024, 6, 15, tzinfo=UTC)),
        MagicMock(date=datetime(2020, 1, 1, tzinfo=UTC)),
    ]
    mock_client = AsyncMock(return_value=mock_result)

    async def mock_get_entity(inp_peer):
        if isinstance(inp_peer, InputPeerUser):
            if inp_peer.user_id == 1:
                return user_new
            if inp_peer.user_id == 2:
                return user_old
        return None

    mock_client.get_entity = mock_get_entity

    # Patch GetPeerDialogsRequest at the module level so it's recognized but not called
    with (
        patch("src.tools.contacts.GetPeerDialogsRequest", MagicMock()),
        patch(
            "src.tools.contacts.get_connected_client", AsyncMock(return_value=mock_client)
        ),
    ):
        result = await _find_chats_by_include_peers(
            client=mock_client,
            filter_dict={
                "include_peers": [
                    InputPeerUser(user_id=1, access_hash=0),
                    InputPeerUser(user_id=2, access_hash=0),
                ],
                "exclude_peers": [],
            },
            query=None,
            limit=10,
            chat_type=None,
            public=None,
            min_date="2024-01-01",
            max_date=None,
        )

    chats = result.get("chats", [])
    # NewUser (last_activity 2024-06-15 >= 2024-01-01) should be included
    # OldUser (last_activity 2020-01-01 < 2024-01-01) should be excluded
    assert len(chats) == 1, f"Expected 1 chat, got {len(chats)}: {chats}"
    assert chats[0]["first_name"] == "NewUser"


@pytest.mark.asyncio
async def test_find_chats_by_include_peers_fallback_iter_messages_uses_per_peer_entity():
    """When GetPeerDialogs omits last-activity, fallback must call iter_messages on that peer's entity."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, MagicMock

    from telethon.tl.types import InputPeerUser

    from src.tools.contacts import _find_chats_by_include_peers

    user_a = make_user(1, first_name="A")
    user_b = make_user(2, first_name="B")

    mock_result = MagicMock()
    mock_result.dialogs = [
        MagicMock(peer=MagicMock(user_id=1)),
        MagicMock(peer=MagicMock(user_id=2)),
    ]
    mock_result.messages = [
        MagicMock(date=None),
        MagicMock(date=None),
    ]

    mock_client = AsyncMock(return_value=mock_result)
    iter_entity_ids: list[int] = []

    async def mock_get_entity(inp_peer):
        if isinstance(inp_peer, InputPeerUser):
            if inp_peer.user_id == 1:
                return user_a
            if inp_peer.user_id == 2:
                return user_b
        return None

    async def iter_messages(entity, limit=1):
        iter_entity_ids.append(getattr(entity, "id", None))
        m = MagicMock()
        m.date = datetime(2024, 6, 1, tzinfo=UTC)
        yield m

    mock_client.get_entity = mock_get_entity
    mock_client.iter_messages = iter_messages

    with (
        patch("src.tools.contacts.GetPeerDialogsRequest", MagicMock()),
        patch(
            "src.tools.contacts.get_connected_client", AsyncMock(return_value=mock_client)
        ),
    ):
        result = await _find_chats_by_include_peers(
            client=mock_client,
            filter_dict={
                "include_peers": [
                    InputPeerUser(user_id=1, access_hash=0),
                    InputPeerUser(user_id=2, access_hash=0),
                ],
                "exclude_peers": [],
            },
            query=None,
            limit=10,
            chat_type=None,
            public=None,
            min_date="2024-01-01",
            max_date=None,
        )

    assert len(result.get("chats", [])) == 2
    assert iter_entity_ids == [1, 2], (
        f"iter_messages should run per peer entity; got order/ids {iter_entity_ids!r}"
    )


@pytest.mark.asyncio
async def test_find_chats_get_peer_dialogs_mismatch_warns(caplog):
    """Mismatched dialogs vs messages length should log a warning, not assume extra rows."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, MagicMock

    from telethon.tl.types import InputPeerUser

    from src.tools.contacts import _find_chats_by_include_peers

    u = make_user(1, first_name="Solo")
    mock_result = MagicMock()
    mock_result.dialogs = [MagicMock(peer=MagicMock(user_id=1))]
    mock_result.messages = [
        MagicMock(date=datetime(2024, 6, 1, tzinfo=UTC)),
        MagicMock(date=datetime(2024, 6, 2, tzinfo=UTC)),
    ]
    mock_client = AsyncMock(return_value=mock_result)
    mock_client.get_entity = AsyncMock(return_value=u)

    with (
        caplog.at_level("WARNING", logger="src.tools.contacts"),
        patch("src.tools.contacts.GetPeerDialogsRequest", MagicMock()),
        patch(
            "src.tools.contacts.get_connected_client", AsyncMock(return_value=mock_client)
        ),
    ):
        await _find_chats_by_include_peers(
            client=mock_client,
            filter_dict={
                "include_peers": [InputPeerUser(user_id=1, access_hash=0)],
                "exclude_peers": [],
            },
            query=None,
            limit=10,
            chat_type=None,
            public=None,
            min_date=None,
            max_date=None,
        )
    assert any("GetPeerDialogs" in r.message and "len(dialogs)" in r.message for r in caplog.records)
