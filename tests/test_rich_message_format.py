"""Tests for Telegram RichMessage flattening and MCP serialization."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.utils.message_format import (
    build_message_result,
    message_has_displayable_content,
)
from src.utils.message_format.attachments import (
    _maybe_set_rich_attachment_download_urls,
    build_rich_attachment_placeholders,
)
from src.utils.message_format.rich import (
    RichMediaRef,
    flatten_rich_message,
)

_ATTACH = "src.utils.message_format.attachments"


class TextPlain:
    def __init__(self, value: str):
        self.text = value


class TextBold:
    def __init__(self, value: str):
        self.text = TextPlain(value)


class PageBlockParagraph:
    def __init__(self, text):
        self.text = text


class PageBlockDetails:
    def __init__(self, title, blocks):
        self.title = title
        self.blocks = blocks


class PageBlockPhoto:
    def __init__(self, photo_id: int):
        self.photo_id = photo_id
        self.caption = None


class PageBlockVideo:
    def __init__(self, video_id: int, caption=None):
        self.video_id = video_id
        self.caption = caption


class PageBlockList:
    def __init__(self, items):
        self.items = items


class PageListItemBlocks:
    def __init__(self, blocks):
        self.blocks = blocks


class PhotoSize:
    def __init__(self, size: int):
        self.size = size


class DocumentAttributeFilename:
    def __init__(self, file_name: str):
        self.file_name = file_name


def _rich_message(blocks, photos=None, documents=None):
    return SimpleNamespace(
        blocks=blocks,
        photos=photos or [],
        documents=documents or [],
    )


def test_message_has_displayable_content_rich_only():
    msg = SimpleNamespace(
        text=None,
        message="",
        caption=None,
        media=None,
        action=None,
        rich_message=_rich_message([PageBlockParagraph(TextPlain("hello"))]),
    )
    assert message_has_displayable_content(msg) is True


def test_flatten_paragraph_and_bold():
    rich = _rich_message(
        [
            PageBlockParagraph(TextBold("Title")),
            PageBlockParagraph(TextPlain("body")),
        ]
    )
    text, refs = flatten_rich_message(rich)
    assert "**Title**" in text
    assert "body" in text
    assert refs == []


def test_flatten_nested_details():
    rich = _rich_message(
        [
            PageBlockDetails(
                TextPlain("Summary"),
                [PageBlockParagraph(TextPlain("inside details"))],
            )
        ]
    )
    text, _ = flatten_rich_message(rich)
    assert "Summary" in text
    assert "inside details" in text


def test_flatten_media_refs_tree_order_deduped():
    photo = SimpleNamespace(id=42, sizes=[])
    doc = SimpleNamespace(
        id=99,
        mime_type="video/mp4",
        size=1000,
        attributes=[],
    )
    rich = _rich_message(
        [
            PageBlockPhoto(42),
            PageBlockPhoto(42),
            PageBlockVideo(99),
        ],
        photos=[photo],
        documents=[doc],
    )
    text, refs = flatten_rich_message(rich)
    assert "[media: photo 42]" in text
    assert "[media: document 99]" in text
    assert len(refs) == 2
    assert refs[0].kind == "photo" and refs[0].media_id == 42
    assert refs[1].kind == "document" and refs[1].media_id == 99


def test_flatten_nested_list_item_blocks():
    rich = _rich_message(
        [
            PageBlockList(
                [
                    PageListItemBlocks(
                        [PageBlockPhoto(77), PageBlockParagraph(TextPlain("nested"))]
                    )
                ]
            )
        ],
        photos=[SimpleNamespace(id=77, sizes=[])],
    )
    text, refs = flatten_rich_message(rich)
    assert "[media: photo 77]" in text
    assert "nested" in text
    assert len(refs) == 1


def test_flatten_media_caption():
    caption = SimpleNamespace(text=TextPlain("photo caption"))
    rich = _rich_message(
        [PageBlockPhoto(5)],
        photos=[SimpleNamespace(id=5, sizes=[])],
    )
    rich.blocks[0].caption = caption
    text, _ = flatten_rich_message(rich)
    assert "photo caption" in text


def test_build_rich_attachment_placeholders():
    photo = SimpleNamespace(id=7, sizes=[PhotoSize(500)])
    doc = SimpleNamespace(
        id=8,
        mime_type="application/pdf",
        size=1200,
        attributes=[DocumentAttributeFilename("spec.pdf")],
    )
    rich = _rich_message([], photos=[photo], documents=[doc])
    refs = [
        RichMediaRef("photo", 7, "PageBlockPhoto"),
        RichMediaRef("document", 8, "PageBlockVideo"),
    ]
    placeholders = build_rich_attachment_placeholders(rich, refs)
    assert len(placeholders) == 2
    assert placeholders[0]["type"] == "photo"
    assert placeholders[0]["rich_media_id"] == 7
    assert placeholders[1]["filename"] == "spec.pdf"
    assert placeholders[1]["rich_kind"] == "document"


@pytest.mark.asyncio
async def test_build_message_result_rich_text_and_flag():
    rich = _rich_message([PageBlockParagraph(TextPlain("Rich body"))])
    message = SimpleNamespace(
        id=12688,
        date=SimpleNamespace(isoformat=lambda: "2026-07-12T00:23:22+00:00"),
        text=None,
        message="",
        caption=None,
        media=None,
        rich_message=rich,
        sender_id=None,
        reply_to=None,
        reply_to_msg_id=None,
        reply_markup=None,
        forward=None,
    )
    result = await build_message_result(
        message, {"id": 1, "type": "group"}, "https://t.me/c/1/12688"
    )
    assert result["rich"] is True
    assert result["text"] == "Rich body"


@pytest.mark.asyncio
async def test_build_message_result_prefers_flatten_over_plain():
    rich = _rich_message([PageBlockParagraph(TextPlain("from rich"))])
    message = SimpleNamespace(
        id=1,
        date=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00+00:00"),
        text="stale plain",
        message="stale plain",
        caption=None,
        media=None,
        rich_message=rich,
        sender_id=None,
        reply_to=None,
        reply_to_msg_id=None,
        reply_markup=None,
        forward=None,
    )
    result = await build_message_result(message, {"id": 1, "type": "group"}, None)
    assert result["text"] == "from rich"


@pytest.mark.asyncio
async def test_rich_attachment_urls_minted(http_no_auth_config):
    from src.config.server_config import set_config

    http_no_auth_config.domain = "files.example.test"
    set_config(http_no_auth_config)
    photo = SimpleNamespace(id=55, sizes=[])
    rich = _rich_message([PageBlockPhoto(55)], photos=[photo])
    refs = [RichMediaRef("photo", 55, "PageBlockPhoto")]
    attachments = build_rich_attachment_placeholders(rich, refs)
    message = SimpleNamespace(id=100)
    with patch(f"{_ATTACH}.mint_attachment_ticket", new_callable=AsyncMock) as mint_m:
        mint_m.return_value = "ticket-uuid"
        await _maybe_set_rich_attachment_download_urls(
            attachments, message, -1003627148483
        )
    assert attachments[0]["attachment_download_url"].startswith(
        "https://files.example.test/v1/attachments/ticket-uuid"
    )
    mint_m.assert_awaited_once()
    kwargs = mint_m.await_args.kwargs
    assert kwargs["rich_kind"] == "photo"
    assert kwargs["rich_media_id"] == 55
