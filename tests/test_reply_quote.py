"""Reply-quote extraction (issue #160).

Telegram's "reply with quote" answers a *fragment* of another message. Before
this, ``get_messages`` emitted only ``reply_to_msg_id``, so an agent read the
reply as addressing the whole original message — wrong whenever that message is
a list. These tests pin the quote fields and the "plain replies are unchanged"
contract.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from telethon.tl.types import MessageEntityBold, MessageEntityTextUrl

from src.tools.search.context_enrichment import (
    _lightweight_from_raw,
    _lightweight_from_result,
)
from src.utils.message_format import build_message_result, extract_reply_quote


def _reply_header(**kwargs):
    """A reply header with telethon's defaults, overridden by kwargs."""
    defaults = {
        "quote": False,
        "quote_text": None,
        "quote_offset": None,
        "quote_entities": None,
        "reply_to_msg_id": 1479,
        "forum_topic": False,
        "reply_to_top_id": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _message(reply_to=None, reply_to_msg_id=1479):
    return SimpleNamespace(
        id=1480,
        text="that one is dead",
        message="that one is dead",
        caption=None,
        date=datetime(2026, 10, 19, 12, 0, 0),
        media=None,
        rich_message=None,
        action=None,
        forward=None,
        reply_markup=None,
        reply_to=reply_to,
        reply_to_msg_id=reply_to_msg_id,
    )


class TestExtractReplyQuote:
    def test_no_reply_header(self):
        assert extract_reply_quote(_message(reply_to=None)) is None

    def test_plain_reply_has_no_quote(self):
        """A reply to the whole message carries no quote and stays unchanged."""
        msg = _message(reply_to=_reply_header())
        assert extract_reply_quote(msg) is None

    def test_quoted_fragment(self):
        msg = _message(
            reply_to=_reply_header(quote=True, quote_text="India", quote_offset=17)
        )
        assert extract_reply_quote(msg) == {"text": "India", "offset": 17}

    def test_quote_text_without_offset(self):
        msg = _message(reply_to=_reply_header(quote=True, quote_text="India"))
        assert extract_reply_quote(msg) == {"text": "India"}

    def test_quote_entities_are_serialized(self):
        msg = _message(
            reply_to=_reply_header(
                quote=True,
                quote_text="India is dead",
                quote_offset=0,
                quote_entities=[
                    MessageEntityBold(offset=0, length=5),
                    MessageEntityTextUrl(offset=6, length=2, url="https://example.org"),
                ],
            )
        )
        assert extract_reply_quote(msg) == {
            "text": "India is dead",
            "offset": 0,
            "entities": [
                {"type": "bold", "offset": 0, "length": 5},
                {
                    "type": "text_url",
                    "offset": 6,
                    "length": 2,
                    "url": "https://example.org",
                },
            ],
        }

    def test_quote_flag_without_content_is_omitted(self):
        """`quote` set but no fragment: nothing to report, so no empty dict."""
        msg = _message(reply_to=_reply_header(quote=True))
        assert extract_reply_quote(msg) is None


class TestBuildMessageResult:
    @pytest.mark.asyncio
    async def test_plain_reply_shape_unchanged(self):
        msg = _message(reply_to=_reply_header())
        result = await build_message_result(msg, None, link=None)
        assert result["reply_to_msg_id"] == 1479
        assert "reply_quote" not in result

    @pytest.mark.asyncio
    async def test_quoted_reply_carries_fragment(self):
        msg = _message(
            reply_to=_reply_header(quote=True, quote_text="India", quote_offset=17)
        )
        result = await build_message_result(msg, None, link=None)
        assert result["reply_to_msg_id"] == 1479
        assert result["reply_quote"] == {"text": "India", "offset": 17}


class TestContextCarriesQuote:
    def test_lightweight_from_raw(self):
        msg = _message(
            reply_to=_reply_header(quote=True, quote_text="India", quote_offset=17)
        )
        msg.sender_id = 42
        lightweight = _lightweight_from_raw(msg)
        assert lightweight["reply_quote"] == {"text": "India", "offset": 17}

    def test_lightweight_from_raw_without_quote(self):
        msg = _message(reply_to=_reply_header())
        msg.sender_id = 42
        assert "reply_quote" not in _lightweight_from_raw(msg)

    def test_lightweight_from_result(self):
        result = {
            "id": 1480,
            "date": "2026-10-19T12:00:00+00:00",
            "text": "that one is dead",
            "sender": {"id": 42},
            "reply_quote": {"text": "India", "offset": 17},
        }
        assert _lightweight_from_result(result)["reply_quote"] == {
            "text": "India",
            "offset": 17,
        }

    def test_lightweight_from_result_without_quote(self):
        result = {"id": 1480, "text": "hi", "sender": {"id": 42}}
        assert "reply_quote" not in _lightweight_from_result(result)
