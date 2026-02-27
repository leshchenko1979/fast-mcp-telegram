import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.tools.contacts import _list_forum_topics, get_chat_info_impl
from src.tools.messages import (
    _extract_send_message_params,
    _send_message_or_files,
    edit_message_impl,
)
from src.utils.message_format import _extract_topic_metadata, build_message_result


class Channel:
    def __init__(self, *, chat_id: int, title: str, forum: bool):
        self.id = chat_id
        self.title = title
        self.forum = forum
        self.broadcast = True
        self.megagroup = False


@pytest.mark.asyncio
async def test_build_message_result_includes_topic_fields_for_forum_chat():
    entity = Channel(chat_id=123, title="Forum Chat", forum=True)
    message = SimpleNamespace(
        id=10,
        date=datetime.now(UTC),
        text="hello",
        message="hello",
        caption=None,
        reply_to_msg_id=51,
        reply_to=SimpleNamespace(reply_to_top_id=51, forum_topic=True),
        media=None,
    )

    with (
        patch(
            "src.utils.message_format.get_sender_info",
            new=AsyncMock(return_value={"id": 1}),
        ),
        patch(
            "src.utils.message_format._extract_forward_info",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await build_message_result(None, message, entity, None)

    assert result["topic_id"] == 51


@pytest.mark.asyncio
async def test_build_message_result_topic_fallback_to_message_reply_to_msg_id():
    entity = Channel(chat_id=123, title="Forum Chat", forum=True)
    message = SimpleNamespace(
        id=12,
        date=datetime.now(UTC),
        text="hello",
        message="hello",
        caption=None,
        reply_to_msg_id=42,
        reply_to=SimpleNamespace(
            reply_to_top_id=None, forum_topic=True, reply_to_msg_id=None
        ),
        media=None,
    )

    with (
        patch(
            "src.utils.message_format.get_sender_info",
            new=AsyncMock(return_value={"id": 1}),
        ),
        patch(
            "src.utils.message_format._extract_forward_info",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await build_message_result(None, message, entity, None)

    assert result["topic_id"] == 42


@pytest.mark.asyncio
async def test_build_message_result_topic_fallback_to_reply_object_reply_to_msg_id():
    entity = Channel(chat_id=123, title="Forum Chat", forum=True)
    message = SimpleNamespace(
        id=13,
        date=datetime.now(UTC),
        text="hello",
        message="hello",
        caption=None,
        reply_to_msg_id=None,
        reply_to=SimpleNamespace(
            reply_to_top_id=None, forum_topic=True, reply_to_msg_id=99
        ),
        media=None,
    )

    with (
        patch(
            "src.utils.message_format.get_sender_info",
            new=AsyncMock(return_value={"id": 1}),
        ),
        patch(
            "src.utils.message_format._extract_forward_info",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await build_message_result(None, message, entity, None)

    assert result["topic_id"] == 99


@pytest.mark.asyncio
async def test_build_message_result_omits_topic_fields_when_forum_topic_has_no_ids():
    entity = Channel(chat_id=123, title="Forum Chat", forum=True)
    message = SimpleNamespace(
        id=14,
        date=datetime.now(UTC),
        text="hello",
        message="hello",
        caption=None,
        reply_to_msg_id=None,
        reply_to=SimpleNamespace(
            reply_to_top_id=None, forum_topic=True, reply_to_msg_id=None
        ),
        media=None,
    )

    with (
        patch(
            "src.utils.message_format.get_sender_info",
            new=AsyncMock(return_value={"id": 1}),
        ),
        patch(
            "src.utils.message_format._extract_forward_info",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await build_message_result(None, message, entity, None)

    assert "topic_id" not in result


@pytest.mark.asyncio
async def test_build_message_result_omits_topic_fields_for_non_forum_chat():
    entity = Channel(chat_id=124, title="Regular Channel", forum=False)
    message = SimpleNamespace(
        id=11,
        date=datetime.now(UTC),
        text="hello",
        message="hello",
        caption=None,
        reply_to_msg_id=51,
        reply_to=SimpleNamespace(reply_to_top_id=None, forum_topic=False),
        media=None,
    )

    with (
        patch(
            "src.utils.message_format.get_sender_info",
            new=AsyncMock(return_value={"id": 1}),
        ),
        patch(
            "src.utils.message_format._extract_forward_info",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await build_message_result(None, message, entity, None)

    assert "topic_id" not in result


@pytest.mark.asyncio
async def test_get_chat_info_returns_topics_for_forum_chat():
    entity = Channel(chat_id=999, title="Forum Chat", forum=True)

    with (
        patch(
            "src.tools.contacts.get_entity_by_id", new=AsyncMock(return_value=entity)
        ),
        patch(
            "src.tools.contacts.build_entity_dict_enriched",
            new=AsyncMock(
                return_value={
                    "id": 999,
                    "title": "Forum Chat",
                    "type": "group",
                    "is_forum": True,
                }
            ),
        ),
        patch(
            "src.tools.contacts._list_forum_topics",
            new=AsyncMock(
                return_value={
                    "topics": [{"topic_id": 7, "title": "Topic 7"}],
                    "has_more": False,
                }
            ),
        ) as topics_mock,
    ):
        result = await get_chat_info_impl("999", topics_limit=5)

    assert result["topics"] == [{"topic_id": 7, "title": "Topic 7"}]
    assert result["topics_has_more"] is False
    topics_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_chat_info_skips_topics_for_non_forum_chat():
    entity = Channel(chat_id=1000, title="Regular", forum=False)

    with (
        patch(
            "src.tools.contacts.get_entity_by_id", new=AsyncMock(return_value=entity)
        ),
        patch(
            "src.tools.contacts.build_entity_dict_enriched",
            new=AsyncMock(
                return_value={"id": 1000, "title": "Regular", "type": "group"}
            ),
        ),
        patch(
            "src.tools.contacts._list_forum_topics",
            new=AsyncMock(side_effect=RuntimeError("must not call")),
        ),
    ):
        result = await get_chat_info_impl("1000", topics_limit=5)

    assert "topics" not in result


@pytest.mark.asyncio
async def test_send_message_or_files_uses_reply_to_target():
    client = AsyncMock()
    client.send_message = AsyncMock(return_value=SimpleNamespace(id=1))
    entity = SimpleNamespace(id=1)

    error, _ = await _send_message_or_files(
        client=client,
        entity=entity,
        message="hello",
        files=None,
        reply_to_msg_id=77,
        parse_mode=None,
        operation="send_message",
        params={},
    )

    assert error is None
    assert client.send_message.await_args.kwargs["reply_to"] == 77


@pytest.mark.asyncio
async def test_send_message_or_files_without_reply_sends_plain_message():
    client = AsyncMock()
    client.send_message = AsyncMock(return_value=SimpleNamespace(id=1))
    entity = SimpleNamespace(id=1)

    error, _ = await _send_message_or_files(
        client=client,
        entity=entity,
        message="hello",
        files=None,
        reply_to_msg_id=None,
        parse_mode=None,
        operation="send_message",
        params={},
    )

    assert error is None
    assert client.send_message.await_args.kwargs["reply_to"] is None


@pytest.mark.asyncio
async def test_edit_message_in_forum_includes_topic_id_only():
    client = AsyncMock()
    chat = SimpleNamespace(
        id=1, title="Forum Chat", forum=True, broadcast=True, megagroup=False
    )

    edited_message = SimpleNamespace(
        id=123,
        date=datetime.now(UTC),
        edit_date=datetime.now(UTC),
        text="updated",
        sender=None,
        reply_to_msg_id=51,
        reply_to=SimpleNamespace(reply_to_top_id=51, forum_topic=True),
    )

    client.edit_message = AsyncMock(return_value=edited_message)

    with (
        patch(
            "src.tools.messages.get_connected_client",
            new=AsyncMock(return_value=client),
        ),
        patch("src.tools.messages.get_entity_by_id", new=AsyncMock(return_value=chat)),
    ):
        result = await edit_message_impl(
            chat_id="-1001",
            message_id=123,
            new_text="updated",
            parse_mode=None,
        )

    assert result["status"] == "edited"
    assert result["topic_id"] == 51
    assert "top_msg_id" not in result
    client.edit_message.assert_awaited_once()


# --- 4b: File-sending branch in _send_message_or_files ---


@pytest.mark.asyncio
async def test_send_message_or_files_files_with_reply_target():
    """files non-empty with reply_to_msg_id -> _send_files_to_entity gets the same reply target."""
    client = AsyncMock()
    entity = SimpleNamespace(id=1)

    with patch(
        "src.tools.messages._validate_file_paths",
        return_value=(["http://example.com/photo.jpg"], None),
    ), patch(
        "src.tools.messages._send_files_to_entity",
        new=AsyncMock(return_value=SimpleNamespace(id=1)),
    ) as send_files_mock:
        error, _ = await _send_message_or_files(
            client=client,
            entity=entity,
            message="hello",
            files=["http://example.com/photo.jpg"],
            reply_to_msg_id=123,
            parse_mode=None,
            operation="send_message",
            params={},
        )

    assert error is None
    send_files_mock.assert_awaited_once()
    assert send_files_mock.await_args[0][4] == 123


@pytest.mark.asyncio
async def test_send_message_or_files_files_without_reply_target():
    """files non-empty without reply target -> _send_files_to_entity gets None reply."""
    client = AsyncMock()
    entity = SimpleNamespace(id=1)

    with patch(
        "src.tools.messages._validate_file_paths",
        return_value=(["http://example.com/photo.jpg"], None),
    ), patch(
        "src.tools.messages._send_files_to_entity",
        new=AsyncMock(return_value=SimpleNamespace(id=1)),
    ) as send_files_mock:
        error, _ = await _send_message_or_files(
            client=client,
            entity=entity,
            message="hello",
            files=["http://example.com/photo.jpg"],
            reply_to_msg_id=None,
            parse_mode=None,
            operation="send_message",
            params={},
        )

    assert error is None
    send_files_mock.assert_awaited_once()
    assert send_files_mock.await_args[0][4] is None


# --- 4c: edit_message_impl edge cases ---


@pytest.mark.asyncio
async def test_edit_message_non_forum_omits_topic_id():
    """forum_topic=False → no topic_id in result."""
    client = AsyncMock()
    chat = SimpleNamespace(
        id=1, title="Regular Chat", forum=False, broadcast=True, megagroup=False
    )

    edited_message = SimpleNamespace(
        id=123,
        date=datetime.now(UTC),
        edit_date=datetime.now(UTC),
        text="updated",
        sender=None,
        reply_to_msg_id=51,
        reply_to=SimpleNamespace(
            reply_to_top_id=None, forum_topic=False, reply_to_msg_id=51
        ),
    )

    client.edit_message = AsyncMock(return_value=edited_message)

    with (
        patch(
            "src.tools.messages.get_connected_client",
            new=AsyncMock(return_value=client),
        ),
        patch("src.tools.messages.get_entity_by_id", new=AsyncMock(return_value=chat)),
    ):
        result = await edit_message_impl(
            chat_id="-1001",
            message_id=123,
            new_text="updated",
            parse_mode=None,
        )

    assert result["status"] == "edited"
    assert "topic_id" not in result


@pytest.mark.asyncio
async def test_edit_message_forum_no_ids_omits_topic_id():
    """forum_topic=True, all ids None → no topic_id."""
    client = AsyncMock()
    chat = SimpleNamespace(
        id=1, title="Forum Chat", forum=True, broadcast=True, megagroup=False
    )

    edited_message = SimpleNamespace(
        id=123,
        date=datetime.now(UTC),
        edit_date=datetime.now(UTC),
        text="updated",
        sender=None,
        reply_to_msg_id=None,
        reply_to=SimpleNamespace(
            reply_to_top_id=None, forum_topic=True, reply_to_msg_id=None
        ),
    )

    client.edit_message = AsyncMock(return_value=edited_message)

    with (
        patch(
            "src.tools.messages.get_connected_client",
            new=AsyncMock(return_value=client),
        ),
        patch("src.tools.messages.get_entity_by_id", new=AsyncMock(return_value=chat)),
    ):
        result = await edit_message_impl(
            chat_id="-1001",
            message_id=123,
            new_text="updated",
            parse_mode=None,
        )

    assert result["status"] == "edited"
    assert "topic_id" not in result


# --- 4d: _list_forum_topics edge cases for has_more ---


@pytest.mark.asyncio
async def test_list_forum_topics_exactly_limit_has_more_false_and_requests_plus_one():
    entity = SimpleNamespace(id=999)
    # API returns exactly 20 topics even though we requested 21.
    topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 21)]
    client = AsyncMock(return_value=SimpleNamespace(topics=topics))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=20)

    request = client.await_args.args[0]
    assert request.limit == 21
    assert len(result["topics"]) == 20
    assert result["has_more"] is False


@pytest.mark.asyncio
async def test_list_forum_topics_limit_plus_one_has_more_true_and_trims_output():
    entity = SimpleNamespace(id=999)
    topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 22)]
    client = AsyncMock(return_value=SimpleNamespace(topics=topics))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=20)

    assert len(result["topics"]) == 20
    assert result["topics"][0]["topic_id"] == 1
    assert result["topics"][-1]["topic_id"] == 20
    assert result["has_more"] is True


@pytest.mark.asyncio
async def test_list_forum_topics_limit_100_probes_next_page_and_sets_has_more_true():
    entity = SimpleNamespace(id=999)
    page_topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 101)]

    client = AsyncMock(
        side_effect=[
            SimpleNamespace(topics=page_topics),
            SimpleNamespace(topics=[SimpleNamespace(id=101, title="Topic 101")]),
        ]
    )

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=100)

    assert len(result["topics"]) == 100
    assert result["has_more"] is True
    assert client.await_count == 2

    first_request = client.await_args_list[0].args[0]
    second_request = client.await_args_list[1].args[0]
    assert first_request.limit == 100
    assert second_request.limit == 1
    assert second_request.offset_topic == 100


@pytest.mark.asyncio
async def test_list_forum_topics_limit_100_probes_next_page_and_sets_has_more_false():
    entity = SimpleNamespace(id=999)
    page_topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 101)]

    client = AsyncMock(
        side_effect=[
            SimpleNamespace(topics=page_topics),
            SimpleNamespace(topics=[]),
        ]
    )

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=100)

    assert len(result["topics"]) == 100
    assert result["has_more"] is False
    assert client.await_count == 2


