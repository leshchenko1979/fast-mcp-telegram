"""Tests for common-groups enrichment in get_chat_info (_list_common_chats)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.tools.chat_discovery.chat_info import _list_common_chats, get_chat_info_impl
from tests.conftest import make_channel, make_chat, make_user


@pytest.mark.asyncio
async def test_get_chat_info_user_target_includes_common_chats():
    """User target -> common_chats + common_chats_has_more merged from RPC result."""
    entity = make_user(1001, first_name="Alexey", username="leshchenko1979")
    raw_chat_1 = SimpleNamespace(id=500, title="Group A", access_hash=1)
    raw_chat_2 = SimpleNamespace(id=501, title="Channel B", access_hash=2)

    client = AsyncMock(
        return_value=SimpleNamespace(count=5, chats=[raw_chat_1, raw_chat_2])
    )

    with (
        patch(
            "src.tools.chat_discovery.chat_info.get_entity_by_id",
            new=AsyncMock(return_value=entity),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.build_entity_dict_enriched",
            new=AsyncMock(
                return_value={"id": 1001, "title": "Alexey", "type": "private"}
            ),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.get_connected_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.build_entity_dict",
            side_effect=[
                {"id": 500, "title": "Group A", "type": "group"},
                {"id": 501, "title": "Channel B", "type": "channel"},
            ],
        ),
    ):
        result = await get_chat_info_impl("1001", common_chats_limit=10)

    assert result["id"] == 1001
    assert result["common_chats"] == [
        {"id": 500, "title": "Group A", "type": "group"},
        {"id": 501, "title": "Channel B", "type": "channel"},
    ]
    # ChatsSlice with count=5 but only 2 returned -> has_more True.
    assert result["common_chats_has_more"] is True
    request = client.await_args.args[0]
    assert request.max_id == 0
    assert request.limit == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entity, entity_type",
    [
        (make_chat(200, title="Group"), "group"),
        (make_channel(300, title="Channel"), "channel"),
    ],
)
async def test_get_chat_info_non_user_skips_common_chats(entity, entity_type):
    """Group/channel targets -> no common_chats key and no RPC attempted."""
    with (
        patch(
            "src.tools.chat_discovery.chat_info.get_entity_by_id",
            new=AsyncMock(return_value=entity),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.build_entity_dict_enriched",
            new=AsyncMock(
                return_value={
                    "id": entity.id,
                    "title": entity.title,
                    "type": entity_type,
                }
            ),
        ),
        patch(
            "src.tools.chat_discovery.chat_info._list_common_chats",
            new=AsyncMock(side_effect=RuntimeError("must not call")),
        ),
    ):
        result = await get_chat_info_impl(str(entity.id), common_chats_limit=10)

    assert "common_chats" not in result
    assert "common_chats_has_more" not in result


@pytest.mark.asyncio
async def test_get_chat_info_common_chats_rpc_failure_is_non_fatal():
    """RPC raising inside _list_common_chats -> profile returned, field omitted."""
    entity = make_user(1002, first_name="Bot", bot=True)
    client = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch(
            "src.tools.chat_discovery.chat_info.get_entity_by_id",
            new=AsyncMock(return_value=entity),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.build_entity_dict_enriched",
            new=AsyncMock(return_value={"id": 1002, "title": "Bot", "type": "bot"}),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.get_connected_client",
            new=AsyncMock(return_value=client),
        ),
    ):
        result = await get_chat_info_impl("1002", common_chats_limit=10)

    assert result["id"] == 1002
    assert "common_chats" not in result
    assert "common_chats_has_more" not in result


@pytest.mark.asyncio
async def test_list_common_chats_clamps_limit_low():
    """limit=0 -> clamped to 1 in the GetCommonChatsRequest."""
    entity = make_user(1003, first_name="Alice")
    client = AsyncMock(return_value=SimpleNamespace(chats=[]))

    with patch(
        "src.tools.chat_discovery.chat_info.get_connected_client",
        new=AsyncMock(return_value=client),
    ):
        result = await _list_common_chats(entity, limit=0)

    request = client.await_args.args[0]
    assert request.limit == 1
    # Empty chats, no count -> has_more False (0 >= 1 is False).
    assert result["common_chats_has_more"] is False


@pytest.mark.asyncio
async def test_list_common_chats_clamps_limit_high():
    """limit=5000 -> clamped to 100 in the GetCommonChatsRequest."""
    entity = make_user(1004, first_name="Bob")
    raw_chats = [
        SimpleNamespace(id=i, title=f"G{i}", access_hash=i) for i in range(100)
    ]
    client = AsyncMock(return_value=SimpleNamespace(chats=raw_chats))

    with (
        patch(
            "src.tools.chat_discovery.chat_info.get_connected_client",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "src.tools.chat_discovery.chat_info.build_entity_dict",
            side_effect=[
                {"id": c.id, "title": c.title, "type": "group"} for c in raw_chats
            ],
        ),
    ):
        result = await _list_common_chats(entity, limit=5000)

    request = client.await_args.args[0]
    assert request.limit == 100
    assert len(result["common_chats"]) == 100
    # Plain Chats (no count) with exactly limit entries -> has_more True.
    assert result["common_chats_has_more"] is True


@pytest.mark.asyncio
async def test_list_common_chats_non_user_returns_none():
    """Helper guard: non-User entity -> None without touching the client."""
    entity = make_chat(201, title="Group")
    client = AsyncMock(side_effect=RuntimeError("must not call"))

    with patch(
        "src.tools.chat_discovery.chat_info.get_connected_client",
        new=AsyncMock(return_value=client),
    ):
        result = await _list_common_chats(entity, limit=10)

    assert result is None
    client.assert_not_awaited()
