"""Payload model for the telemetry collector.

Replaced Pydantic v2 with stdlib ``dataclasses`` to reduce RSS
(~15-20 MB saved by not loading pydantic-core Rust .so).

Validation runs in ``__post_init__`` — no type coercion, strict
type checks.  All errors are collected and reported at once.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.payload_validation import (
    ValidationError,
    construct_from_dict,
    validate_iid,
    validate_ts,
    validate_ver,
)


@dataclass
class TelemetryPayload:
    """Schema for incoming anonymous telemetry events.

    Matches the payload sent by fast-mcp-telegram library clients
    (see ``src.telemetry.gather_payload`` and ADR 0005).

    No extra fields are allowed — use ``.from_dict()`` for construction
    (it checks for unknown keys).
    """

    v: Literal[1]
    iid: str
    ts: int
    started_at: int
    ver: str
    os: str
    py: str
    features: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, int | None] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    tools: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate all field constraints.

        ``Literal[1]`` on ``v`` is not enforced by ``dataclass`` init —
        Python does not check type annotations at runtime — so we
        validate it manually along with length bounds and non-negativity.
        """
        errors: list[str] = []

        # --- v (Literal[1]) ---
        if self.v != 1:
            errors.append(f"v must be 1, got {self.v!r}")

        # --- iid ---
        validate_iid(self.iid, errors)

        # --- ts ---
        validate_ts(self.ts, errors)

        # --- started_at ---
        if not isinstance(self.started_at, int) or isinstance(self.started_at, bool):
            errors.append("started_at must be an integer")
        elif self.started_at < 0:
            errors.append(f"started_at must be >= 0, got {self.started_at}")

        # --- ver ---
        validate_ver(self.ver, errors)

        # --- os ---
        if not isinstance(self.os, str):
            errors.append("os must be a string")
        elif len(self.os) > 128:
            errors.append(f"os exceeds 128 chars ({len(self.os)})")

        # --- py ---
        if not isinstance(self.py, str):
            errors.append("py must be a string")
        elif len(self.py) > 32:
            errors.append(f"py exceeds 32 chars ({len(self.py)})")

        # --- features ---
        if not isinstance(self.features, dict):
            errors.append("features must be a dict")
        else:
            if len(self.features) > 256:
                errors.append(f"features has {len(self.features)} keys (max 256)")
            for k in self.features:
                if not isinstance(k, str) or not k:
                    errors.append("feature keys must be non-empty strings")
                    break
                if len(k) > 128:
                    errors.append(f"feature key {k!r} exceeds 128 chars")
                    break

        # --- runtime / counters ---
        #
        # Two different rules, deliberately not shared:
        #
        # ``runtime`` values may be ``int`` *or* ``None``.  ``memory_kb``
        # is the RSS of the client process, read from /proc/self/status,
        # which only exists on Linux — non-Linux clients (macOS/Windows)
        # send ``null`` for it by design (see ADR 0005 and
        # ``src.telemetry._get_rss_kb``).  The key is optional and null
        # is a valid value, so rejecting it silently drops every event
        # from those platforms.
        #
        # ``counters`` values are strictly non-negative ints: they are
        # accumulating totals, never absent by platform.
        if not isinstance(self.runtime, dict):
            errors.append("runtime must be a dict")
        else:
            for k, val in self.runtime.items():
                if val is None:
                    continue
                if not isinstance(val, int) or isinstance(val, bool):
                    errors.append(
                        f"runtime.{k!r} must be int or null, got {type(val).__name__}"
                    )
                    break
                if val < 0:
                    errors.append(f"runtime.{k!r} must be >= 0, got {val}")
                    break

        if not isinstance(self.counters, dict):
            errors.append("counters must be a dict")
        else:
            for k, val in self.counters.items():
                if not isinstance(val, int) or isinstance(val, bool):
                    errors.append(
                        f"counters.{k!r} must be int, got {type(val).__name__}"
                    )
                    break
                if val < 0:
                    errors.append(f"counters.{k!r} must be >= 0, got {val}")
                    break

        if errors:
            raise ValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict.

        Replaces ``pydantic.BaseModel.model_dump(mode="json")``.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryPayload:
        """Construct and validate from a raw dict.

        Rejects extra keys not in the schema (like pydantic's
        ``model_config = {"extra": "forbid"}``).

        Raises ``ValidationError`` on any issue.
        """
        return construct_from_dict(cls, data)
