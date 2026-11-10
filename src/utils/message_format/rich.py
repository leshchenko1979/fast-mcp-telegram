"""Flatten Telegram RichMessage (PageBlock tree) for MCP tool responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RichKind = Literal["photo", "document"]

_MAX_DEPTH = 16
_MAX_NODES = 500
_MAX_TEXT_CHARS = 50_000
_MAX_ATTACHMENTS = 50

_HEADING_BLOCKS = frozenset(
    {
        "PageBlockTitle",
        "PageBlockSubtitle",
        "PageBlockHeader",
        "PageBlockSubheader",
        "PageBlockKicker",
    }
)

_TEXT_MARKUP: dict[str, tuple[str, str]] = {
    "TextBold": ("**", "**"),
    "TextItalic": ("_", "_"),
    "TextStrike": ("~~", "~~"),
    "TextFixed": ("`", "`"),
    "TextCode": ("`", "`"),
}


@dataclass(frozen=True)
class RichMediaRef:
    """One media embed referenced from the PageBlock tree."""

    kind: RichKind
    media_id: int
    block_type: str


def tl_class_name(obj: Any) -> str:
    return obj.__class__.__name__ if obj is not None else ""


def rich_media_maps(rich_message: Any) -> tuple[dict[int, Any], dict[int, Any]]:
    def by_id(items: Any) -> dict[int, Any]:
        return {
            getattr(item, "id", None): item
            for item in items or []
            if getattr(item, "id", None) is not None
        }

    return (
        by_id(getattr(rich_message, "photos", [])),
        by_id(getattr(rich_message, "documents", [])),
    )


def resolve_rich_media(rich_message: Any, kind: RichKind, media_id: int) -> Any | None:
    """Return the Photo or Document object for a rich embed id."""
    photos, documents = rich_media_maps(rich_message)
    if kind == "photo":
        return photos.get(media_id)
    return documents.get(media_id)


def _heading_level(block_name: str) -> int:
    if not block_name.startswith("PageBlockHeading"):
        return 2
    try:
        return int(block_name[len("PageBlockHeading") :])
    except ValueError:
        return 2


class _RichFlattener:
    def __init__(self) -> None:
        self._parts: list[str] = []
        self._attachments: list[RichMediaRef] = []
        self._seen: set[tuple[RichKind, int]] = set()
        self._nodes = 0
        self._depth = 0
        self._truncated = False

    def _budget_ok(self) -> bool:
        if self._nodes >= _MAX_NODES:
            self._truncated = True
            return False
        if sum(len(p) for p in self._parts) >= _MAX_TEXT_CHARS:
            self._truncated = True
            return False
        return True

    def _append(self, text: str) -> None:
        if not text or not self._budget_ok():
            return
        remaining = _MAX_TEXT_CHARS - sum(len(p) for p in self._parts)
        if remaining <= 0:
            self._truncated = True
            return
        if len(text) > remaining:
            self._parts.append(text[:remaining])
            self._truncated = True
        else:
            self._parts.append(text)

    def _newline(self) -> None:
        if self._parts and not self._parts[-1].endswith("\n"):
            self._append("\n")

    def _emit_text(self, text_obj: Any, *, prefix: str = "", suffix: str = "") -> None:
        flat = self._flatten_text(text_obj)
        if flat:
            self._append(f"{prefix}{flat}{suffix}")
            self._newline()

    def _emit_caption(self, caption: Any) -> None:
        if caption is None:
            return
        text_obj = getattr(caption, "text", caption)
        self._emit_text(text_obj)

    def _register_media(self, kind: RichKind, media_id: int, block_type: str) -> None:
        if len(self._attachments) >= _MAX_ATTACHMENTS:
            self._truncated = True
            return
        key = (kind, media_id)
        if key not in self._seen:
            self._seen.add(key)
            self._attachments.append(
                RichMediaRef(kind=kind, media_id=media_id, block_type=block_type)
            )
        self._append(f"[media: {kind} {media_id}]")

    def _flatten_text(self, text_obj: Any) -> str:
        if text_obj is None or not self._budget_ok():
            return ""
        self._nodes += 1
        cls = tl_class_name(text_obj)
        if cls in _TEXT_MARKUP:
            inner = self._flatten_text(getattr(text_obj, "text", None))
            if not inner:
                return ""
            open_mark, close_mark = _TEXT_MARKUP[cls]
            return f"{open_mark}{inner}{close_mark}"
        match cls:
            case "TextPlain":
                return getattr(text_obj, "text", "") or ""
            case "TextEmpty":
                return ""
            case "TextUnderline" | "TextMarked":
                return self._flatten_text(getattr(text_obj, "text", None))
            case "TextConcat":
                texts = getattr(text_obj, "texts", []) or []
                return "".join(self._flatten_text(t) for t in texts)
            case "TextUrl":
                inner = self._flatten_text(getattr(text_obj, "text", None))
                url = getattr(text_obj, "url", "") or ""
                return f"[{inner}]({url})" if inner and url else inner or url
            case _:
                if hasattr(text_obj, "text"):
                    return self._flatten_text(getattr(text_obj, "text", None))
                return f"[Unsupported: {cls}]"

    def _flatten_blocks(self, blocks: list[Any]) -> None:
        for block in blocks or []:
            if not self._budget_ok():
                break
            self._flatten_block(block)

    def _flatten_block(self, block: Any) -> None:
        if block is None or not self._budget_ok():
            return
        if self._depth >= _MAX_DEPTH:
            self._truncated = True
            return
        self._nodes += 1
        self._depth += 1
        try:
            cls = tl_class_name(block)
            match cls:
                case "PageBlockParagraph" | "PageBlockFooter":
                    self._emit_text(getattr(block, "text", None))
                case name if (
                    name.startswith("PageBlockHeading") or name in _HEADING_BLOCKS
                ):
                    text = self._flatten_text(getattr(block, "text", None))
                    if text:
                        self._append(f"{'#' * min(_heading_level(name), 6)} {text}")
                        self._newline()
                case "PageBlockPreformatted":
                    text = self._flatten_text(getattr(block, "text", None))
                    if text:
                        self._append(f"```\n{text}\n```")
                        self._newline()
                case "PageBlockDivider":
                    self._append("---")
                    self._newline()
                case "PageBlockList" | "PageBlockOrderedList":
                    for item in getattr(block, "items", []) or []:
                        if nested := getattr(item, "blocks", None):
                            self._flatten_blocks(nested)
                            continue
                        item_text = self._flatten_text(getattr(item, "text", None))
                        if item_text:
                            self._append(f"- {item_text}")
                            self._newline()
                case "PageBlockTable":
                    for row in getattr(block, "rows", []) or []:
                        cells = getattr(row, "cells", []) or []
                        row_texts = [
                            self._flatten_text(getattr(cell, "text", None))
                            for cell in cells
                        ]
                        if any(row_texts):
                            self._append(" | ".join(row_texts))
                            self._newline()
                case "PageBlockDetails":
                    self._emit_text(
                        getattr(block, "title", None), prefix="**", suffix="**"
                    )
                    self._flatten_blocks(getattr(block, "blocks", []) or [])
                case "PageBlockBlockquote" | "PageBlockPullquote":
                    self._emit_text(getattr(block, "text", None), prefix="> ")
                case "PageBlockBlockquoteBlocks":
                    self._flatten_blocks(getattr(block, "blocks", []) or [])
                case "PageBlockPhoto":
                    photo_id = getattr(block, "photo_id", None)
                    if photo_id is not None:
                        self._register_media("photo", int(photo_id), cls)
                    self._emit_caption(getattr(block, "caption", None))
                case "PageBlockVideo" | "PageBlockAudio":
                    media_id = getattr(block, "video_id", None) or getattr(
                        block, "audio_id", None
                    )
                    if media_id is not None:
                        self._register_media("document", int(media_id), cls)
                    self._emit_caption(getattr(block, "caption", None))
                case "PageBlockCollage" | "PageBlockSlideshow":
                    for item in getattr(block, "items", []) or []:
                        self._flatten_block(item)
                    self._emit_caption(getattr(block, "caption", None))
                case "PageBlockCover":
                    cover = getattr(block, "cover", None)
                    if cover is not None:
                        self._flatten_block(cover)
                    self._flatten_blocks(getattr(block, "blocks", []) or [])
                case "PageBlockEmbed":
                    if poster_id := getattr(block, "poster_photo_id", None):
                        self._register_media("photo", int(poster_id), cls)
                    self._emit_text(getattr(block, "caption", None))
                case "PageBlockEmbedPost":
                    if author_photo_id := getattr(block, "author_photo_id", None):
                        self._register_media("photo", int(author_photo_id), cls)
                    self._flatten_blocks(getattr(block, "blocks", []) or [])
                case "PageBlockUnsupported":
                    self._append("[Unsupported: PageBlockUnsupported]")
                    self._newline()
                case _:
                    if nested := getattr(block, "blocks", None):
                        self._flatten_blocks(nested)
                    elif text := getattr(block, "text", None):
                        self._emit_text(text)
                    else:
                        self._append(f"[Unsupported: {cls}]")
                        self._newline()
        finally:
            self._depth -= 1

    def flatten(self, rich_message: Any) -> tuple[str, list[RichMediaRef]]:
        self._flatten_blocks(getattr(rich_message, "blocks", []) or [])
        text = "".join(self._parts).strip()
        if self._truncated and text:
            text = f"{text}\n[... truncated ...]"
        return text, list(self._attachments)


def flatten_rich_message(rich_message: Any) -> tuple[str, list[RichMediaRef]]:
    """Return markdown-ish text and tree-order unique media refs from a RichMessage."""
    if rich_message is None:
        return "", []
    return _RichFlattener().flatten(rich_message)
