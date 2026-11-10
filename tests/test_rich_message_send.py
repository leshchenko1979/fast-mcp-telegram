"""Tests for parse_mode='rich' dialect detection and TL send/edit routing."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.tl import types

from src.tools.messages.core import detect_message_formatting, detect_rich_dialect
from src.tools.messages.rich_send import (
    _message_from_tl_result,
    build_input_rich_message,
    edit_rich_via_tl,
    send_rich_via_tl,
)
from src.tools.messages.sending import _send_message_or_files
from src.utils.message_format import build_send_edit_result


class TestDetectRichDialect:
    def test_plain_defaults_to_markdown(self):
        assert detect_rich_dialect("hello") == "markdown"
        assert detect_rich_dialect("") == "markdown"

    def test_inequality_stays_markdown(self):
        assert detect_rich_dialect("1 < 2 and 3 > 0") == "markdown"

    def test_tags_in_inline_code_stay_markdown(self):
        assert detect_rich_dialect("use `<b>` for bold") == "markdown"

    def test_tags_in_fenced_code_stay_markdown(self):
        body = "Example:\n```html\n<b>hi</b>\n```\nDone"
        assert detect_rich_dialect(body) == "markdown"

    def test_real_html_outside_code_is_html(self):
        assert detect_rich_dialect("<b>hi</b>") == "html"
        assert detect_rich_dialect("<h2>Title</h2><ul><li>a</li></ul>") == "html"

    def test_markdown_heading_is_markdown(self):
        assert detect_rich_dialect("## Hello\n\n- a\n- b") == "markdown"

    def test_classic_detect_still_flags_inequality_as_html(self):
        # Classic auto unchanged; rich path must not reuse it.
        assert detect_message_formatting("1 < 2 and 3 > 0") == "html"
        assert detect_rich_dialect("1 < 2 and 3 > 0") == "markdown"


class TestBuildInputRichMessage:
    def test_markdown_constructor(self):
        obj = build_input_rich_message("## Hi", "markdown")
        assert isinstance(obj, types.InputRichMessageMarkdown)
        assert obj.markdown == "## Hi"

    def test_html_constructor(self):
        obj = build_input_rich_message("<b>x</b>", "html")
        assert isinstance(obj, types.InputRichMessageHTML)
        assert obj.html == "<b>x</b>"


@pytest.mark.asyncio
async def test_send_rich_via_tl_uses_markdown_and_reply():
    sent = SimpleNamespace(
        id=10,
        date=datetime(2026, 1, 1, tzinfo=UTC),
        message="",
        text="",
        rich_message=SimpleNamespace(blocks=[], photos=[], documents=[]),
        sender=None,
        reply_markup=None,
    )

    class FakeClient:
        def __init__(self):
            self.get_input_entity = AsyncMock(return_value=types.InputPeerSelf())
            self._get_response_message = MagicMock(return_value=sent)
            self.last_req = None

        async def __call__(self, req):
            self.last_req = req
            assert isinstance(req.rich_message, types.InputRichMessageMarkdown)
            assert req.message == ""
            assert isinstance(req.reply_to, types.InputReplyToMessage)
            assert req.reply_to.reply_to_msg_id == 77
            return SimpleNamespace(updates=[])

    client = FakeClient()
    msg, dialect = await send_rich_via_tl(
        client, "me", "## Hello\n- a", reply_to_msg_id=77
    )
    assert msg is sent
    assert dialect == "markdown"
    assert client.last_req is not None


@pytest.mark.asyncio
async def test_send_rich_via_tl_uses_html_for_tags():
    sent = SimpleNamespace(id=11, date=datetime(2026, 1, 1, tzinfo=UTC))

    class FakeClient:
        def __init__(self):
            self.get_input_entity = AsyncMock(return_value=types.InputPeerSelf())
            self._get_response_message = MagicMock(return_value=sent)

        async def __call__(self, req):
            assert isinstance(req.rich_message, types.InputRichMessageHTML)
            return SimpleNamespace(updates=[])

    _, dialect = await send_rich_via_tl(FakeClient(), "me", "<b>hi</b>")
    assert dialect == "html"


@pytest.mark.asyncio
async def test_edit_rich_via_tl_builds_edit_request():
    edited = SimpleNamespace(id=12, date=datetime(2026, 1, 1, tzinfo=UTC))

    class FakeClient:
        def __init__(self):
            self.get_input_entity = AsyncMock(return_value=types.InputPeerSelf())
            self._get_response_message = MagicMock(return_value=edited)

        async def __call__(self, req):
            assert req.id == 12
            assert isinstance(req.rich_message, types.InputRichMessageMarkdown)
            return SimpleNamespace(updates=[])

    msg, dialect = await edit_rich_via_tl(FakeClient(), "me", 12, "## Edited")
    assert msg is edited
    assert dialect == "markdown"


@pytest.mark.asyncio
async def test_send_message_or_files_rejects_rich_with_files():
    client = MagicMock()
    error, msg = await _send_message_or_files(
        client,
        entity=SimpleNamespace(id=1),
        message="## Hi",
        files=["https://example.com/a.png"],
        reply_to_msg_id=None,
        parse_mode="rich",
        operation="send_message",
        params={"chat_id": "me"},
    )
    assert msg is None
    assert error is not None
    assert error.get("ok") is False
    assert "rich" in error.get("error", "").lower()
    client.send_message.assert_not_called()
    client.send_file.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_or_files_rich_sets_params_rich_format():
    client = MagicMock()
    params: dict = {"chat_id": "me"}
    fake_msg = SimpleNamespace(id=1)

    with patch(
        "src.tools.messages.sending.send_rich_via_tl",
        new=AsyncMock(return_value=(fake_msg, "markdown")),
    ) as mock_send:
        error, msg = await _send_message_or_files(
            client,
            entity=SimpleNamespace(id=1),
            message="## Hi",
            files=None,
            reply_to_msg_id=None,
            parse_mode="rich",
            operation="send_message",
            params=params,
        )
    assert error is None
    assert msg is fake_msg
    assert params["rich_format"] == "markdown"
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_message_from_tl_result_refetches_when_primary_extract_fails():
    refetched = SimpleNamespace(id=99, message="", text="")

    class FakeClient:
        def __init__(self):
            self._get_response_message = MagicMock(return_value=None)
            self.get_messages = AsyncMock(return_value=refetched)

    client = FakeClient()
    result = SimpleNamespace(updates=[SimpleNamespace(message=SimpleNamespace(id=99))])
    msg = await _message_from_tl_result(
        client, request=object(), result=result, entity="me"
    )
    assert msg is refetched
    client.get_messages.assert_awaited_once_with("me", ids=99)


@pytest.mark.asyncio
async def test_message_from_tl_result_raises_when_no_message_id():
    class FakeClient:
        def __init__(self):
            self._get_response_message = MagicMock(return_value=None)
            self.get_messages = AsyncMock()

    with pytest.raises(RuntimeError, match="without an extractable message"):
        await _message_from_tl_result(
            FakeClient(),
            request=object(),
            result=SimpleNamespace(updates=[]),
            entity="me",
        )


def test_build_send_edit_result_flattens_rich_and_sets_fields():
    from src.utils.message_format.rich import RichMediaRef

    rich = SimpleNamespace(blocks=[], photos=[], documents=[])
    message = SimpleNamespace(
        id=42,
        date=datetime(2026, 1, 1, tzinfo=UTC),
        message="",
        text="",
        rich_message=rich,
        sender=None,
        reply_markup=None,
        edit_date=None,
    )
    chat = SimpleNamespace(
        id=100,
        title="Test",
        username="t",
        first_name=None,
        last_name=None,
        access_hash=None,
        megagroup=False,
        bot=False,
        forum=False,
    )

    with patch(
        "src.utils.message_format.core.flatten_rich_message",
        return_value=("## Flat", [RichMediaRef("photo", 1, "PageBlockPhoto")]),
    ):
        result = build_send_edit_result(message, chat, "sent", rich_format="markdown")

    assert result["text"] == "## Flat"
    assert result["rich"] is True
    assert result["rich_format"] == "markdown"
    assert result["message_id"] == 42
