"""Unit tests for ascending date-time ordering of message payloads."""

from __future__ import annotations

from src.utils.message_order import message_sort_key, sort_messages_ascending


def _msg(msg_id: int, date: str | None) -> dict:
    message = {"id": msg_id}
    if date is not None:
        message["date"] = date
    return message

def test_sorts_iso_dates_ascending():
    messages = [
        _msg(3, "2025-01-01T00:00:00+00:00"),
        _msg(1, "2023-01-01T00:00:00+00:00"),
        _msg(2, "2024-06-15T12:30:00+00:00"),
    ]

    assert [m["id"] for m in sort_messages_ascending(messages)] == [1, 2, 3]

def test_undated_entries_land_last_in_stable_order():
    messages = [
        _msg(10, None),
        _msg(2, "2024-06-15T12:30:00+00:00"),
        _msg(11, None),
        _msg(1, "2023-01-01T00:00:00+00:00"),
        {"id": 12},  # missing date key entirely, as message_ids stubs are
    ]

    assert [m["id"] for m in sort_messages_ascending(messages)] == [1, 2, 10, 11, 12]

def test_equal_dates_keep_original_order():
    same = "2024-06-15T12:30:00+00:00"
    messages = [_msg(7, same), _msg(8, same), _msg(9, same)]

    assert [m["id"] for m in sort_messages_ascending(messages)] == [7, 8, 9]

def test_whole_second_sorts_before_same_second_with_microseconds():
    messages = [
        _msg(2, "2024-06-15T12:30:00.500000+00:00"),
        _msg(1, "2024-06-15T12:30:00+00:00"),
    ]

    assert [m["id"] for m in sort_messages_ascending(messages)] == [1, 2]

def test_empty_and_blank_dates():
    assert sort_messages_ascending([]) == []
    assert message_sort_key(_msg(1, "")) == (True, "")
    assert message_sort_key(_msg(1, "2024-06-15T12:30:00+00:00")) == (
        False,
        "2024-06-15T12:30:00+00:00",
    )

def test_does_not_mutate_input_order_contract():
    """The helper returns a new list; callers rely on the original staying put."""
    messages = [_msg(2, "2024-06-15T12:30:00+00:00"), _msg(1, "2023-01-01T00:00:00+00:00")]
    ordered = sort_messages_ascending(messages)

    assert [m["id"] for m in ordered] == [1, 2]
    assert [m["id"] for m in messages] == [2, 1]
