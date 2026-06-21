"""Tests for the auth telemetry payload model (ADR 0008).

Tests the AuthPayload dataclass validation — type discrimination,
atomic events, flow_id, method/branch/event/error allowlists.
"""

from __future__ import annotations

import time
import uuid

import pytest
from app.auth_models import AuthPayload, ValidationError

from collector.tests._helpers import make_auth_event, make_auth_payload


class TestAuthPayload:
    """Schema validation for auth telemetry payloads."""

    # ── Valid payloads ──────────────────────────────────────────────

    def test_valid_payload_passes(self):
        """A well-formed auth payload passes validation."""
        payload = AuthPayload.from_dict(make_auth_payload())
        assert payload.type == "auth"
        assert payload.method == "phone"
        assert payload.branch == "phone_code"
        assert len(payload.events) == 2

    def test_valid_qr_payload(self):
        """QR method with qr_scan branch passes validation."""
        data = make_auth_payload(method="qr", branch="qr_scan")
        payload = AuthPayload.from_dict(data)
        assert payload.method == "qr"
        assert payload.branch == "qr_scan"

    def test_valid_bot_payload(self):
        """Bot method with bot_token branch passes validation."""
        data = make_auth_payload(method="bot", branch="bot_token")
        payload = AuthPayload.from_dict(data)
        assert payload.method == "bot"
        assert payload.branch == "bot_token"

    def test_valid_reauth_payload(self):
        """Reauth method with reauth_code branch passes validation."""
        data = make_auth_payload(method="reauth", branch="reauth_code")
        payload = AuthPayload.from_dict(data)
        assert payload.method == "reauth"
        assert payload.branch == "reauth_code"

    def test_valid_2fa_branches(self):
        """2FA branches (phone_2fa, qr_2fa, reauth_2fa) pass validation."""
        for method, branch in [
            ("phone", "phone_2fa"),
            ("qr", "qr_2fa"),
            ("reauth", "reauth_2fa"),
        ]:
            data = make_auth_payload(method=method, branch=branch)
            payload = AuthPayload.from_dict(data)
            assert payload.branch == branch

    def test_payload_with_error_events(self):
        """Events with error fields pass validation."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[
                make_auth_event(
                    ts=int(time.time()),
                    event="code_validated",
                    flow_id=flow_id,
                    error="invalid_code",
                ),
            ],
        )
        payload = AuthPayload.from_dict(data)
        assert payload.events[0]["error"] == "invalid_code"

    def test_single_event_payload(self):
        """Payload with a single event passes validation."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[
                make_auth_event(
                    ts=int(time.time()),
                    event="session_established",
                    flow_id=flow_id,
                ),
            ],
        )
        payload = AuthPayload.from_dict(data)
        assert len(payload.events) == 1

    # ── Type field ──────────────────────────────────────────────────

    def test_type_must_be_auth(self):
        """type must be 'auth'."""
        data = make_auth_payload(type="heartbeat")
        with pytest.raises(ValidationError, match="type"):
            AuthPayload.from_dict(data)

    def test_type_missing_fails(self):
        """Missing type field fails validation."""
        data = make_auth_payload()
        del data["type"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    # ── Required fields ─────────────────────────────────────────────

    def test_missing_iid_fails(self):
        """Missing iid fails validation."""
        data = make_auth_payload()
        del data["iid"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    def test_missing_flow_id_fails(self):
        """Missing flow_id fails validation."""
        data = make_auth_payload()
        del data["flow_id"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    def test_missing_ts_fails(self):
        """Missing ts fails validation."""
        data = make_auth_payload()
        del data["ts"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    def test_missing_ver_fails(self):
        """Missing ver fails validation."""
        data = make_auth_payload()
        del data["ver"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    def test_missing_method_fails(self):
        """Missing method fails validation."""
        data = make_auth_payload()
        del data["method"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    def test_missing_branch_fails(self):
        """Missing branch fails validation."""
        data = make_auth_payload()
        del data["branch"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    def test_missing_events_fails(self):
        """Missing events array fails validation."""
        data = make_auth_payload()
        del data["events"]
        with pytest.raises(ValidationError):
            AuthPayload.from_dict(data)

    # ── Extra fields ────────────────────────────────────────────────

    def test_extra_field_fails(self):
        """Extra fields are rejected."""
        data = make_auth_payload(hacked="yes")
        with pytest.raises(ValidationError, match="Unexpected"):
            AuthPayload.from_dict(data)

    # ── flow_id validation ──────────────────────────────────────────

    def test_flow_id_must_be_uuid(self):
        """flow_id must be a valid UUID."""
        data = make_auth_payload(flow_id="not-a-uuid")
        with pytest.raises(ValidationError, match="flow_id"):
            AuthPayload.from_dict(data)

    def test_flow_id_empty_fails(self):
        """Empty flow_id fails validation."""
        data = make_auth_payload(flow_id="")
        with pytest.raises(ValidationError, match="flow_id"):
            AuthPayload.from_dict(data)

    # ── method validation ─────────────────────────────���─────────────

    def test_invalid_method_fails(self):
        """Unknown method fails validation."""
        data = make_auth_payload(method="magic")
        with pytest.raises(ValidationError, match="method"):
            AuthPayload.from_dict(data)

    # ── branch validation ───────────────────────────────────────────

    def test_invalid_branch_fails(self):
        """Unknown branch fails validation."""
        data = make_auth_payload(branch="unknown_branch")
        with pytest.raises(ValidationError, match="branch"):
            AuthPayload.from_dict(data)

    def test_branch_must_match_method(self):
        """Branch must be valid for the given method."""
        # phone_code is not valid for qr method
        data = make_auth_payload(method="qr", branch="phone_code")
        with pytest.raises(ValidationError, match="branch"):
            AuthPayload.from_dict(data)

    # ── events validation ───────────────────────────────────────────

    def test_empty_events_fails(self):
        """Empty events array fails validation."""
        data = make_auth_payload(events=[])
        with pytest.raises(ValidationError, match="events"):
            AuthPayload.from_dict(data)

    def test_event_missing_ts_fails(self):
        """Event without ts fails validation."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[{"event": "user_submitted_phone", "flow_id": flow_id}],
        )
        with pytest.raises(ValidationError, match="ts"):
            AuthPayload.from_dict(data)

    def test_event_missing_event_name_fails(self):
        """Event without event name fails validation."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[{"ts": int(time.time()), "flow_id": flow_id}],
        )
        with pytest.raises(ValidationError, match="event"):
            AuthPayload.from_dict(data)

    def test_invalid_event_name_fails(self):
        """Unknown event name fails validation."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[
                make_auth_event(
                    ts=int(time.time()),
                    event="made_up_event",
                    flow_id=flow_id,
                ),
            ],
        )
        with pytest.raises(ValidationError, match="event"):
            AuthPayload.from_dict(data)

    def test_invalid_error_category_fails(self):
        """Unknown error category fails validation."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[
                make_auth_event(
                    ts=int(time.time()),
                    event="code_validated",
                    flow_id=flow_id,
                    error="made_up_error",
                ),
            ],
        )
        with pytest.raises(ValidationError, match="error"):
            AuthPayload.from_dict(data)

    # ── ts validation ───────────────────────────────────────────────

    def test_future_ts_fails(self):
        """ts more than 5 min in the future fails validation."""
        data = make_auth_payload(ts=int(time.time()) + 600)
        with pytest.raises(ValidationError, match="future"):
            AuthPayload.from_dict(data)

    def test_old_ts_fails(self):
        """ts older than 7 days fails validation."""
        data = make_auth_payload(ts=int(time.time()) - (8 * 86400))
        with pytest.raises(ValidationError, match="old"):
            AuthPayload.from_dict(data)

    # ── Serialization ───────────────────────────────────────────────

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict roundtrip preserves data."""
        data = make_auth_payload()
        payload = AuthPayload.from_dict(data)
        d = payload.to_dict()
        assert d["type"] == "auth"
        assert d["method"] == "phone"
        assert d["branch"] == "phone_code"
        assert len(d["events"]) == 2

    def test_to_dict_events_preserved(self):
        """to_dict preserves all events with their fields."""
        flow_id = str(uuid.uuid4())
        data = make_auth_payload(
            flow_id=flow_id,
            events=[
                make_auth_event(
                    ts=1000,
                    event="user_submitted_phone",
                    flow_id=flow_id,
                ),
                make_auth_event(
                    ts=1001,
                    event="code_validated",
                    flow_id=flow_id,
                    error="invalid_code",
                ),
            ],
        )
        payload = AuthPayload.from_dict(data)
        d = payload.to_dict()
        assert d["events"][0]["event"] == "user_submitted_phone"
        assert d["events"][1]["error"] == "invalid_code"
