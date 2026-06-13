"""
Anonymous feature-adoption telemetry for fast-mcp-telegram.

Sends periodic heartbeats with anonymised feature-flag and counter data
to the maintainer's collection endpoint.  Opt-out via ``DO_NOT_TRACK=1``.

See ADR 0005 for full design.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import json
import logging
import os
import platform
import sys
import threading
import time
import uuid
from pathlib import Path

from src._version import __version__
from src.config.server_config import cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TELEMETRY_ENDPOINT = "https://fast-mcp-telegram-telemetry.l1979.ru/v1/event"
"""Stable URL baked into each release.  The destination may 301-forward."""

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "fast-mcp-telegram"
"""Directory where the instance-id file lives."""

_MIN_INTERVAL_SECONDS = 3600
"""Minimum heartbeat interval (1 hour)."""

_DEFAULT_INTERVAL_SECONDS = 6 * 3600
"""Default interval between heartbeats (6 hours)."""

# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


def should_send() -> bool:
    """Return ``True`` when telemetry is allowed (the default)."""
    do_not_track = os.environ.get("DO_NOT_TRACK", "").strip()
    return do_not_track != "1"


# ---------------------------------------------------------------------------
# MetricsStore — shared between tool-call sites and the telemetry task
# ---------------------------------------------------------------------------


class MetricsStore:
    """Lifetime-of-process counters for tool-call activity.

    Thread-safe: all mutations and reads go through a ``threading.Lock``
    because ``snapshot()`` is called from a thread-pool executor while
    the event-loop wields ``record_tool_call()``.

    Tracks per-tool, per-parameter-set statistics: call count, total
    duration (ms), error count, and last-N error traces.  The heartbeat
    payload carries a ``tools`` block with this breakdown alongside the
    flat ``counters`` dict for quick health checks.
    """

    # Maximum number of error traces to retain per (tool, param-set) combo.
    MAX_TRACES_PER_COMBO: int = 5

    def __init__(self) -> None:
        self.total_calls: int = 0
        self.errors: int = 0
        self.flood_waits: int = 0
        self._tools: dict[str, dict] = {}
        self._lock = threading.Lock()

    def record_tool_call(
        self,
        tool: str,
        params: frozenset[str],
        duration_ms: float,
        *,
        error: str | None = None,
    ) -> None:
        """Record one tool invocation with duration and optional error.

        Thread-safe — acquires the internal lock.

        Args:
            tool: Tool name (e.g. ``"send_message"``, ``"get_messages"``).
            params: Set of parameter names that were explicitly provided
                in this call (not parameter *values* — just presence).
            duration_ms: Wall-clock duration of the call in milliseconds.
            error:
                * ``None``  — call succeeded, no error counter incremented.
                * ``""``    — error counted but no trace available (e.g.
                  non-ok result from the Telegram API).
                * ``str``   — error counted and the string is stored as a
                  trace (e.g. ``traceback.format_exc()``).
        """
        with self._lock:
            self.total_calls += 1
            param_key = ",".join(sorted(params))

            stats = self._tools.setdefault(
                tool,
                {
                    "calls": 0,
                    "errors": 0,
                    "duration_ms": 0.0,
                    "param_sets": {},
                },
            )
            stats["calls"] += 1
            stats["duration_ms"] += duration_ms

            ps = stats["param_sets"].setdefault(
                param_key,
                {
                    "calls": 0,
                    "errors": 0,
                    "duration_ms": 0.0,
                    "traces": collections.deque(maxlen=self.MAX_TRACES_PER_COMBO),
                },
            )
            ps["calls"] += 1
            ps["duration_ms"] += duration_ms

            if error is not None:
                self.errors += 1
                stats["errors"] += 1
                ps["errors"] += 1
                if error:  # non-empty string = has trace text
                    ps["traces"].append(error)

    def record_flood_wait(self) -> None:
        """Increment flood_waits by 1 (atomic w.r.t. snapshot)."""
        with self._lock:
            self.flood_waits += 1

    def snapshot(self) -> dict:
        """Return a frozen copy of the current counters + per-tool stats.

        The returned dict has the same structure as the heartbeat payload's
        ``counters`` and ``tools`` blocks.
        """
        with self._lock:
            # Deep-copy tools to avoid mutation after releasing the lock
            tools_copy: dict[str, dict] = {}
            for tool_name, stats in self._tools.items():
                ps_copy: dict[str, dict] = {}
                for pk, pstats in stats["param_sets"].items():
                    ps_copy[pk] = {
                        "calls": pstats["calls"],
                        "errors": pstats["errors"],
                        "duration_ms": pstats["duration_ms"],
                        "traces": list(pstats["traces"]),
                    }
                tools_copy[tool_name] = {
                    "calls": stats["calls"],
                    "errors": stats["errors"],
                    "duration_ms": stats["duration_ms"],
                    "param_sets": ps_copy,
                }
            return {
                "total_calls": self.total_calls,
                "errors": self.errors,
                "flood_waits": self.flood_waits,
                "tools": tools_copy,
            }


# Module-level singleton created at import time.
metrics = MetricsStore()

# ---------------------------------------------------------------------------
# Instance ID — persisted across restarts
# ---------------------------------------------------------------------------

_instance_id: str | None = None
"""In-memory cache of the instance ID (avoids re-reading the file every heartbeat)."""


def get_instance_id(config_dir: str | None = None) -> str:
    """Return the persistent instance ID, creating a new UUID v4 if needed.

    The ID is stored in ``{config_dir}/instance_id`` (defaults to
    ``~/.config/fast-mcp-telegram/instance_id``) and survives package reinstall,
    but can be reset by deleting that file.
    """
    global _instance_id

    if _instance_id is not None:
        return _instance_id

    cfg_dir = Path(config_dir) if config_dir else _DEFAULT_CONFIG_DIR
    id_path = cfg_dir / "instance_id"

    if id_path.is_file():
        _instance_id = id_path.read_text(encoding="utf-8").strip()
        return _instance_id

    _instance_id = str(uuid.uuid4())
    cfg_dir.mkdir(parents=True, exist_ok=True)
    id_path.write_text(_instance_id, encoding="utf-8")
    return _instance_id


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------

# Track server start once per process.
_started_at: int = int(time.time())


def _collect_features() -> dict:
    """Assemble the ``features`` block of the telemetry payload."""
    config = cfg()
    return {
        "server_mode": config.server_mode.value,
        "acl_enabled": config.acl_enabled,
        "acl_deny_unlisted_principals": config.acl_deny_unlisted_principals,
        "bot_api_token": bool(config.bot_api_token),
        "mtproto_proxy": bool(config.mtproto_proxy),
        "prefix_mcp_tools_with_account": config.prefix_mcp_tools_with_account,
        "max_active_sessions": config.max_active_sessions,
        "inactive_session_days": config.inactive_session_days,
        "block_private_ips": config.block_private_ips,
        "allow_http_urls": config.allow_http_urls,
    }


def _get_rss_kb() -> int | None:
    """Return the current RSS (resident set size) in kilobytes, or ``None``.

    Reads ``/proc/self/status`` on Linux — no dependencies.  Returns
    ``None`` on any non-Linux platform, permission error, or parsing
    failure so the collector (which expects ``int | null``) handles it
    gracefully.
    """
    with contextlib.suppress(OSError, ValueError, IndexError):  # noqa: SIM117 — must nest so suppress covers open()
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    # Expected: "VmRSS:\t<value> kB"
                    if len(parts) >= 3 and parts[2] == "kB":
                        return int(parts[1])
    return None


def _collect_runtime() -> dict:
    """Assemble the ``runtime`` block of the telemetry payload."""
    config = cfg()
    session_dir = config.session_directory
    session_files = 0
    if session_dir.is_dir():
        session_files = sum(1 for f in session_dir.iterdir() if f.suffix == ".session")

    # Runtime import avoids circular dependencies at module load time.
    from src.client.connection import get_active_session_count

    return {
        "sessions": get_active_session_count(),
        "session_files": session_files,
        "setup_sessions": 0,  # not yet tracked
        "memory_kb": _get_rss_kb(),
    }


def gather_payload() -> dict:
    """Return a self-contained dictionary that can be sent as a heartbeat."""
    from src.server_components.session_acl import principal_count, read_only_count

    snap = metrics.snapshot()

    payload = {
        "v": 1,
        "iid": get_instance_id(),
        "ts": int(time.time()),
        "started_at": _started_at,
        "ver": __version__,
        "os": f"{sys.platform} {platform.machine()}",
        "py": f"{sys.version_info.major}.{sys.version_info.minor}",
        "features": _collect_features(),
        "runtime": _collect_runtime(),
        "counters": {
            "total_calls": snap["total_calls"],
            "errors": snap["errors"],
            "flood_waits": snap["flood_waits"],
        },
        "tools": snap["tools"],
    }

    # ACL depth is added to the features block, not sourced from config so we
    # call the new methods on SessionACL.
    payload["features"]["acl_principals"] = principal_count()
    payload["features"]["acl_read_only"] = read_only_count()

    return payload


# ---------------------------------------------------------------------------
# Send (synchronous — wrapped in a thread by the async loop)
# ---------------------------------------------------------------------------


def send_heartbeat(payload: dict | None = None) -> None:
    """Transmit a telemetry heartbeat.

    When ``MCP_TELEMETRY_DEBUG=1`` the payload is logged to stderr instead of
    being sent.  Network errors are silently logged at DEBUG level.
    """
    if not should_send():
        return

    if payload is None:
        payload = gather_payload()

    # Debug mode — print to stderr instead of sending
    if os.environ.get("MCP_TELEMETRY_DEBUG", "").strip() == "1":
        print("TELEMETRY", json.dumps(payload, indent=2), file=sys.stderr)
        return

    # Fire the POST (blocking in this thread — caller runs us in a thread)
    import urllib.error
    import urllib.request

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        TELEMETRY_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as exc:
        logger.debug("Telemetry: HTTP %s from %s", exc.code, TELEMETRY_ENDPOINT)
    except (OSError, urllib.error.URLError) as exc:
        logger.debug("Telemetry: network error — %s", exc)


# ---------------------------------------------------------------------------
# Asynchronous telemetry loop (started in server.py lifespan)
# ---------------------------------------------------------------------------


async def telemetry_task() -> None:
    """Background ``asyncio`` task that sends heartbeats periodically."""
    if not should_send():
        logger.info("Telemetry: disabled (DO_NOT_TRACK=1)")
        return

    logger.info("Telemetry: enabled (disable with DO_NOT_TRACK=1)")

    # Send an immediate heartbeat on startup.
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, send_heartbeat)
    except Exception:
        logger.debug("Telemetry: startup heartbeat failed", exc_info=True)

    # Subsequent heartbeats at the configured interval.
    raw_interval = os.environ.get("MCP_TELEMETRY_INTERVAL", "")
    interval = _DEFAULT_INTERVAL_SECONDS
    if raw_interval.strip():
        with contextlib.suppress(ValueError):
            interval = max(int(raw_interval.strip()), _MIN_INTERVAL_SECONDS)

    while True:
        try:
            await asyncio.sleep(interval)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, send_heartbeat)
        except asyncio.CancelledError:
            # Best-effort shutdown heartbeat — fires on graceful SIGTERM
            # (e.g. docker stop, systemctl stop, MCP client disconnect).
            # Tagged with features.shutdown=True so the collector can
            # distinguish it from a startup or periodic heartbeat.
            try:
                shutdown_payload = gather_payload()
                shutdown_payload["features"]["shutdown"] = True
                _loop = asyncio.get_running_loop()
                await _loop.run_in_executor(None, send_heartbeat, shutdown_payload)
            except Exception:
                logger.debug("Telemetry: shutdown heartbeat failed", exc_info=True)
            break
        except Exception:
            logger.debug("Telemetry: periodic heartbeat failed", exc_info=True)


# ---------------------------------------------------------------------------
# Server-config integration
# ---------------------------------------------------------------------------

# ``server_config.py`` reads ``DO_NOT_TRACK`` as an env-var-only check (no
# pydantic field needed).  The check is trivial and lives in ``should_send()``
# above — the config module does not need a dedicated property.
