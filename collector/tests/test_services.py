"""Tests for the telemetry collector service layer."""

import pytest
from app.services import (
    RateLimitError,
    process_event,
)
from app.services import (
    ValidationError as ServiceValidationError,
)

from collector.tests._helpers import make_auth_payload, make_nested_payload


class TestProcessEvent:
    """Core business logic for processing telemetry events."""

    def test_valid_event_stored(self, storage, valid_payload_data):
        """A valid event is stored in the backend."""
        process_event(valid_payload_data, "192.168.1.1", storage)
        assert len(storage.events) == 1
        stored = storage.events[0]["payload"]
        assert stored.iid == valid_payload_data["iid"]
        assert stored.counters["total_calls"] == 0

    def test_invalid_event_raises(self, storage, valid_payload_data):
        """An invalid event raises and is not stored."""
        valid_payload_data["counters"] = {"total_calls": -1, "errors": 0}
        with pytest.raises(ServiceValidationError):
            process_event(valid_payload_data, "192.168.1.1", storage)
        assert len(storage.events) == 0

    def test_duplicate_within_window_is_deduped(self, storage, valid_payload_data):
        """Same payload within 5 min window is silently deduped."""
        process_event(valid_payload_data, "192.168.1.1", storage)
        process_event(valid_payload_data, "192.168.1.1", storage)
        assert len(storage.events) == 1

    def test_duplicate_from_different_ip_stored(self, storage, valid_payload_data):
        """Same payload from different IP is still deduped (hash-based)."""
        process_event(valid_payload_data, "192.168.1.1", storage)
        process_event(valid_payload_data, "10.0.0.1", storage)
        assert len(storage.events) == 1

    def test_rate_limit_exceeded_raises(self, storage, valid_payload_data):
        """Too many events from one iid in 24h raises RateLimitError."""
        from app.services import INSTANCE_RATE_LIMIT

        process_event(valid_payload_data, "10.0.0.1", storage)
        for i in range(1, INSTANCE_RATE_LIMIT):
            data = make_nested_payload()
            # vary counters to bypass dedup
            data["counters"] = {"total_calls": i, "errors": 0}
            process_event(data, "10.0.0.1", storage)
        assert len(storage.events) == INSTANCE_RATE_LIMIT
        with pytest.raises(RateLimitError):
            new_data = make_nested_payload()
            new_data["counters"] = {"total_calls": 9999, "errors": 0}
            process_event(new_data, "10.0.0.1", storage)
        assert len(storage.events) == INSTANCE_RATE_LIMIT

    def test_different_instance_not_rate_limited(self, storage, valid_payload_data):
        """Events from different iids don't interfere."""
        from app.services import INSTANCE_RATE_LIMIT

        for i in range(INSTANCE_RATE_LIMIT):
            data = make_nested_payload()
            data["iid"] = f"550e8400-e29b-41d4-a716-4466554400{i:02d}"
            data["counters"] = {"total_calls": i, "errors": 0}
            process_event(data, "10.0.0.1", storage)
        assert len(storage.events) == INSTANCE_RATE_LIMIT

    def test_row_cap_enforced(self, storage, valid_payload_data):
        """Storage enforces maximum row count by dropping oldest."""
        cap = 5
        for i in range(cap):
            data = make_nested_payload()
            data["iid"] = f"550e8400-e29b-41d4-a716-44665544000{i}"
            data["counters"] = {"total_calls": i, "errors": 0}
            process_event(data, "10.0.0.1", storage, max_rows=cap)
        assert len(storage.events) == cap
        # One more triggers the cap removal
        new_data = make_nested_payload()
        new_data["iid"] = "550e8400-e29b-41d4-a716-446655449999"
        new_data["counters"] = {"total_calls": 9999, "errors": 0}
        process_event(new_data, "10.0.0.1", storage, max_rows=cap)
        # Still at cap (oldest got removed)
        assert len(storage.events) == cap
        # The newest event should still be present
        assert storage.events[-1]["payload"].iid.endswith("9999")

    def test_storage_backend_close(self, storage):
        """close() cleans up."""
        storage.close()
        assert len(storage.events) == 0


class TestProcessAuthEvent:
    """Type discrimination: auth events vs heartbeats."""

    def test_valid_auth_event_stored(self, storage):
        """A valid auth payload is stored in the backend."""
        data = make_auth_payload()
        process_event(data, "192.168.1.1", storage)
        assert len(storage.events) == 1

    def test_auth_event_not_rate_limited_separately(self, storage):
        """Auth events use the same rate limit as heartbeats."""
        from app.services import INSTANCE_RATE_LIMIT

        # Fill up the rate limit with heartbeats
        for i in range(INSTANCE_RATE_LIMIT):
            data = make_nested_payload()
            data["counters"] = {"total_calls": i, "errors": 0}
            process_event(data, "10.0.0.1", storage)
        # Auth event should be rate-limited too
        auth_data = make_auth_payload()
        with pytest.raises(RateLimitError):
            process_event(auth_data, "10.0.0.1", storage)

    def test_invalid_auth_event_raises(self, storage):
        """An invalid auth payload raises ValidationError."""
        data = make_auth_payload(method="invalid_method")
        with pytest.raises(ServiceValidationError):
            process_event(data, "192.168.1.1", storage)
        assert len(storage.events) == 0

    def test_auth_event_with_invalid_events_raises(self, storage):
        """Auth payload with invalid event names raises ValidationError."""
        import uuid as uuid_mod

        flow_id = str(uuid_mod.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[
                {"ts": 1000, "event": "fake_event", "flow_id": flow_id},
            ],
        )
        with pytest.raises(ServiceValidationError):
            process_event(data, "192.168.1.1", storage)

    def test_auth_and_heartbeat_coexist(self, storage):
        """Auth events and heartbeats can be stored in the same backend."""
        heartbeat = make_nested_payload()
        process_event(heartbeat, "192.168.1.1", storage)
        auth = make_auth_payload()
        process_event(auth, "192.168.1.1", storage)
        assert len(storage.events) == 2
