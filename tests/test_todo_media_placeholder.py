"""Regression: MessageMediaToDo completions must not embed Telethon Peer objects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic_core import to_jsonable_python
from telethon.tl.types import PeerUser

from src.utils.message_format import (
    _fill_todo_media_placeholder,
    _todo_completed_by_to_int,
)


def test_todo_completed_by_peer_user_becomes_int():
    assert _todo_completed_by_to_int(PeerUser(user_id=4242)) == 4242
    assert _todo_completed_by_to_int(99) == 99
    assert _todo_completed_by_to_int(None) is None


def test_fill_todo_media_placeholder_serializes_for_mcp():
    class ListTitle:
        text = "List title"

    class ItemTitle:
        text = "item text"

    class TodoItem:
        id = 1
        title = ItemTitle()

    class TodoList:
        title = ListTitle()
        list: ClassVar = [TodoItem()]

    class Completion:
        id = 1
        completed_by = PeerUser(user_id=12345)
        date = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    class Media:
        completions: ClassVar = [Completion()]

    placeholder: dict = {}
    _fill_todo_media_placeholder(placeholder, Media(), TodoList())

    to_jsonable_python(placeholder)

    assert placeholder["type"] == "todo"
    assert placeholder["items"][0]["completed_by"] == 12345
    assert placeholder["items"][0]["completed"] is True
    assert "T" in placeholder["items"][0]["completed_at"]
