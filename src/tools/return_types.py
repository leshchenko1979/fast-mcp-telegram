"""Typed return types for MCP tool output schemas.

FastMCP auto-generates ``outputSchema`` from return-type annotations.
Using ``TypedDict`` (with ``total=False``) produces specific schemas instead
of the generic ``{"type": "object", "additionalProperties": true}`` that
``dict[str, Any]`` yields.

All fields are optional (``total=False``) because tools may return either a
success payload *or* a standardised error dict (``ok: false, error, ...``).
"""

from __future__ import annotations

from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Shared error fields (mixed into every result type)
# ---------------------------------------------------------------------------


class _ErrorFields(TypedDict, total=False):
    """Standard error envelope — present when ``ok`` is ``False``."""

    ok: bool
    error: str
    operation: str
    code: int
    params: dict[str, Any]
    exception: dict[str, Any]
    action: str
    error_code: str


# ---------------------------------------------------------------------------
# Message search / retrieval  (search_messages_globally, get_messages)
# ---------------------------------------------------------------------------


class SearchResult(_ErrorFields, total=False):
    """Return type for ``search_messages_globally`` and ``get_messages``."""

    messages: list[dict[str, Any]]
    has_more: bool
    total_count: int
    _warning: str


# ---------------------------------------------------------------------------
# Send / edit message  (send_message, edit_message)
# ---------------------------------------------------------------------------


class SendEditResult(_ErrorFields, total=False):
    """Return type for ``send_message`` and ``edit_message``."""

    message_id: int
    date: str
    chat: dict[str, Any]
    text: str
    status: str
    sender: dict[str, Any]
    reply_markup: dict[str, Any]
    edit_date: str
    topic_id: int
    rich: bool
    rich_format: str


# ---------------------------------------------------------------------------
# Find chats
# ---------------------------------------------------------------------------


class FindChatsResult(_ErrorFields, total=False):
    """Return type for ``find_chats``."""

    chats: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Chat info
# ---------------------------------------------------------------------------


class ChatInfoResult(_ErrorFields, total=False):
    """Return type for ``get_chat_info``."""

    id: int
    title: str
    username: str
    first_name: str
    last_name: str
    phone: str
    is_forum: bool
    is_channel: bool
    is_group: bool
    is_user: bool
    is_bot: bool
    participants_count: int
    topics: list[dict[str, Any]]
    topics_has_more: bool
    common_chats: list[dict[str, Any]]
    common_chats_has_more: bool


# ---------------------------------------------------------------------------
# Send to phone
# ---------------------------------------------------------------------------


class SendToPhoneResult(SendEditResult, total=False):
    """Return type for ``send_message_to_phone``."""

    phone_number: str
    contact_was_new: bool
    contact_removed: bool


# ---------------------------------------------------------------------------
# MTProto invoke
# ---------------------------------------------------------------------------


class MtprotoResult(_ErrorFields, total=False):
    """Return type for ``invoke_mtproto``.

    The success payload is a JSON-safe dict whose shape depends on the
    Telegram API method invoked.  Common top-level fields are listed here;
    everything else passes through as-is.
    """

    _: str
    id: int
    date: int
    users: list[dict[str, Any]]
    chats: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    # Wrapper for methods whose RPC result is a bare scalar rather than an
    # object (messages.EditChatAbout returns Bool). FastMCP rejects a non-dict
    # structured_content, so the scalar is carried under this key. Typed Any
    # because the wrapped value may be a bool, int or str.
    result: Any
