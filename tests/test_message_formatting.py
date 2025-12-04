"""
Tests for message formatting detection functionality.
"""

import pytest

from src.tools.messages import detect_message_formatting


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
