"""
Tests for message formatting detection functionality.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.tools.messages import (
    detect_message_formatting,
    edit_message_impl,
    send_message_impl,
    send_message_to_phone_impl,
)


class TestMessageFormattingDetection:
    """Test cases for detect_message_formatting function."""

    def test_plain_text_detection(self):
        """Test that plain text returns None."""
        test_cases = [
            "",
            "   ",
            "Hello world",
            "123456",
            "Plain text without formatting",
            "Text with punctuation!@#$%^&*()",
        ]

        for text in test_cases:
            assert detect_message_formatting(text) is None, (
                f"Expected None for: {text!r}"
            )

    def test_html_detection(self):
        """Test that HTML tags are detected and take precedence."""
        test_cases = [
            ("<b>Bold</b>", "html"),
            ("<i>Italic</i>", "html"),
            ("<code>Code</code>", "html"),
            ('<a href="url">Link</a>', "html"),
            ("<strong>Bold</strong>", "html"),
            ("<em>Emphasis</em>", "html"),
            ("<p>Paragraph</p>", "html"),
            ("<b>Bold</b> and <i>italic</i>", "html"),
            ('<div class="test">Content</div>', "html"),
            ("<notatag>", "html"),  # Invalid HTML but still matches pattern
        ]

        for text, expected in test_cases:
            result = detect_message_formatting(text)
            assert result == expected, (
                f"Expected {expected} for: {text!r}, got {result}"
            )

    def test_markdown_detection(self):
        """Test that Markdown syntax is detected."""
        test_cases = [
            ("`code`", "markdown"),
            ("```code block```", "markdown"),
            ("**bold**", "markdown"),
            ("*italic*", "markdown"),
            ("_italic_", "markdown"),
            ("[Link](url)", "markdown"),
            ("# Header", "markdown"),
            ("## Header 2", "markdown"),
            ("### Header 3", "markdown"),
            ("1. List item", "markdown"),
            ("* Bullet point", "markdown"),
            ("- Bullet point", "markdown"),
            ("**Bold** and *italic*", "markdown"),
            ("`code` and **bold**", "markdown"),
        ]

        for text, expected in test_cases:
            result = detect_message_formatting(text)
            assert result == expected, (
                f"Expected {expected} for: {text!r}, got {result}"
            )

    def test_html_precedence_over_markdown(self):
        """Test that HTML takes precedence over Markdown when both are present."""
        test_cases = [
            "<b>**bold**</b>",
            "**<b>bold</b>**",
            "<i>*italic*</i>",
            "<code>`code`</code>",
            "<b>**bold**</b> and <i>*italic*</i>",
        ]

        for text in test_cases:
            result = detect_message_formatting(text)
            assert result == "html", (
                f"Expected 'html' precedence for: {text!r}, got {result}"
            )

    def test_incomplete_markdown_not_detected(self):
        """Test that incomplete Markdown patterns are not detected."""
        test_cases = [
            "*",  # Single asterisk
            "**",  # Just bold markers
            "**incomplete",  # Missing closing markers
            "`",  # Single backtick
            "`incomplete",  # Missing closing backtick
            "[",  # Incomplete link
            "#",  # Just hash without space
            "1.",  # Numbered list without space
            "*",  # Just asterisk without space
            "-",  # Just dash without space
        ]

        for text in test_cases:
            result = detect_message_formatting(text)
            assert result is None, (
                f"Expected None for incomplete markdown: {text!r}, got {result}"
            )

    def test_edge_cases(self):
        """Test edge cases and special scenarios."""
        # Empty and None inputs
        assert detect_message_formatting("") is None
        assert detect_message_formatting("   ") is None

        # Numbers and special characters
        assert detect_message_formatting("123") is None
        assert detect_message_formatting("!@#$%^&*()") is None

        # Mixed content without clear formatting
        assert detect_message_formatting("Text with * but no closing") is None
        assert detect_message_formatting("Text with < but no closing") is None

    def test_multiline_content(self):
        """Test multiline content detection."""
        multiline_markdown = """# Header
This is a **bold** paragraph.

* List item 1
* List item 2

```python
code block
```"""

        assert detect_message_formatting(multiline_markdown) == "markdown"

        multiline_html = """<div>
