"""Synchronous HTTP server for the telemetry collector.

Serves the /v1/event endpoint and /health check using stdlib
``http.server.ThreadingHTTPServer`` — no ASGI framework needed.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.services import (
    RateLimitError,
    StorageBackend,
    ValidationError,
    hash_source_ip,
    process_event,
)

logger = logging.getLogger("collector")

# A single validation error can list dozens of fields — cap the reason so one
# bad payload cannot flood the container log.
MAX_REASON_CHARS = 300
MAX_IID_CHARS = 16


def _identity(data: object) -> tuple[str, str, str]:
    """Best-effort ``(iid, ver, os)`` from a raw body; never raises."""
    if not isinstance(data, dict):
        return "-", "-", "-"

    def field(key: str, limit: int) -> str:
        value = data.get(key)
        return value[:limit] if isinstance(value, str) else "-"

    return field("iid", MAX_IID_CHARS), field("ver", 32), field("os", 128)


def log_reject(
    status: int,
    reason: object,
    ip_hash: str,
    data: object = None,
) -> None:
    """Log one greppable rejection line.

    ``ip_hash`` must already be hashed — the raw client IP is never logged.
    This function must never raise into the request path.
    """
    try:
        text = str(reason)
        if len(text) > MAX_REASON_CHARS:
            text = text[:MAX_REASON_CHARS] + "..."
        iid, ver, os_name = _identity(data)
        logger.warning(
            "reject status=%d reason=%r ip_hash=%s iid=%s ver=%s os=%r",
            status,
            text,
            ip_hash,
            iid,
            ver,
            os_name,
        )
    except Exception:  # pragma: no cover - logging must never break a request
        logger.debug("reject status=%d (rejection logging failed)", status)


def create_handler(
    storage: StorageBackend,
) -> type[BaseHTTPRequestHandler]:
    """Build a ``BaseHTTPRequestHandler`` subclass wired to *storage*.

    In tests, pass an in-memory ``storage`` backend.
    In production, ``main()`` builds a ``PgStorage`` and passes it here.
    """

    class TelemetryHandler(BaseHTTPRequestHandler):
        """Minimal HTTP handler for telemetry ingestion."""

        server_version = "TelemetryCollector/0.1.0"
        sys_version = ""

        # ---- helpers ----

        def _json_response(self, data: object, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", 0))
            return self.rfile.read(length)

        # ---- routes ----

        def do_GET(self) -> None:
            if self.path == "/health":
                now = time.time()
                try:
                    last = storage.last_event_at()
                except Exception:
                    last = None

                if last is not None:
                    last_ts = (
                        last.timestamp() if hasattr(last, "timestamp") else float(last)
                    )
                    seconds_ago = round(now - last_ts)
                    last_iso = (
                        last.isoformat() if hasattr(last, "isoformat") else str(last)
                    )
                else:
                    seconds_ago = None
                    last_iso = None

                return self._json_response(
                    {
                        "status": "ok",
                        "service": "telemetry-collector",
                        "last_heartbeat_at": last_iso,
                        "seconds_since_last_heartbeat": seconds_ago,
                    }
                )
            self._json_response({"error": "not found"}, 404)
            return None

        def do_POST(self) -> None:
            if self.path != "/v1/event":
                return self._json_response({"error": "not found"}, 404)

            raw = self._read_body()
            client_ip = self.client_address[0]
            ip_hash = hash_source_ip(client_ip)

            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                log_reject(422, exc, ip_hash)
                return self._json_response({"detail": "Invalid JSON body"}, 422)

            if not isinstance(data, dict):
                log_reject(422, "Body must be a JSON object", ip_hash)
                return self._json_response(
                    {"detail": "Body must be a JSON object"}, 422
                )

            try:
                process_event(data, client_ip, storage)
                self.send_response(204)
                self.end_headers()
            except ValidationError as exc:
                log_reject(422, exc, ip_hash, data)
                self._json_response({"detail": str(exc)}, 422)
            except RateLimitError as exc:
                log_reject(429, exc, ip_hash, data)
                self._json_response({"detail": str(exc)}, 429)
            except Exception:
                # Never leak the exception text to the client, but do leave a
                # traceback: otherwise the client sees a reset and nothing is
                # written anywhere.
                logger.exception(
                    "unhandled error ip_hash=%s iid=%s",
                    ip_hash,
                    _identity(data)[0],
                )
                self._json_response({"detail": "internal error"}, 500)

        def log_message(self, fmt: str, *args: object) -> None:
            """Access log — emitted only when LOG_LEVEL=DEBUG."""
            logger.debug("%s - %s", self.address_string(), fmt % args)

    return TelemetryHandler


# ---- Production entry point (used by Docker CMD) ----


def _log_level() -> int:
    """Resolve ``LOG_LEVEL`` to a logging level, defaulting to INFO."""
    name = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, name, None)
    return level if isinstance(level, int) else logging.INFO


def main() -> None:
    """Connect to PostgreSQL and start the HTTP server.

    Called by ``python3 -m app.main`` in the Docker container.
    """
    logging.basicConfig(
        level=_log_level(),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    from app.database import PgStorage
    from app.settings import DSN

    logger.info("Connecting to database…")
    storage = PgStorage(DSN)
    try:
        storage.connect()
    except Exception:
        logger.exception("Database connection failed")
        sys.exit(1)

    logger.info("Connected. Starting HTTP server on http://0.0.0.0:8000")
    handler = create_handler(storage)
    server = ThreadingHTTPServer(("0.0.0.0", 8000), handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down…")
    finally:
        server.server_close()
        storage.close()
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
