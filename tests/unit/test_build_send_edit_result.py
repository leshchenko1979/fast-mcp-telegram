"""Tests for build_send_edit_result — null sender/chat handling.

Regression: FastMCP output validation rejects ``None`` values for fields
typed as ``dict[str, Any]`` in ``SendEditResult`` (``"None is not of type 'object'"``).
The fix: omit ``sender``/``chat`` from the result dict when ``build_entity_dict``
returns ``None``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from src.utils.message_format import build_send_edit_result


def _make_message(**overrides):
    """Build a minimal Telethon-like message stub."""
    defaults = {
        "id": 12345,
        "date": datetime(2026, 6, 19, 20, 0, 0, tzinfo=timezone.utc),
        "text": "hello",
        "sender": SimpleNamespace(id=1, first_name="Alice"),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_chat(**overrides):
    """Build a minimal Telethon-like chat entity stub."""
    defaults = {
        "id": 100,
        "title": "Test Chat",
        "username": "testchat",
        "first_name": None,
        "last_name": None,
        "phone": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestBuildSendEditResultNormal:
    """Normal case: both chat and sender resolve to entity dicts."""

    def test_result_includes_chat_and_sender(self):
        message = _make_message()
        chat = _make_chat()

        result = build_send_edit_result(message, chat, "sent")

        assert result["message_id"] == 12345
        assert result["text"] == "hello"
        assert result["status"] == "sent"
        assert "chat" in result
        assert isinstance(result["chat"], dict)
        assert "sender" in result
        assert isinstance(result["sender"], dict)


class TestBuildSendEditResultNullSender:
    """Regression: sender is None when message.sender is not populated."""

    def test_null_sender_excluded_from_result(self):
        message = _make_message(sender=None)
        chat = _make_chat()

        result = build_send_edit_result(message, chat, "sent")

        assert "sender" not in result, (
            "sender=None must be excluded — FastMCP rejects null for dict type"
        )
        assert "chat" in result
        assert isinstance(result["chat"], dict)

    @patch("src.utils.message_format.build_entity_dict")
    def test_null_sender_from_build_entity_dict(self, mock_build):
        """build_entity_dict returns None for a valid-but-unresolvable sender."""
        # First call (chat) returns a dict, second call (sender) returns None
        mock_build.side_effect = [
            {"id": 100, "title": "Test", "type": "group"},
            None,
        ]
        message = _make_message()
        chat = _make_chat()

        result = build_send_edit_result(message, chat, "sent")

        assert "sender" not in result
        assert "chat" in result


class TestBuildSendEditResultNullChat:
    """Edge case: chat entity is None (shouldn't happen in practice but defensive)."""

    @patch("src.utils.message_format.build_entity_dict")
    def test_null_chat_excluded_from_result(self, mock_build):
        # First call (chat) returns None, second call (sender) returns dict
        mock_build.side_effect = [
            None,
            {"id": 1, "first_name": "Alice", "type": "private"},
        ]
        message = _make_message()
        chat = _make_chat()

        result = build_send_edit_result(message, chat, "sent")

        assert "chat" not in result
        assert "sender" in result


class TestBuildSendEditResultBothNull:
    """Both sender and chat are None — result must still be a valid dict."""

    @patch("src.utils.message_format.build_entity_dict")
    def test_both_null_result_still_valid(self, mock_build):
        mock_build.return_value = None
        message = _make_message(sender=None)
        chat = _make_chat()

        result = build_send_edit_result(message, chat, "sent")

        assert isinstance(result, dict)
        assert "chat" not in result
        assert "sender" not in result
        assert result["message_id"] == 12345
        assert result["status"] == "sent"


class TestBuildSendEditResultEdited:
    """Edited message includes edit_date."""

    def test_edit_date_present(self):
        message = _make_message(edit_date=datetime(2026, 6, 19, 21, 0, 0, tzinfo=timezone.utc))
        chat = _make_chat()

        result = build_send_edit_result(message, chat, "edited")

        assert result["status"] == "edited"
        assert "edit_date" in result
