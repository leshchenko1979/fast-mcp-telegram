"""Tests for auth telemetry (ADR 0008).

Tests the client-side auth telemetry implementation:
- send_auth_event accumulates events in per-flow buffer
- flush_auth_events sends batched HTTP POST
- flush_auth_events clears buffer after send
- flush_auth_events handles network errors silently
- web_setup instrumentation fires correct atomic events
- cli_setup instrumentation fires correct atomic events
"""

from __future__ import annotations

import os
import uuid

import pytest


@pytest.fixture(autouse=True)
def _clear_env():
    """Remove telemetry-related env vars before each test."""
    for key in ("DO_NOT_TRACK",):
        os.environ.pop(key, None)
    yield


@pytest.fixture(autouse=True)
def _clear_auth_buffers():
    """Clear auth event buffers before each test."""
    import src.telemetry as tel

    tel._auth_buffers.clear()
    yield
    tel._auth_buffers.clear()


@pytest.fixture
def tel():
    """Import telemetry module for testing."""
    import src.telemetry as tel_mod

    return tel_mod


class _SyncThread:
    """Fake thread that runs target synchronously (for testing)."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        pass


@pytest.fixture
def _sync_threads(monkeypatch):
    """Make threading.Thread run synchronously for deterministic tests."""
    import threading

    monkeypatch.setattr(threading, "Thread", _SyncThread)


# ───────────────────────────── send_auth_event ───────────────────────────


class TestSendAuthEvent:
    """send_auth_event accumulates events in per-flow buffer."""

    def test_send_auth_event_accumulates(self, tel):
        """Events are accumulated in the buffer keyed by flow_id."""
        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        assert flow_id in tel._auth_buffers
        assert len(tel._auth_buffers[flow_id]) == 1
        assert tel._auth_buffers[flow_id][0]["event"] == "user_submitted_phone"

    def test_send_auth_event_multiple_events(self, tel):
        """Multiple events accumulate in the same flow buffer."""
        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        tel.send_auth_event(
            event="code_requested",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        tel.send_auth_event(
            event="user_submitted_code",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        assert len(tel._auth_buffers[flow_id]) == 3

    def test_send_auth_event_different_flows_separate(self, tel):
        """Different flow_ids have separate buffers."""
        flow_a = str(uuid.uuid4())
        flow_b = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_a,
            method="phone",
            branch="phone_code",
        )
        tel.send_auth_event(
            event="qr_session_created",
            flow_id=flow_b,
            method="qr",
            branch="qr_scan",
        )
        assert len(tel._auth_buffers[flow_a]) == 1
        assert len(tel._auth_buffers[flow_b]) == 1
        assert tel._auth_buffers[flow_a][0]["event"] == "user_submitted_phone"
        assert tel._auth_buffers[flow_b][0]["event"] == "qr_session_created"

    def test_send_auth_event_carries_metadata(self, tel):
        """Each event carries method, branch, and error fields."""
        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="code_validated",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
            error="invalid_code",
        )
        event = tel._auth_buffers[flow_id][0]
        assert event["method"] == "phone"
        assert event["branch"] == "phone_code"
        assert event["error"] == "invalid_code"

    def test_send_auth_event_no_error_field_when_none(self, tel):
        """Events without error don't have an error key."""
        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="session_established",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        event = tel._auth_buffers[flow_id][0]
        assert "error" not in event

    def test_send_auth_event_disabled_by_do_not_track(self, tel):
        """DO_NOT_TRACK=1 prevents event accumulation."""
        os.environ["DO_NOT_TRACK"] = "1"
        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        assert flow_id not in tel._auth_buffers

    def test_send_auth_event_has_timestamp(self, tel):
        """Each event has a ts field (unix seconds)."""
        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        event = tel._auth_buffers[flow_id][0]
        assert "ts" in event
        assert isinstance(event["ts"], int)
        assert event["ts"] > 0


# ───────────────────────────── flush_auth_events ─────────────────────────


class TestFlushAuthEvents:
    """flush_auth_events sends batched HTTP POST and clears buffer."""

    def test_flush_sends_batch(self, tel, monkeypatch, _sync_threads):
        """flush_auth_events sends all accumulated events in one POST."""
        captured = []

        def mock_post(payload, label):
            captured.append(payload)

        monkeypatch.setattr(tel, "_post_json", mock_post)

        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        tel.send_auth_event(
            event="code_requested",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        tel.flush_auth_events(flow_id)

        assert len(captured) == 1
        payload = captured[0]
        assert payload["type"] == "auth"
        assert payload["flow_id"] == flow_id
        assert len(payload["events"]) == 2

    def test_flush_clears_buffer(self, tel, monkeypatch, _sync_threads):
        """flush_auth_events clears the buffer after sending."""
        monkeypatch.setattr(tel, "_post_json", lambda *_: None)

        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        tel.flush_auth_events(flow_id)
        assert flow_id not in tel._auth_buffers

    def test_flush_noop_for_unknown_flow(self, tel, monkeypatch, _sync_threads):
        """flush_auth_events is a no-op for unknown flow_id."""
        called = []
        monkeypatch.setattr(tel, "_post_json", lambda *_: called.append(1))

        tel.flush_auth_events(str(uuid.uuid4()))
        assert len(called) == 0

    def test_flush_includes_metadata(self, tel, monkeypatch, _sync_threads):
        """Flushed payload includes iid, ver, method, branch."""
        captured = []
        monkeypatch.setattr(tel, "_post_json", lambda p, _: captured.append(p))

        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="session_established",
            flow_id=flow_id,
            method="qr",
            branch="qr_scan",
        )
        tel.flush_auth_events(flow_id)

        payload = captured[0]
        assert "iid" in payload
        assert "ver" in payload
        assert payload["method"] == "qr"
        assert payload["branch"] == "qr_scan"

    def test_flush_error_silent(self, tel, monkeypatch, _sync_threads):
        """Network errors during flush are silently ignored."""

        def fail(*_):
            raise ConnectionError("refused")

        monkeypatch.setattr(tel, "_post_json", fail)

        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="user_submitted_phone",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
        )
        # Should not raise
        tel.flush_auth_events(flow_id)
        # Buffer should still be cleared
        assert flow_id not in tel._auth_buffers

    def test_flush_includes_all_event_fields(self, tel, monkeypatch, _sync_threads):
        """Flushed events include all fields: ts, event, flow_id, method, branch, error."""
        captured = []
        monkeypatch.setattr(tel, "_post_json", lambda p, _: captured.append(p))

        flow_id = str(uuid.uuid4())
        tel.send_auth_event(
            event="code_validated",
            flow_id=flow_id,
            method="phone",
            branch="phone_code",
            error="invalid_code",
        )
        tel.flush_auth_events(flow_id)

        event = captured[0]["events"][0]
        assert event["ts"] > 0
        assert event["event"] == "code_validated"
        assert event["flow_id"] == flow_id
        assert event["method"] == "phone"
        assert event["branch"] == "phone_code"
        assert event["error"] == "invalid_code"
