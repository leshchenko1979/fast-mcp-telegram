"""Core business logic for the telemetry collector.

Handles validation, rate limiting, deduplication, and storage of
incoming telemetry events.
"""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from app.auth_models import AuthPayload
from app.models import (  # noqa: F401 — re-exported for main.py and tests
    TelemetryPayload,
    ValidationError,
)

# --- Configurable limits (can be overridden per-call or via env) ---
INSTANCE_RATE_LIMIT: int = 100  # Max events per instance_id per 24h
DEDUP_WINDOW_SECONDS: int = 300  # Exact-payload dedup window (5 min)
MAX_ROWS: int = 10_000_000  # Hard ceiling on total stored rows
RETENTION_DAYS: int = 90  # TTL — purge rows older than this

# Union type for storage backends
PayloadLike = TelemetryPayload | AuthPayload


class StorageBackend(Protocol):
    """Abstract storage backend that the service layer depends on."""

    def store(
        self,
        payload: PayloadLike,
        source_ip_hash: str,
        payload_hash: str,
    ) -> None: ...

    def count_recent_events(self, instance_id: str, window_hours: int = 24) -> int: ...

    def has_exact_payload(
        self, payload_hash: str, window_seconds: int = DEDUP_WINDOW_SECONDS
    ) -> bool: ...

    def enforce_row_cap(self, max_rows: int = MAX_ROWS) -> int: ...

    def cleanup_ttl(self, retention_days: int = RETENTION_DAYS) -> int: ...

    def last_event_at(self) -> object: ...


class RateLimitError(Exception):
    """The sender has exceeded their rate limit."""


# --- Helpers ---


def hash_source_ip(source_ip: str) -> str:
    """One-way hash of the source IP for privacy."""
    return hashlib.sha256(source_ip.encode()).hexdigest()


def compute_payload_hash(payload: PayloadLike) -> str:
    """Canonical SHA-256 hash of the payload (for dedup).

    Computed once per request and passed to the storage layer so the
    storage backend does not need to recompute it.
    """
    canonical = json.dumps(
        payload.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# --- Core entry point ---


def process_event(
    data: dict,
    source_ip: str,
    storage: StorageBackend,
    *,
    instance_rate_limit: int = INSTANCE_RATE_LIMIT,
    max_rows: int = MAX_ROWS,
    dedup_window: int = DEDUP_WINDOW_SECONDS,
) -> None:
    """Validate, rate-limit, deduplicate, and store a telemetry event.

    Args:
        data: Raw JSON body (validated & parsed internally).
        source_ip: The client's IP address (for rate-limiting & logging).
        storage: A StorageBackend implementation.
        instance_rate_limit: Max events per instance_id per 24h.
        max_rows: Hard ceiling on total stored rows.
        dedup_window: Seconds within which an exact payload match is
            considered a duplicate.

    Raises:
        ValidationError: Payload failed schema validation.
        RateLimitError: Sender exceeded rate limit.
    """
    # 1. Parse and validate payload (type discrimination)
    if data.get("type") == "auth":
        payload = AuthPayload.from_dict(data)
    else:
        payload = TelemetryPayload.from_dict(data)

    # 2. Check per-instance_id rate limit
    recent = storage.count_recent_events(payload.iid, window_hours=24)
    if recent >= instance_rate_limit:
        raise RateLimitError(
            f"Instance {payload.iid[:16]}… has sent {recent} events "
            f"in the last 24h (limit: {instance_rate_limit})"
        )

    # 3. Check dedup against exact payload in last N seconds
    payload_hash = compute_payload_hash(payload)
    if storage.has_exact_payload(payload_hash, window_seconds=dedup_window):
        return  # Silent dedup — already seen this exact payload

    # 4. Store (pass the precomputed hash — no recomputation)
    ip_hash = hash_source_ip(source_ip)
    storage.store(payload, ip_hash, payload_hash)

    # 5. Enforce row cap and TTL
    storage.enforce_row_cap(max_rows)
    storage.cleanup_ttl(RETENTION_DAYS)
