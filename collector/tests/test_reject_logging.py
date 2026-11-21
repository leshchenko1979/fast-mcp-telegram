"""Tests for rejection and dedup logging in the telemetry collector.

The collector used to drop events silently: a macOS client could be
rejected for a month with no way to observe it from outside. These tests
pin the log contract that makes rejections visible.
"""

from __future__ import annotations

import logging

from app.services import INSTANCE_RATE_LIMIT

from collector.tests._helpers import make_nested_payload

COLLECTOR_LOGGER = "collector"


def _reject_records(caplog, status: int) -> list[logging.LogRecord]:
    """WARNING records carrying the ``reject status=<status>`` marker."""
    marker = f"reject status={status}"
    return [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and marker in record.getMessage()
    ]


def _warnings(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestRejectionLogging:
    """Every rejection path writes exactly one greppable WARNING line."""

    def test_invalid_json_logs_422(self, client, caplog):
        """Unparseable body: 422 + WARNING with the JSON error and no iid."""
        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            resp = client.post(
                "/v1/event",
                content=b"not-json",
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 422
        records = _reject_records(caplog, 422)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "reason=" in message
        assert "Expecting" in message  # real JSONDecodeError text
        assert "iid=-" in message
        assert "ip_hash=" in message
        assert "ip_hash=-" not in message

    def test_non_object_body_logs_422(self, client, caplog):
        """JSON that is not an object: 422 + WARNING with the fixed reason."""
        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            resp = client.post("/v1/event", json=[1, 2, 3])

        assert resp.status_code == 422
        records = _reject_records(caplog, 422)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "Body must be a JSON object" in message
        assert "iid=-" in message

    def test_validation_error_logs_422_with_identity(self, client, caplog):
        """ValidationError: 422 + WARNING carrying iid/ver/os from the body."""
        data = make_nested_payload(counters={"total_calls": -1, "errors": 0})

        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            resp = client.post("/v1/event", json=data)

        assert resp.status_code == 422
        records = _reject_records(caplog, 422)
        assert len(records) == 1
        message = records[0].getMessage()
        assert "counters.'total_calls' must be >= 0" in message
        assert "iid=550e8400-e29b-41 " in message  # truncated to 16 chars
        assert "ver=0.7.0" in message
        assert "os='linux x86_64'" in message

    def test_rate_limit_logs_429(self, client, caplog):
        """RateLimitError: 429 + WARNING with the real limit text."""
        for i in range(INSTANCE_RATE_LIMIT):
            data = make_nested_payload()
            data["counters"] = {"total_calls": i, "errors": 0}
            assert client.post("/v1/event", json=data).status_code == 204

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            resp = client.post("/v1/event", json=make_nested_payload())

        assert resp.status_code == 429
        records = _reject_records(caplog, 429)
        assert len(records) == 1
        message = records[0].getMessage()
        assert f"limit: {INSTANCE_RATE_LIMIT}" in message
        assert "iid=550e8400-e29b-41 " in message  # truncated to 16 chars


class TestNoFalsePositives:
    """The instrument must stay silent on normal traffic."""

    def test_valid_payload_logs_no_warning(self, client, caplog, valid_payload_data):
        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            resp = client.post("/v1/event", json=valid_payload_data)

        assert resp.status_code == 204
        assert _warnings(caplog) == []

    def test_duplicate_payload_logs_no_warning(
        self, client, caplog, valid_payload_data
    ):
        """Dedup is a 204, not a rejection — no WARNING, but a DEBUG trace."""
        assert client.post("/v1/event", json=valid_payload_data).status_code == 204

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger=COLLECTOR_LOGGER):
            resp = client.post("/v1/event", json=valid_payload_data)

        assert resp.status_code == 204
        assert _warnings(caplog) == []
        dedup = [r for r in caplog.records if "dedup drop" in r.getMessage()]
        assert len(dedup) == 1
        assert "iid=550e8400-e29b-41 " in dedup[0].getMessage()


class TestPrivacy:
    """Raw client IPs never reach a WARNING/ERROR line."""

    def test_raw_ip_absent_from_rejection_logs(
        self, client, storage, caplog, monkeypatch
    ):
        monkeypatch.setattr(
            storage, "count_recent_events", lambda *a, **k: INSTANCE_RATE_LIMIT
        )
        data = make_nested_payload()
        del data["iid"]

        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            client.post("/v1/event", content=b"not-json")
            client.post("/v1/event", json=[1, 2, 3])
            client.post("/v1/event", json=data)
            client.post("/v1/event", json=make_nested_payload())

        assert _warnings(caplog), "expected rejections to be logged"
        assert "127.0.0.1" not in caplog.text
        assert "::1" not in caplog.text
        for record in caplog.records:
            assert "127.0.0.1" not in record.getMessage()


class TestUnhandledException:
    """A storage blow-up must leave a traceback, not a bare connection reset."""

    def test_storage_failure_logs_error_and_returns_500(
        self, client, storage, caplog, monkeypatch, valid_payload_data
    ):
        def boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(storage, "count_recent_events", boom)

        with caplog.at_level(logging.WARNING, logger=COLLECTOR_LOGGER):
            resp = client.post("/v1/event", json=valid_payload_data)

        assert resp.status_code == 500
        assert resp.json() == {"detail": "internal error"}

        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(errors) == 1
        assert errors[0].exc_info is not None
        assert "RuntimeError: db down" in caplog.text
        assert "db down" not in resp.json()["detail"]


class TestAccessLog:
    """``log_message`` is a real DEBUG logger, not a no-op lie."""

    def test_access_log_at_debug(self, client, caplog):
        with caplog.at_level(logging.DEBUG, logger=COLLECTOR_LOGGER):
            assert client.get("/health").status_code == 200

        access = [
            r
            for r in caplog.records
            if r.levelno == logging.DEBUG and "GET /health" in r.getMessage()
        ]
        assert len(access) == 1

    def test_no_access_log_at_default_level(self, client, caplog):
        with caplog.at_level(logging.INFO, logger=COLLECTOR_LOGGER):
            assert client.get("/health").status_code == 200

        assert [r for r in caplog.records if "GET /health" in r.getMessage()] == []