@pytest.mark.asyncio
async def test_list_forum_topics_handles_invalid_limit_with_default():
    entity = SimpleNamespace(id=999)
    topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 22)]
    client = AsyncMock(return_value=SimpleNamespace(topics=topics))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit="not-a-number")

    request = client.await_args.args[0]
    # Default limit is 20, fetches one extra for has_more detection.
    assert request.limit == 21
    assert len(result["topics"]) == 20
    assert result["has_more"] is True


@pytest.mark.asyncio
async def test_list_forum_topics_limit_is_clamped_to_one_and_hundred():
    entity = SimpleNamespace(id=999)
    client = AsyncMock(return_value=SimpleNamespace(topics=[]))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        await _list_forum_topics(entity, limit=0)
    req_low = client.await_args.args[0]
    assert req_low.limit == 2  # requested_limit=1 -> fetch_limit=2

    client.reset_mock(return_value=True)
    client.return_value = SimpleNamespace(topics=[])
    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        await _list_forum_topics(entity, limit=10_000)
    req_high = client.await_args.args[0]
    assert req_high.limit == 100  # max clamp


@pytest.mark.asyncio
async def test_list_forum_topics_filters_items_missing_id_or_title():
    entity = SimpleNamespace(id=999)
    raw_topics = [
        SimpleNamespace(id=1, title="ok"),
        SimpleNamespace(id=None, title="bad"),
        SimpleNamespace(id=3, title=None),
        SimpleNamespace(id=4, title="ok-2"),
    ]
    client = AsyncMock(return_value=SimpleNamespace(topics=raw_topics))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=20)

    assert result["topics"] == [
        {"topic_id": 1, "title": "ok"},
        {"topic_id": 4, "title": "ok-2"},
    ]


