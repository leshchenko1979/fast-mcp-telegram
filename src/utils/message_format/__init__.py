"""Format Telethon messages for MCP tool responses."""

from __future__ import annotations

from .attachments import (
    _maybe_set_attachment_download_url,
    _maybe_set_rich_attachment_download_urls,
    response_attachment_warning,
)
from .core import (
    build_message_result,
    build_send_edit_result,
    extract_reply_quote,
    extract_topic_metadata,
    get_sender_info,
    message_has_displayable_content,
)
from .rich import flatten_rich_message
from .transcription import PremiumRequiredError, transcribe_voice_messages

__all__ = [
    "PremiumRequiredError",
    "build_message_result",
    "build_send_edit_result",
    "extract_reply_quote",
    "extract_topic_metadata",
    "flatten_rich_message",
    "get_sender_info",
    "message_has_displayable_content",
    "response_attachment_warning",
    "transcribe_voice_messages",
]
