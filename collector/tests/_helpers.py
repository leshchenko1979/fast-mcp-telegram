"""Test helper functions shared across the collector test suite."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def make_nested_payload(**overrides) -> dict:
    """Build a payload that mirrors ``src.telemetry.gather_payload()`` output.

    Returns a dict that passes the collector's ``TelemetryPayload``
    validation. Tests can override any field via keyword args.
    """
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "v": 1,
        "iid": "550e8400-e29b-41d4-a716-446655440000",
        "ts": now,
        "started_at": now,
        "ver": "0.7.0",
        "os": "linux x86_64",
        "py": "3.12",
        "features": {"raw_edit": True, "sandboxed": False},
        "runtime": {"sessions": 0, "session_files": 0, "setup_sessions": 0},
        "counters": {"total_calls": 0, "errors": 0},
    }
    payload.update(overrides)
    return payload


def make_auth_payload(**overrides) -> dict:
    """Build a valid auth telemetry payload.

    Returns a dict that passes the collector's ``AuthPayload``
    validation. Tests can override any field via keyword args.
    """
    now = int(datetime.now(UTC).timestamp())
    flow_id = str(uuid.uuid4())
    payload = {
        "type": "auth",
        "iid": "550e8400-e29b-41d4-a716-446655440000",
        "flow_id": flow_id,
        "ts": now,
        "ver": "0.38.0",
        "method": "phone",
        "branch": "phone_code",
        "events": [
            {"ts": now, "event": "user_submitted_phone", "flow_id": flow_id},
            {"ts": now + 1, "event": "code_requested", "flow_id": flow_id},
        ],
    }
    payload.update(overrides)
    return payload


def make_auth_event(**overrides) -> dict:
    """Build a single atomic auth event dict.

    Returns a dict suitable for inclusion in an AuthPayload's events array.
    Tests can override any field via keyword args.
    """
    now = int(datetime.now(UTC).timestamp())
    event = {
        "ts": now,
        "event": "user_submitted_phone",
        "flow_id": str(uuid.uuid4()),
    }
    event.update(overrides)
    return event
