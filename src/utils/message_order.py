"""Ascending date-time ordering for message payloads returned by tools.

Owner order (2026-10-01): every message list a tool returns is ordered by
ascending date-time.

Ordering is a *presentation* concern only. Callers truncate to the newest N
messages before this module runs, so the payload stays "the newest N messages,
presented oldest-first" and ``has_more`` keeps its meaning.

The ``date`` field written by the formatter is an ISO-8601 string in UTC with a
fixed ``+00:00`` offset (``src/utils/message_format/core.py``), so lexicographic
comparison is chronological: the offset never varies and the fraction is absent
or ``.ffffff``, where ``'+' < '.'`` keeps whole seconds ahead of the same second
with microseconds — the correct order.
"""

from __future__ import annotations

from typing import Any

# Nested lists inside a result's ``context`` envelope that also hold messages.
CONTEXT_MESSAGE_KEYS: tuple[str, ...] = ("before", "after", "replies")

def message_sort_key(message: Any) -> tuple[bool, str]:
    """Return a sort key ordering dated messages first, undated ones last.

    Entries without a usable ``date`` — ``message_ids`` stubs for missing or
    deleted messages carry none — share one key, so the stable sort keeps them
    in the order they arrived. Anything that is not a message dict sorts with
    them rather than raising at a tool boundary.
    """
    if not isinstance(message, dict):
        return (True, "")
    date = message.get("date")
    if isinstance(date, str) and date:
        return (False, date)
    return (True, "")

def sort_messages_ascending(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return ``messages`` ordered by ascending date-time.

    The sort is stable, so messages sharing a date keep their existing order.
    """
    return sorted(messages, key=message_sort_key)

def _sort_context_lists(message: Any) -> None:
    """Order a result's nested context lists in place.

    ``context.before`` is built most-recent-first and ``context.replies``
    inherits Telethon's newest-first order, so both need the same treatment as
    the top-level list.
    """
    if not isinstance(message, dict):
        return
    context = message.get("context")
    if not isinstance(context, dict):
        return
    for key in CONTEXT_MESSAGE_KEYS:
        value = context.get(key)
        if isinstance(value, list):
            context[key] = sort_messages_ascending(value)

def apply_ascending_message_order(result: dict[str, Any]) -> dict[str, Any]:
    """Order every message list in a tool result by ascending date-time.

    Covers the top-level ``messages`` list and each result's nested
    ``context.before`` / ``context.after`` / ``context.replies`` lists.

    Applied at the shared output boundary, after the newest-N window has been
    selected, so which messages a call returns never changes — only their
    order. Payloads without a ``messages`` list (error envelopes) pass through
    untouched.
    """
    messages = result.get("messages")
    if not isinstance(messages, list):
        return result
    ordered = sort_messages_ascending(messages)
    for message in ordered:
        _sort_context_lists(message)
    result["messages"] = ordered
    return result
