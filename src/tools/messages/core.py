"""Core message formatting utilities."""

from __future__ import annotations

import re


def _normalize_parse_mode(parse_mode: str | None) -> str | None:
    """Return parse_mode lowercased if not None, otherwise None. Ensures case-insensitive handling."""
    return parse_mode.lower() if parse_mode is not None else None


def detect_message_formatting(message: str) -> str | None:
    """
    Detect message formatting based on content patterns.

    Returns:
        "html" if HTML tags are detected
        "markdown" if Markdown syntax is detected
        None if no formatting is detected
    """
    if not message or not isinstance(message, str):
        return None

    html_pattern = r"<[^>]+>"
    if re.search(html_pattern, message):
        return "html"

    markdown_patterns = [
        r"```.+?```",
        r"`[^`]+`",
        r"\*\*[^[*].*?\*\*",
        r"\*[^**].*?\*",
        r"_[^_]*?_",
        r"\[.*?\]\(.*?\)",
        r"^#{1,6}\s",
        r"^\d+\.\s",
        r"^\*\s",
        r"^\-\s",
    ]

    return next(
        (
            "markdown"
            for pattern in markdown_patterns
            if re.search(pattern, message, re.MULTILINE)
        ),
        None,
    )
