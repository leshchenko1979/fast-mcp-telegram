"""Test fixtures for the telemetry collector.

The fixtures use the nested payload format produced by
``src.telemetry.gather_payload()`` — this is the real format the
client sends. Tests verify that the collector accepts it.
"""

import json as json_module
import sys
import threading
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

# Make ``app.*`` module importable (matches the Docker runtime path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import PayloadLike

from collector.tests._helpers import make_nested_payload


def pytest_configure(config):
    """Register custom markers."""
    for marker in ("unit", "integration", "e2e"):
        config.addinivalue_line("markers", f"{marker}: custom marker")


# ---- In-memory storage backend for testing ----


class InMemoryStorage:
    """In-memory storage backend for testing."""

    def __init__(self):
        self.events: list[dict] = []

    def store(
        self,
        payload: PayloadLike,
        source_ip_hash: str,
        payload_hash: str,
    ) -> None:
        self.events.append({
            "payload": payload,
            "source_ip_hash": source_ip_hash,
            "received_at": datetime.now(UTC),
            "payload_hash": payload_hash,
        })

    def count_recent_events(
        self, instance_id: str, window_hours: int = 24
    ) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        return sum(
            1 for e in self.events
            if e["payload"].iid == instance_id
            and e["received_at"] >= cutoff
        )

    def has_exact_payload(
        self, payload_hash: str, window_seconds: int = 300
    ) -> bool:
        cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
        return any(
            e["payload_hash"] == payload_hash and e["received_at"] >= cutoff
            for e in self.events
        )

    def enforce_row_cap(self, max_rows: int = 10_000_000) -> int:
        if len(self.events) <= max_rows:
            return 0
        keep = self.events[-max_rows:]
        removed = len(self.events) - len(keep)
        self.events = keep
        return removed

    def last_event_at(self):
        """Return the timestamp of the most recent event, or None."""
        if not self.events:
            return None
        return max(e["received_at"] for e in self.events)

    def cleanup_ttl(self, retention_days: int = 90) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        before = len(self.events)
        self.events = [
            e for e in self.events if e["received_at"] >= cutoff
        ]
        return before - len(self.events)

    def close(self) -> None:
        self.events.clear()


# ---- Fixtures ----


@pytest.fixture
def storage():
    """In-memory storage backend for tests."""
    return InMemoryStorage()


@pytest.fixture
def valid_payload_data():
    """A valid telemetry payload as a dict (matches gather_payload)."""
    return make_nested_payload()


class _TestClient:
    """Minimal HTTP test client wrapping http.client.

    Preserves the ``client.get(path)`` / ``client.post(path, json=…)``
    syntax from the old FastAPI TestClient tests.
    """

    def __init__(self, port: int):
        self._port = port

    def _request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        conn = HTTPConnection("localhost", self._port, timeout=5)
        try:
            req_headers = {"Content-Type": "application/json"} if body else {}
            if headers:
                req_headers.update(headers)
            conn.request(method, path, body=body, headers=req_headers)
            resp = conn.getresponse()
            data = resp.read()
            resp.status_code = resp.status
            resp.json = lambda _data=data: json_module.loads(_data)
            return resp
        finally:
            conn.close()

    def get(self, path: str):
        return self._request("GET", path)

    def post(
        self,
        path: str,
        json: dict | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ):
        """POST JSON dict (``json=``) or raw bytes (``data=`` / ``content=``)."""
        if json is not None:
            body = json_module.dumps(json).encode()
            req_headers = {"Content-Type": "application/json"}
        else:
            body = data if data is not None else (content or b"")
            req_headers = {}
        if headers:
            req_headers.update(headers)
        return self._request("POST", path, body, req_headers)


@pytest.fixture
def server_port(storage):
    """Start a ThreadingHTTPServer on a random port with in-memory storage.

    Yields the port number. Server is shut down after the test.
    """
    from app.main import create_handler

    handler = create_handler(storage)
    server = ThreadingHTTPServer(("localhost", 0), handler)
    port = server.server_address[1]

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    yield port

    server.shutdown()


@pytest.fixture
def client(server_port):
    """HTTP test client connected to the in-memory test server."""
    return _TestClient(server_port)
