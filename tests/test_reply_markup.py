"""
Tests for reply markup extraction functionality.
"""

import pytest
from unittest.mock import MagicMock

from src.utils.message_format import _extract_reply_markup


class TestReplyMarkupExtraction:
    """Test cases for _extract_reply_markup function."""

    def test_no_reply_markup(self):
        """Test that None is returned when message has no reply markup."""
        message = MagicMock()
        message.reply_markup = None

        result = _extract_reply_markup(message)
        assert result is None

    def test_missing_reply_markup_attribute(self):
        """Test that None is returned when message lacks reply_markup attribute."""
        message = MagicMock(spec=[])  # No attributes

        result = _extract_reply_markup(message)
        assert result is None

    def test_reply_keyboard_markup_basic(self):
        """Test extraction of basic reply keyboard markup."""
        # Create mock keyboard markup
        keyboard_markup = MagicMock()
        keyboard_markup.__class__.__name__ = "ReplyKeyboardMarkup"
        keyboard_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Button 1"),
                MagicMock(text="Button 2")
            ]),
            MagicMock(buttons=[
                MagicMock(text="Button 3")
            ])
        ]
        keyboard_markup.resize = True
        keyboard_markup.single_use = False
        keyboard_markup.selective = None
        keyboard_markup.persistent = True
        keyboard_markup.placeholder = "Choose an option"

        message = MagicMock()
        message.reply_markup = keyboard_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "keyboard",
            "rows": [
                [{"text": "Button 1"}, {"text": "Button 2"}],
                [{"text": "Button 3"}]
            ],
            "resize": True,
            "single_use": False,
            "selective": None,
            "persistent": True,
            "placeholder": "Choose an option"
        }

        assert result == expected

    def test_reply_keyboard_markup_missing_attributes(self):
        """Test keyboard markup with missing optional attributes."""
        keyboard_markup = MagicMock()
        keyboard_markup.__class__.__name__ = "ReplyKeyboardMarkup"
        keyboard_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="OK")
            ])
        ]
        # Missing optional attributes
        del keyboard_markup.resize
        del keyboard_markup.single_use
        del keyboard_markup.selective
        del keyboard_markup.persistent
        del keyboard_markup.placeholder

        message = MagicMock()
        message.reply_markup = keyboard_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "keyboard",
            "rows": [
                [{"text": "OK"}]
            ],
            "resize": None,
            "single_use": None,
            "selective": None,
            "persistent": None,
            "placeholder": None
        }

        assert result == expected

    def test_reply_inline_markup_url_button(self):
        """Test extraction of inline markup with URL buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Visit Site", url="https://example.com")
            ])
        ]

        # Mock button class name
        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonUrl"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Visit Site",
                    "type": "url",
                    "url": "https://example.com"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_callback_button(self):
        """Test extraction of inline markup with callback buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Click Me", data=b"callback_data")
            ])
        ]

        # Mock button class name
        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonCallback"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Click Me",
                    "type": "callback_data",
                    "data": "callback_data"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_callback_button_bytes_decode(self):
        """Test callback button data decoding with UTF-8 bytes."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Emoji", data="🚀test".encode('utf-8'))
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonCallback"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Emoji",
                    "type": "callback_data",
                    "data": "🚀test"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_switch_inline_query(self):
        """Test extraction of switch inline query buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Search", query="search term")
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonSwitchInline"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Search",
                    "type": "switch_inline_query",
                    "query": "search term"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_switch_inline_current_chat(self):
        """Test extraction of switch inline query current chat buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Search Here", query="local search")
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonSwitchInlineSame"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Search Here",
                    "type": "switch_inline_query_current_chat",
                    "query": "local search"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_game_button(self):
        """Test extraction of game callback buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Play Game")
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonGame"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Play Game",
                    "type": "callback_game"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_pay_button(self):
        """Test extraction of payment buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Pay Now")
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonBuy"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Pay Now",
                    "type": "pay"
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_user_profile_button(self):
        """Test extraction of user profile buttons."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="View Profile", user_id=12345)
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "KeyboardButtonUserProfile"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "View Profile",
                    "type": "user_profile",
                    "user_id": 12345
                }]
            ]
        }

        assert result == expected

    def test_reply_inline_markup_unknown_button_type(self):
        """Test extraction of unknown inline button types."""
        inline_markup = MagicMock()
        inline_markup.__class__.__name__ = "ReplyInlineMarkup"
        inline_markup.rows = [
            MagicMock(buttons=[
                MagicMock(text="Unknown Button")
            ])
        ]

        inline_markup.rows[0].buttons[0].__class__.__name__ = "UnknownButtonType"

        message = MagicMock()
        message.reply_markup = inline_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "inline",
            "rows": [
                [{
                    "text": "Unknown Button",
                    "type": "unknown"
                }]
            ]
        }

        assert result == expected

    def test_reply_keyboard_force_reply(self):
        """Test extraction of force reply markup."""
        force_reply_markup = MagicMock()
        force_reply_markup.__class__.__name__ = "ReplyKeyboardForceReply"
        force_reply_markup.selective = True
        force_reply_markup.placeholder = "Type your reply"

        message = MagicMock()
        message.reply_markup = force_reply_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "force_reply",
            "selective": True,
            "placeholder": "Type your reply"
        }

        assert result == expected

    def test_reply_keyboard_hide(self):
        """Test extraction of keyboard hide markup."""
        hide_markup = MagicMock()
        hide_markup.__class__.__name__ = "ReplyKeyboardHide"
        hide_markup.selective = False

        message = MagicMock()
        message.reply_markup = hide_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "hide",
            "selective": False
        }

        assert result == expected

    def test_unknown_markup_type(self):
        """Test extraction of unknown markup types."""
        unknown_markup = MagicMock()
        unknown_markup.__class__.__name__ = "UnknownMarkupType"

        message = MagicMock()
        message.reply_markup = unknown_markup

        result = _extract_reply_markup(message)

        expected = {
            "type": "unknown",
            "class": "UnknownMarkupType"
        }

        assert result == expected

    def test_missing_rows_attribute(self):
        """Test handling of markup without rows attribute."""
        keyboard_markup = MagicMock()
        keyboard_markup.__class__.__name__ = "ReplyKeyboardMarkup"
        # Missing rows attribute
        del keyboard_markup.rows

        message = MagicMock()
        message.reply_markup = keyboard_markup

        result = _extract_reply_markup(message)

        # Should not crash, rows should be empty list
        assert result["type"] == "keyboard"
        assert result["rows"] == []

    def test_missing_buttons_attribute(self):
        """Test handling of row without buttons attribute."""
        keyboard_markup = MagicMock()
        keyboard_markup.__class__.__name__ = "ReplyKeyboardMarkup"
        keyboard_markup.rows = [
            MagicMock()  # Missing buttons attribute
        ]

        message = MagicMock()
        message.reply_markup = keyboard_markup

        result = _extract_reply_markup(message)

        # Should not crash, row should be empty list
        assert result["type"] == "keyboard"
        assert result["rows"] == [[]]

    def test_missing_button_text(self):
        """Test handling of buttons without text attribute."""
        # Create a button mock that doesn't have a text attribute
        button_mock = MagicMock(spec=[])  # No attributes allowed

        keyboard_markup = MagicMock()
        keyboard_markup.__class__.__name__ = "ReplyKeyboardMarkup"
        keyboard_markup.rows = [
            MagicMock(buttons=[button_mock])
        ]

        message = MagicMock()
        message.reply_markup = keyboard_markup

        result = _extract_reply_markup(message)

        # Should use empty string as default
        assert result["type"] == "keyboard"
        assert result["rows"] == [[{"text": ""}]]