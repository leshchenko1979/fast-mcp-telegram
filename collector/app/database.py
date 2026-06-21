"""PostgreSQL storage backend for the telemetry collector.

Stores the full client payload as JSONB and extracts ``instance_id`` to
a top-level indexed column for efficient rate-limit queries.

Schema:
    id              BIGSERIAL — primary key
    received_at     TIMESTAMPTZ — server-side insert time
    instance_id     TEXT — extracted from payload.iid (indexed)
    payload         JSONB — the full nested payload from the client
    payload_hash    TEXT — SHA-256 of canonicalized payload (indexed)
    source_ip_hash  TEXT — SHA-256 of the request source IP
"""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras
from app.services import PayloadLike

_SQL_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS telemetry (
    id              BIGSERIAL PRIMARY KEY,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instance_id     TEXT NOT NULL,
    payload         JSONB NOT NULL,
    payload_hash    TEXT NOT NULL,
    source_ip_hash  TEXT NOT NULL
);
"""

_SQL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_telemetry_instance_id ON telemetry(instance_id)",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_received_at ON telemetry(received_at)",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_payload_hash ON telemetry(payload_hash)",
]

# TCP keepalive options — prevent PostgreSQL from silently dropping idle connections.
_KEEPALIVES = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}


class PgStorage:
    """Production PostgreSQL backend for the collector.

    Includes automatic reconnection on stale/dead connections and TCP
    keepalive settings to prevent idle disconnects.

    Usage:
        storage = PgStorage(dsn="postgres://user:pass@host/db")
        storage.connect()
        storage.store(payload, ip_hash, payload_hash)
        storage.close()
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg2.connection | None = None

    # ---- lifecycle ----

    def connect(self) -> None:
        """Create connection and ensure table exists."""
        self._conn = psycopg2.connect(self._dsn, **_KEEPALIVES)
        with self._conn.cursor() as cur:
            cur.execute(_SQL_CREATE_TABLE)
            for idx in _SQL_INDEXES:
                cur.execute(idx)
        self._conn.commit()

    def close(self) -> None:
        """Close the connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_connection(self) -> None:
        """Ping the connection and reconnect if it's dead."""
        if self._conn is None:
            self.connect()
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            print("Database connection stale — reconnecting…", file=sys.stderr)
            with contextlib.suppress(Exception):
                self._conn.close()
            self.connect()

    def _execute(self, func: Any) -> Any:
        """Execute *func(cursor)* with automatic retry on stale connection."""
        try:
            return func()
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            print("Query failed on stale connection — retrying…", file=sys.stderr)
            self._ensure_connection()
            return func()

    # ---- storage interface ----

    def store(
        self,
        payload: PayloadLike,
        source_ip_hash: str,
        payload_hash: str,
    ) -> None:
        """Insert one telemetry event.

        ``payload_hash`` is computed once by the service layer and
        passed in — the storage backend does not recompute it.
        """
        payload_json = json.dumps(payload.to_dict())

        def _do() -> None:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO telemetry
                        (instance_id, payload, payload_hash, source_ip_hash)
                    VALUES (%s, %s::jsonb, %s, %s)
                    """,
                    (payload.iid, payload_json, payload_hash, source_ip_hash),
                )
            self._conn.commit()

        self._execute(_do)

    def count_recent_events(self, instance_id: str, window_hours: int = 24) -> int:
        """Count events for a given instance_id within a time window."""

        def _do() -> int:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM telemetry
                    WHERE instance_id = %s
                      AND received_at >= NOW() - make_interval(hours => %s)
                    """,
                    (instance_id, window_hours),
                )
                row = cur.fetchone()
                return row[0] if row else 0

        return self._execute(_do)

    def has_exact_payload(self, payload_hash: str, window_seconds: int = 300) -> bool:
        """Check if an identical payload hash exists within the time window."""

        def _do() -> bool:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM telemetry
                    WHERE payload_hash = %s
                      AND received_at >= NOW() - make_interval(secs => %s)
                    LIMIT 1
                    """,
                    (payload_hash, window_seconds),
                )
                return cur.fetchone() is not None

        return self._execute(_do)

    def last_event_at(self) -> datetime | None:
        """Return the timestamp of the most recent event, or ``None``."""

        def _do() -> datetime | None:
            with self._conn.cursor() as cur:
                cur.execute("SELECT MAX(received_at) FROM telemetry")
                row = cur.fetchone()
                return row[0] if row and row[0] else None

        return self._execute(_do)

    def enforce_row_cap(self, max_rows: int = 10_000_000) -> int:
        """Delete oldest rows when count exceeds max_rows.

        Orders by id DESC (newest first) and finds the boundary ID
        at the cap position, then does a range delete — this is
        significantly faster than ``OFFSET`` in a subquery for
        tables with millions of rows.

        Reference: https://dba.stackexchange.com/a/183096
        """

        def _do() -> int:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    WITH boundary AS (
                        SELECT id FROM telemetry
                        ORDER BY id DESC
                        OFFSET %s LIMIT 1
                    )
                    DELETE FROM telemetry
                    WHERE id <= (SELECT id FROM boundary)
                      AND EXISTS (SELECT 1 FROM boundary)
                    """,
                    (max_rows,),
                )
                result = cur.rowcount
            self._conn.commit()
            return result

        return self._execute(_do)

    def cleanup_ttl(self, retention_days: int = 90) -> int:
        """Purge rows older than retention_days."""

        def _do() -> int:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM telemetry
                    WHERE received_at < NOW() - make_interval(days => %s)
                    """,
                    (retention_days,),
                )
                result = cur.rowcount
            self._conn.commit()
            return result

        return self._execute(_do)