@pytest.mark.asyncio
async def test_get_chat_info_not_found_returns_error_dict():
    with patch(
        "src.tools.contacts.get_entity_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await get_chat_info_impl("404")

    assert "error" in result
    assert "404" in result["error"]


@pytest.mark.asyncio
async def test_get_chat_info_forum_topics_failure_is_non_fatal():
    entity = Channel(chat_id=999, title="Forum Chat", forum=True)

    with (
        patch(
            "src.tools.contacts.get_entity_by_id",
            new=AsyncMock(return_value=entity),
        ),
        patch(
            "src.tools.contacts.build_entity_dict_enriched",
            new=AsyncMock(
                return_value={"id": 999, "title": "Forum Chat", "is_forum": True}
            ),
        ),
        patch(
            "src.tools.contacts._list_forum_topics",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await get_chat_info_impl("999", topics_limit=5)

    assert result["id"] == 999
    assert "topics" not in result
    assert "topics_has_more" not in result


def test_extract_topic_metadata_prefers_reply_to_top_id():
    message = SimpleNamespace(
        reply_to_msg_id=10,
        reply_to=SimpleNamespace(reply_to_top_id=99, reply_to_msg_id=55, forum_topic=True),
    )
    assert _extract_topic_metadata(message) == {"topic_id": 99}


def test_extract_topic_metadata_uses_message_reply_to_msg_id_fallback():
    message = SimpleNamespace(
        reply_to_msg_id=42,
        reply_to=SimpleNamespace(reply_to_top_id=None, reply_to_msg_id=None, forum_topic=True),
    )
    assert _extract_topic_metadata(message) == {"topic_id": 42}


def test_extract_topic_metadata_uses_reply_object_reply_to_msg_id_fallback():
    message = SimpleNamespace(
        reply_to_msg_id=None,
        reply_to=SimpleNamespace(reply_to_top_id=None, reply_to_msg_id=77, forum_topic=True),
    )
    assert _extract_topic_metadata(message) == {"topic_id": 77}


def test_extract_topic_metadata_non_forum_returns_empty_even_with_reply_ids():
    message = SimpleNamespace(
        reply_to_msg_id=55,
        reply_to=SimpleNamespace(reply_to_top_id=None, reply_to_msg_id=55, forum_topic=False),
    )
    assert _extract_topic_metadata(message) == {}


def test_extract_topic_metadata_without_reply_data_returns_empty():
    message = SimpleNamespace(reply_to_msg_id=None, reply_to=None)
    assert _extract_topic_metadata(message) == {}


def test_extract_send_message_params_marks_reply_target_as_reply():
    params = _extract_send_message_params(
        chat_id="-1001",
        message="hello",
        reply_to_msg_id=77,
        parse_mode=None,
        files=None,
    )
    assert params["has_reply"] is True


def test_extract_send_message_params_marks_no_reply_when_no_ids():
    params = _extract_send_message_params(
        chat_id="-1001",
        message="hello",
        reply_to_msg_id=None,
        parse_mode=None,
        files=None,
    )
    assert params["has_reply"] is False


@pytest.mark.asyncio
async def test_list_forum_topics_limit_100_underfilled_page_skips_probe_and_has_more_false():
    entity = SimpleNamespace(id=999)
    # Simulate backend returning less than requested page size.
    topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 100)]
    client = AsyncMock(return_value=SimpleNamespace(topics=topics))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=100)

    assert len(result["topics"]) == 99
    assert result["has_more"] is False
    # Only initial page request should be made (no probe request).
    assert client.await_count == 1


