"""Parse ISO 8601 date/time strings for API parameters.

``parse_iso_datetime_utc`` returns ``None`` for missing input or invalid strings.
Callers that accept user-supplied non-empty date strings must treat ``None`` as a
validation failure (see ``find_chats`` / ``get_messages`` error paths).

``parse_schedule_date`` is the stricter sibling used by the scheduling params:
it raises instead of returning ``None`` so a caller can never silently fall back
to "send now" when it meant to queue the message.
"""

import time
from contextlib import suppress
from datetime import UTC, datetime

# Telegram needs a schedule_date that is comfortably in the future; anything at
# or before "now" is rejected server-side, so catch it locally with a clear error.
SCHEDULE_MIN_LEAD_SECONDS = 5


def parse_iso_datetime_utc(raw: str | None) -> datetime | None:
    """Parse an ISO date/time string to a timezone-aware datetime (UTC if naive).

    Returns ``None`` for missing/falsy input or when ``fromisoformat`` rejects the
    string. Does not raise for parse errors.

    **Callers:** If the user provided a non-empty ``min_date`` / ``max_date`` (or
    similar) and this returns ``None``, return a structured validation error; do
    not silently skip date filtering.
    """
    if not raw:
        return None
    with suppress(ValueError):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    return None


def parse_schedule_date(raw: str | None) -> int | None:
    """Parse an ISO 8601 string into the unix timestamp TL ``schedule_date`` wants.

    Returns ``None`` for missing/falsy input (meaning "not scheduled").

    Raises ``ValueError`` when the string is not ISO 8601, or when the instant is
    not far enough in the future. Callers must turn that into a structured error:
    a scheduled send that silently degrades to an immediate send is worse than a
    failed one.
    """
    if not raw:
        return None

    dt = parse_iso_datetime_utc(raw)
    if dt is None:
        raise ValueError(
            f"schedule_date '{raw}' is not a valid ISO 8601 date/time "
            "(e.g. '2026-10-20T09:00:00Z' or '2026-10-20T12:00:00+03:00')"
        )

    timestamp = int(dt.timestamp())
    earliest = int(time.time()) + SCHEDULE_MIN_LEAD_SECONDS
    if timestamp <= earliest:
        raise ValueError(
            f"schedule_date '{raw}' is not in the future; Telegram only accepts "
            f"a time at least {SCHEDULE_MIN_LEAD_SECONDS} seconds ahead"
        )
    return timestamp


def format_schedule_date(timestamp: int | None) -> str | None:
    """Render a ``schedule_date`` timestamp back as an ISO 8601 UTC string."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC).isoformat()
