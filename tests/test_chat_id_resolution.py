"""Tests for chat_id resolution and consistent get_messages behavior across ID formats."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.tl.types import PeerChannel, PeerUser

from src.tools.search import search_messages_impl
from src.utils.entity import (
    compute_entity_identifier,
    get_entity_by_id,
    is_ambiguous_peer_scalar,
)

# @telemtrs / Telemt forum — issue #49 repro chat
TELEMTRS_BARE_CHANNEL_ID = 3850125609
TELEMTRS_FULL_CHAT_ID = "-1003850125609"
TELEMTRS_FREE_PROXY_TOPIC_ID = 16160

CHAT_ID_FORMATS = (
    "@telemtrs",
    "telemtrs",
    str(TELEMTRS_BARE_CHANNEL_ID),
    TELEMTRS_FULL_CHAT_ID,
)


def _make_channel_entity(
    entity_id: int = TELEMTRS_BARE_CHANNEL_ID,
    *,
    forum: bool = True,
    username: str = "telemtrs",
):
    return type(
        "Channel",
        (),
        {
            "id": entity_id,
            "title": "Telemt",
            "forum": forum,
            "broadcast": False,
            "megagroup": True,
            "username": username,
            "first_name": None,
            "last_name": None,
            "phone": None,
        },
    )()


def _make_user_entity(entity_id: int):
    return type(
        "User",
        (),
        {
            "id": entity_id,
            "first_name": "Not",
            "last_name": "AForum",
            "username": None,
            "phone": None,
        },
    )()


class TestAmbiguousPeerScalar:
    def test_telemtrs_bare_channel_id_is_ambiguous(self):
        assert is_ambiguous_peer_scalar(str(TELEMTRS_BARE_CHANNEL_ID)) is True

    def test_telemtrs_full_chat_id_is_ambiguous(self):
        assert is_ambiguous_peer_scalar(TELEMTRS_FULL_CHAT_ID) is True

    def test_username_not_ambiguous(self):
        assert is_ambiguous_peer_scalar("@telemtrs") is False
        assert is_ambiguous_peer_scalar("telemtrs") is False


class TestComputeEntityIdentifier:
    def test_channel_with_username_prefers_username(self):
        entity = _make_channel_entity()
        assert compute_entity_identifier(entity) == "telemtrs"

    def test_channel_without_username_uses_minus_100_prefix(self):
        entity = _make_channel_entity(username=None)
        assert compute_entity_identifier(entity) == TELEMTRS_FULL_CHAT_ID

    def test_full_id_string_unchanged_when_already_prefixed(self):
        entity = type(
            "Channel", (), {"id": int(TELEMTRS_FULL_CHAT_ID), "username": None}
        )()
        assert compute_entity_identifier(entity) == TELEMTRS_FULL_CHAT_ID


@pytest.mark.asyncio
async def test_get_entity_by_id_tries_peer_channel_before_user():
    """Bare numeric ids must try PeerChannel before PeerUser to avoid wrong peer type."""
    channel = _make_channel_entity()
    client = AsyncMock()
    seen_candidates: list = []

    async def fake_get_entity(candidate):
        seen_candidates.append(candidate)
        if isinstance(candidate, PeerUser):
            raise ValueError("wrong peer type")
        if isinstance(candidate, PeerChannel):
            return channel
        if candidate == TELEMTRS_BARE_CHANNEL_ID:
            raise ValueError("raw int alone failed")
        raise ValueError(f"unexpected candidate {candidate!r}")

    client.get_entity = fake_get_entity

    resolved = await get_entity_by_id(str(TELEMTRS_BARE_CHANNEL_ID), client=client)
    assert resolved is channel
    assert any(isinstance(c, PeerChannel) for c in seen_candidates)


@pytest.mark.asyncio
async def test_get_entity_by_id_wrong_peer_if_user_resolves_first():
    """Documents risk: if PeerUser succeeds before PeerChannel, forum fetch targets wrong chat."""
    user = _make_user_entity(TELEMTRS_BARE_CHANNEL_ID)
    client = AsyncMock()

    async def fake_get_entity(candidate):
        if isinstance(candidate, (int, PeerUser)) and candidate in (
            TELEMTRS_BARE_CHANNEL_ID,
            PeerUser(TELEMTRS_BARE_CHANNEL_ID),
        ):
            return user
        raise ValueError("channel not found")

    client.get_entity = fake_get_entity

    resolved = await get_entity_by_id(str(TELEMTRS_BARE_CHANNEL_ID), client=client)
    assert resolved is user
    assert not getattr(resolved, "forum", False)


@pytest.mark.asyncio
async def test_replies_use_same_entity_regardless_of_passed_chat_id_string():
    """search_messages_impl must resolve entity once; chat_id string format should not change path."""
    channel = _make_channel_entity()
    fetch_calls: list[str] = []

    async def fake_fetch_replies(
        _client,
        entity,
        reply_to_id,
        limit,
        query=None,
        include_chat_entity=False,
        thread_scope="auto",
        min_date=None,
        max_date=None,
    ):
        fetch_calls.append(
            f"{type(entity).__name__}:{getattr(entity, 'id', None)}:{reply_to_id}:{limit}"
        )
        return [{"id": 1}], None

    with (
        patch(
            "src.tools.search.replies.get_entity_by_id",
            new_callable=AsyncMock,
            return_value=channel,
        ),
        patch(
            "src.tools.search.replies.get_connected_client",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
        patch(
            "src.tools.search.replies._fetch_replies", side_effect=fake_fetch_replies
        ),
    ):
        for chat_id in CHAT_ID_FORMATS:
            result = await search_messages_impl(
                chat_id=chat_id,
                reply_to_id=TELEMTRS_FREE_PROXY_TOPIC_ID,
                thread_scope="auto",
                limit=10,
            )

        assert "error" not in result
        assert len(fetch_calls) == len(CHAT_ID_FORMATS)
        assert len(set(fetch_calls)) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forum_topic_message_count_same_across_chat_id_formats():
    """Live: all canonical chat_id forms must return the same topic message set."""
    if os.getenv("FAST_MCP_TELEGRAM_LIVE_TESTS") != "1":
        pytest.skip("set FAST_MCP_TELEGRAM_LIVE_TESTS=1 to run")

    results: dict[str, dict] = {}
    for chat_id in CHAT_ID_FORMATS:
        out = await search_messages_impl(
            chat_id=chat_id,
            reply_to_id=TELEMTRS_FREE_PROXY_TOPIC_ID,
            thread_scope="auto",
            limit=50,
        )
        if "error" in out:
            pytest.fail(f"chat_id={chat_id!r}: {out['error']}")
        results[chat_id] = out

    counts = {cid: len(r.get("messages") or []) for cid, r in results.items()}
    id_sets = {
        cid: {m["id"] for m in (r.get("messages") or []) if m.get("id") is not None}
        for cid, r in results.items()
    }

    unique_counts = set(counts.values())
    assert len(unique_counts) == 1, f"message counts differ by format: {counts}"
    assert len({frozenset(s) for s in id_sets.values()}) == 1, (
        f"message id sets differ by format: { {k: len(v) for k, v in id_sets.items()} }"
    )
    assert counts["@telemtrs"] >= 40, f"expected full topic, got {counts}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chat_info_forum_flag_for_numeric_chat_ids():
    """Live: get_chat_info must see the same forum group for bare and -100 ids."""
    if os.getenv("FAST_MCP_TELEGRAM_LIVE_TESTS") != "1":
        pytest.skip("set FAST_MCP_TELEGRAM_LIVE_TESTS=1 to run")

    from src.tools.chat_discovery.chat_info import get_chat_info_impl

    for chat_id in (str(TELEMTRS_BARE_CHANNEL_ID), TELEMTRS_FULL_CHAT_ID):
        info = await get_chat_info_impl(chat_id)
        assert "error" not in info, info.get("error", info)
        assert info.get("is_forum") is True, f"{chat_id!r}: {info}"
        assert info.get("id") == TELEMTRS_BARE_CHANNEL_ID
        assert info.get("username") == "telemtrs"