@pytest.mark.asyncio
async def test_list_forum_topics_limit_100_missing_last_topic_id_disables_probe():
    entity = SimpleNamespace(id=999)
    topics = [SimpleNamespace(id=i, title=f"Topic {i}") for i in range(1, 100)]
    topics.append(SimpleNamespace(id=None, title="Broken topic"))
    client = AsyncMock(return_value=SimpleNamespace(topics=topics))

    with patch("src.tools.contacts.get_connected_client", new=AsyncMock(return_value=client)):
        result = await _list_forum_topics(entity, limit=100)

    assert result["has_more"] is False
    # Last topic id is None -> probe cannot run safely.
    assert client.await_count == 1


async def _get_live_forum_entity_or_skip():
    if os.getenv("FAST_MCP_TELEGRAM_LIVE_TESTS") != "1":
        pytest.skip("live integration disabled")

    chat_id = os.getenv("FAST_MCP_TELEGRAM_FORUM_CHAT_ID")
    if not chat_id:
        pytest.skip("FAST_MCP_TELEGRAM_FORUM_CHAT_ID not set")

    from src.tools.contacts import get_entity_by_id

    entity = await get_entity_by_id(chat_id)
    if not entity:
        pytest.skip("forum entity not accessible")

    return entity


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_forum_topics_live_api_shape():
    entity = await _get_live_forum_entity_or_skip()

    result = await _list_forum_topics(entity, limit=5)
    assert isinstance(result, dict)
    assert "topics" in result
    assert "has_more" in result
    assert isinstance(result["topics"], list)
    assert isinstance(result["has_more"], bool)
    for item in result["topics"]:
        assert "topic_id" in item
        assert "title" in item


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_forum_topics_live_limit_20_semantics():
    """Live check: validates basic has_more semantics for limit=20."""
    entity = await _get_live_forum_entity_or_skip()

    result = await _list_forum_topics(entity, limit=20)
    assert len(result["topics"]) <= 20
    assert isinstance(result["has_more"], bool)

    # If API returns fewer than limit topics, has_more should be false.
    if len(result["topics"]) < 20:
        assert result["has_more"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_forum_topics_live_limit_100_semantics():
    """Live check for the boundary limit=100 path (probe-first implementation)."""
    entity = await _get_live_forum_entity_or_skip()

    result = await _list_forum_topics(entity, limit=100)
    assert len(result["topics"]) <= 100
    assert isinstance(result["has_more"], bool)

    # If API returns fewer than limit topics, has_more should be false.
    if len(result["topics"]) < 100:
        assert result["has_more"] is False
