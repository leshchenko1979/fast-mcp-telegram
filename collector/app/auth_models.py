"""Auth telemetry payload model (ADR 0008).

Validates auth event payloads with type discrimination, atomic events,
flow_id, method/branch/event/error allowlists.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.models import ValidationError

# --- Allowlists ---

_VALID_METHODS = {"phone", "qr", "bot", "reauth"}

_VALID_BRANCHES = {
    "phone_code",
    "phone_2fa",
    "qr_scan",
    "qr_2fa",
    "bot_token",
    "reauth_code",
    "reauth_2fa",
}

# Branch → method mapping: which branches are valid for which methods
_BRANCH_METHODS = {
    "phone_code": "phone",
    "phone_2fa": "phone",
    "qr_scan": "qr",
    "qr_2fa": "qr",
    "bot_token": "bot",
    "reauth_code": "reauth",
    "reauth_2fa": "reauth",
}

_VALID_EVENTS = {
    # User actions
    "user_submitted_phone",
    "user_submitted_code",
    "user_submitted_password",
    "user_scanned_qr",
    "user_reloaded_qr",
    "user_submitted_bot_token",
    "reauth_initiated",
    # System actions
    "code_requested",
    "code_validated",
    "password_validated",
    "qr_session_created",
    "qr_login_confirmed",
    "qr_expired",
    "session_established",
    "cleanup_completed",
}

_VALID_ERRORS = {
    "invalid_code",
    "code_expired",
    "2fa_wrong_password",
    "flood_wait",
    "phone_banned",
    "phone_invalid",
    "phone_unoccupied",
    "connect_failed",
    "timeout",
    "reauth_password_required",
    "qr_session_error",
    "already_authorized",
    "unknown",
}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Timestamp drift limits (same as TelemetryPayload)
_FUTURE_DRIFT_SECONDS = 300  # 5 min
_OLD_WINDOW_SECONDS = 7 * 24 * 3600  # 7 days


@dataclass
class AuthPayload:
    """Schema for auth telemetry payloads (ADR 0008).

    Each payload represents one auth flow. The ``events`` array contains
    all atomic events from that flow. ``flow_id`` groups events from the
    same flow — critical for concurrent users.
    """

    type: Literal["auth"]
    iid: str
    flow_id: str
    ts: int
    ver: str
    method: str
    branch: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate all field constraints."""
        errors: list[str] = []

        # --- type ---
        if self.type != "auth":
            errors.append(f"type must be 'auth', got {self.type!r}")

        # --- iid ---
        if not isinstance(self.iid, str) or not self.iid:
            errors.append("iid must be a non-empty string")
        elif len(self.iid) > 128:
            errors.append(f"iid exceeds 128 chars ({len(self.iid)})")

        # --- flow_id (UUID) ---
        if not isinstance(self.flow_id, str) or not self.flow_id:
            errors.append("flow_id must be a non-empty string")
        elif not _UUID_RE.match(self.flow_id):
            errors.append(f"flow_id must be a valid UUID, got {self.flow_id!r}")

        # --- ts ---
        if not isinstance(self.ts, int) or isinstance(self.ts, bool):
            errors.append("ts must be an integer")
        else:
            now = int(time.time())
            if self.ts > now + _FUTURE_DRIFT_SECONDS:
                errors.append(
                    f"ts {self.ts} is {self.ts - now}s in the future "
                    f"(max {_FUTURE_DRIFT_SECONDS}s)"
                )
            if self.ts < now - _OLD_WINDOW_SECONDS:
                errors.append(
                    f"ts {self.ts} is {now - self.ts}s old (max {_OLD_WINDOW_SECONDS}s)"
                )

        # --- ver ---
        if not isinstance(self.ver, str) or not self.ver:
            errors.append("ver must be a non-empty string")
        elif len(self.ver) > 64:
            errors.append(f"ver exceeds 64 chars ({len(self.ver)})")

        # --- method ---
        if not isinstance(self.method, str) or not self.method:
            errors.append("method must be a non-empty string")
        elif self.method not in _VALID_METHODS:
            errors.append(
                f"method must be one of {sorted(_VALID_METHODS)}, got {self.method!r}"
            )

        # --- branch ---
        if not isinstance(self.branch, str) or not self.branch:
            errors.append("branch must be a non-empty string")
        elif self.branch not in _VALID_BRANCHES:
            errors.append(
                f"branch must be one of {sorted(_VALID_BRANCHES)}, got {self.branch!r}"
            )
        elif self.method in _VALID_METHODS and self.branch in _VALID_BRANCHES:
            expected_method = _BRANCH_METHODS.get(self.branch)
            if expected_method and expected_method != self.method:
                errors.append(
                    f"branch {self.branch!r} belongs to method {expected_method!r}, "
                    f"not {self.method!r}"
                )

        # --- events ---
        if not isinstance(self.events, list):
            errors.append("events must be a list")
        elif len(self.events) == 0:
            errors.append("events must not be empty")
        else:
            for i, ev in enumerate(self.events):
                if not isinstance(ev, dict):
                    errors.append(f"events[{i}] must be a dict")
                    continue
                # ts required
                if "ts" not in ev:
                    errors.append(f"events[{i}].ts is required")
                elif not isinstance(ev["ts"], int) or isinstance(ev["ts"], bool):
                    errors.append(f"events[{i}].ts must be an integer")
                # event name required
                if "event" not in ev:
                    errors.append(f"events[{i}].event is required")
                elif ev["event"] not in _VALID_EVENTS:
                    errors.append(
                        f"events[{i}].event must be one of {sorted(_VALID_EVENTS)}, "
                        f"got {ev['event']!r}"
                    )
                # error optional but must be valid if present
                if "error" in ev and ev["error"] not in _VALID_ERRORS:
                    errors.append(
                        f"events[{i}].error must be one of {sorted(_VALID_ERRORS)}, "
                        f"got {ev['error']!r}"
                    )

        if errors:
            raise ValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthPayload:
        """Construct and validate from a raw dict.

        Rejects extra keys not in the schema.
        """
        known = set(cls.__dataclass_fields__)
        extra = set(data) - known
        if extra:
            raise ValidationError(f"Unexpected fields: {', '.join(sorted(extra))}")
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValidationError(str(exc)) from exc