<p>This is <b>bold</b> text.</p>
<ul>
<li>Item 1</li>
<li>Item 2</li>
</ul>
</div>"""

        assert detect_message_formatting(multiline_html) == "html"

    @pytest.mark.parametrize(
        "text,expected",
        [
            # Plain text
            ("Hello world", None),
            ("", None),
            # HTML
            ("<b>Bold</b>", "html"),
            ("<i>Italic</i>", "html"),
            # Markdown
            ("**bold**", "markdown"),
            ("*italic*", "markdown"),
            ("`code`", "markdown"),
            ("# Header", "markdown"),
            ("1. List", "markdown"),
            ("* Bullet", "markdown"),
            # HTML precedence
            ("<b>**bold**</b>", "html"),
        ],
    )
    def test_parametrized_detection(self, text, expected):
        """Parametrized test for various detection scenarios."""
        assert detect_message_formatting(text) == expected


class TestParseModeAutodetectionIntegration:
    """Integration tests for parse mode processing in send/edit message flows."""

    @pytest.mark.asyncio
    async def test_send_message_impl_parse_mode_none_uses_no_autodetection(self):
        """parse_mode=None skips autodetection and passes None through."""
        chat = SimpleNamespace(id=123456, broadcast=False, megagroup=False)
        sent_msg = SimpleNamespace(id=1, text="hello", date=datetime.now())

        with (
            patch(
                "src.tools.messages.get_connected_client",
                new_callable=AsyncMock,
            ),
            patch(
                "src.tools.messages.get_entity_by_id",
                new_callable=AsyncMock,
                return_value=chat,
            ),
            patch(
                "src.tools.messages.get_post_discussion_info",
                new_callable=AsyncMock,
            ),
            patch(
                "src.tools.messages.detect_message_formatting",
            ) as mock_detect,
            patch(
                "src.tools.messages._send_message_or_files",
                new_callable=AsyncMock,
                return_value=(None, sent_msg),
            ) as mock_send,
        ):
            await send_message_impl(
                chat_id="123456",
                message="<b>Bold</b>",
                parse_mode=None,
            )

        mock_detect.assert_not_called()
        mock_send.assert_awaited_once()
        _, _, _, _, _, resolved_parse_mode, _, _ = mock_send.await_args[0]
        assert resolved_parse_mode is None

    @pytest.mark.asyncio
    async def test_edit_message_impl_parse_mode_none_uses_no_autodetection(self):
        """parse_mode=None skips autodetection and passes None through."""
        chat = SimpleNamespace(id=123456, broadcast=False, megagroup=False)
        edited_msg = SimpleNamespace(id=1, text="<b>Bold</b>", date=datetime.now())

        client = AsyncMock()
        client.edit_message = AsyncMock(return_value=edited_msg)

        with (
            patch(
                "src.tools.messages.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.get_entity_by_id",
                new=AsyncMock(return_value=chat),
            ),
            patch(
                "src.tools.messages.detect_message_formatting",
            ) as mock_detect,
        ):
            await edit_message_impl(
                chat_id="123456",
                message_id=1,
                new_text="<b>Bold</b>",
                parse_mode=None,
            )

        mock_detect.assert_not_called()
        client.edit_message.assert_awaited_once()
        assert client.edit_message.await_args[1]["parse_mode"] is None

    @pytest.mark.asyncio
    async def test_send_message_to_phone_impl_parse_mode_none_uses_no_autodetection(
        self,
    ):
        """parse_mode=None skips autodetection and passes None through."""
        user = SimpleNamespace(id=999, first_name="Test")
        sent_msg = SimpleNamespace(id=1, text="<b>Bold</b>", date=datetime.now())

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=user)

        with (
            patch(
                "src.tools.messages.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.detect_message_formatting",
            ) as mock_detect,
            patch(
                "src.tools.messages._send_message_or_files",
                new_callable=AsyncMock,
                return_value=(None, sent_msg),
            ) as mock_send,
        ):
            await send_message_to_phone_impl(
                phone_number="+1234567890",
                message="<b>Bold</b>",
                parse_mode=None,
            )

        mock_detect.assert_not_called()
        mock_send.assert_awaited_once()
        _, _, _, _, _, resolved_parse_mode, _, _ = mock_send.await_args[0]
        assert resolved_parse_mode is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "parse_mode_input,message,expected_resolved",
        [
            ("auto", "<b>Bold</b>", "html"),
            ("AUTO", "<b>Bold</b>", "html"),
            ("Auto", "<b>Bold</b>", "html"),
            ("auto", "**bold**", "markdown"),
            ("AUTO", "**bold**", "markdown"),
            ("auto", "Plain text", None),
            ("auto", "", None),
            ("HTML", "<b>Bold</b>", "html"),
            ("html", "<b>Bold</b>", "html"),
            ("MARKDOWN", "**bold**", "markdown"),
            ("markdown", "**bold**", "markdown"),
        ],
    )
    async def test_send_message_impl_parse_mode_resolution(
        self, parse_mode_input, message, expected_resolved
    ):
        """send_message_impl resolves and lowercases parse_mode correctly."""
        chat = SimpleNamespace(id=123456, broadcast=False, megagroup=False)
        sent_msg = SimpleNamespace(id=1, text=message, date=datetime.now())

        with (
            patch(
                "src.tools.messages.get_connected_client",
                new_callable=AsyncMock,
            ),
            patch(
                "src.tools.messages.get_entity_by_id",
                new_callable=AsyncMock,
                return_value=chat,
            ),
            patch(
                "src.tools.messages.get_post_discussion_info",
                new_callable=AsyncMock,
            ),
            patch(
                "src.tools.messages._send_message_or_files",
                new_callable=AsyncMock,
                return_value=(None, sent_msg),
            ) as mock_send,
        ):
            await send_message_impl(
                chat_id="123456",
                message=message,
                parse_mode=parse_mode_input,
            )

        mock_send.assert_awaited_once()
        _, _, _, _, _, resolved_parse_mode, _, _ = mock_send.await_args[0]
        assert resolved_parse_mode == expected_resolved, (
            f"parse_mode={parse_mode_input!r}, message={message!r} -> "
            f"expected {expected_resolved!r}, got {resolved_parse_mode!r}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "parse_mode_input,new_text,expected_resolved",
        [
            ("auto", "<i>Italic</i>", "html"),
            ("AUTO", "# Header", "markdown"),
            ("auto", "Plain", None),
            ("HTML", "<b>Bold</b>", "html"),
            ("MARKDOWN", "`code`", "markdown"),
        ],
    )
    async def test_edit_message_impl_parse_mode_resolution(
        self, parse_mode_input, new_text, expected_resolved
    ):
        """edit_message_impl resolves and lowercases parse_mode correctly."""
        chat = SimpleNamespace(id=123456, broadcast=False, megagroup=False)
        edited_msg = SimpleNamespace(id=1, text=new_text, date=datetime.now())

        client = AsyncMock()
        client.edit_message = AsyncMock(return_value=edited_msg)

        with (
            patch(
                "src.tools.messages.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages.get_entity_by_id",
                new=AsyncMock(return_value=chat),
            ),
        ):
            result = await edit_message_impl(
                chat_id="123456",
                message_id=1,
                new_text=new_text,
                parse_mode=parse_mode_input,
            )

        assert result["status"] == "edited"
        client.edit_message.assert_awaited_once()
        call_kwargs = client.edit_message.await_args[1]
        assert call_kwargs["parse_mode"] == expected_resolved

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "parse_mode_input,message,expected_resolved",
        [
            ("AUTO", "<b>Bold</b>", "html"),
            ("auto", "<b>Bold</b>", "html"),
            ("Auto", "<b>Bold</b>", "html"),
            ("AUTO", "**bold**", "markdown"),
            ("auto", "**bold**", "markdown"),
            ("AUTO", "just plain text", None),
            ("HTML", "<b>Bold</b>", "html"),
            ("html", "<b>Bold</b>", "html"),
            ("MARKDOWN", "**bold**", "markdown"),
            ("markdown", "**bold**", "markdown"),
        ],
    )
    async def test_send_message_to_phone_impl_parse_mode_resolution(
        self, parse_mode_input, message, expected_resolved
    ):
        """send_message_to_phone_impl normalizes and resolves parse_mode for phone messages."""
        user = SimpleNamespace(id=999, first_name="Test")
        sent_msg = SimpleNamespace(id=1, text=message, date=datetime.now())

        client = AsyncMock()
        client.get_entity = AsyncMock(return_value=user)

        with (
            patch(
                "src.tools.messages.get_connected_client",
                new=AsyncMock(return_value=client),
            ),
            patch(
                "src.tools.messages._send_message_or_files",
                new_callable=AsyncMock,
                return_value=(None, sent_msg),
            ) as mock_send,
        ):
            result = await send_message_to_phone_impl(
                phone_number="+1234567890",
                message=message,
                parse_mode=parse_mode_input,
            )

        mock_send.assert_awaited_once()
        _, _, _, _, _, resolved_parse_mode, _, _ = mock_send.await_args[0]
        assert resolved_parse_mode == expected_resolved, (
            f"parse_mode={parse_mode_input!r}, message={message!r} -> "
            f"expected {expected_resolved!r}, got {resolved_parse_mode!r}"
        )
        assert result["status"] == "sent"
