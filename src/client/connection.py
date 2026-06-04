import asyncio
import base64
import contextlib
import inspect
import logging
import platform
import secrets
import time
import traceback
from contextvars import ContextVar
from pathlib import Path

from telethon import TelegramClient
from telethon import errors as tg_errors
from telethon.tl import functions

from ..config.logging import format_diagnostic_info
from ..config.server_config import PROJECT_ROOT, get_config
from ..config.settings import SESSION_DIR
from ..server_components.session_token_validation import (
    InvalidSessionTokenError,
    validated_session_file_path,
)
from ..utils.proxy import build_mtproto_client_args

_PKG_VERSION: str | None = None
_DEVICE_MODEL: str | None = None

logger = logging.getLogger(__name__)


def _get_app_version() -> str:
    global _PKG_VERSION
    if _PKG_VERSION is not None:
        return _PKG_VERSION
    try:
        from importlib.metadata import version

        _PKG_VERSION = version("fast-mcp-telegram")
    except Exception:
        _PKG_VERSION = "0.0.0"
    return _PKG_VERSION


def _get_device_model() -> str:
    global _DEVICE_MODEL
    if _DEVICE_MODEL is not None:
        return _DEVICE_MODEL
    try:
        system = platform.uname()
        _DEVICE_MODEL = f"{system.system} {system.machine}"
    except Exception:
        _DEVICE_MODEL = "Unknown"
    return _DEVICE_MODEL


class SessionNotAuthorizedError(Exception):
    """Exception raised when a Telegram session is not authorized."""


class TelegramTransportError(ConnectionError):
    """Session has credentials but Telegram (or MTProto proxy) cannot be reached."""


async def verify_authorized_connection(client: TelegramClient) -> None:
    """
    Confirm the session has an auth key and Telegram accepts it.

    Telethon's ``is_user_authorized()`` treats any RPC error as logged out, so
    network or proxy failures are misreported as unauthorized. This helper
    only raises SessionNotAuthorizedError for real auth failures.
    """
    auth_key = getattr(client.session, "auth_key", None)
    if not auth_key:
        client._authorized = False  # type: ignore[attr-defined]
        raise SessionNotAuthorizedError(
            "No credentials in session; authenticate first."
        )

    try:
        await client(functions.updates.GetStateRequest())
    except (tg_errors.UnauthorizedError, tg_errors.AuthKeyError) as e:
        client._authorized = False  # type: ignore[attr-defined]
        raise SessionNotAuthorizedError(
            f"Telegram rejected the session ({type(e).__name__})."
        ) from e
    except tg_errors.FloodError as e:
        client._authorized = None  # type: ignore[attr-defined]
        raise TelegramTransportError(
            "Telegram rate-limited the connection; wait and retry."
        ) from e
    except tg_errors.RPCError as e:
        client._authorized = None  # type: ignore[attr-defined]
        raise TelegramTransportError(
            "Cannot reach Telegram or the MTProto proxy is misconfigured or down "
            f"({type(e).__name__}: {e}). Check network and MTPROTO_PROXY."
        ) from e
    except (OSError, TimeoutError) as e:
        client._authorized = None  # type: ignore[attr-defined]
        raise TelegramTransportError(
            "Cannot reach Telegram; check network connectivity and MTProto proxy "
            "if MTPROTO_PROXY is set."
        ) from e
    else:
        client._authorized = True  # type: ignore[attr-defined]


# Token-based session management (use unified server config)
MAX_ACTIVE_SESSIONS = get_config().max_active_sessions

_current_token: ContextVar[str | None] = ContextVar("_current_token", default=None)
_session_cache: dict[str, tuple[TelegramClient, float]] = {}
_cache_lock = asyncio.Lock()

# Connection failure tracking for circuit breaker and backoff
_connection_failures: dict[
    str, tuple[int, float]
] = {}  # token -> (failure_count, last_failure_time)
_failure_lock = asyncio.Lock()

# Idle session cleanup
MAX_IDLE_TIME = 1800  # 30 minutes in seconds


async def cleanup_idle_sessions():
    """Disconnect sessions that haven't been used for MAX_IDLE_TIME."""
    async with _cache_lock:
        current_time = time.time()
        idle_tokens = []
        default_token = get_config().session_name

        for token, (_client, last_access) in _session_cache.items():
            # Skip cleanup for default session to preserve legacy behavior
            if token == default_token:
                continue

            if current_time - last_access > MAX_IDLE_TIME:
                idle_tokens.append(token)

        for token in idle_tokens:
            client, last_access = _session_cache[token]
            try:
                await client.disconnect()
                logger.info(
                    f"Disconnected idle session for token {token[:8]}... (idle for {(current_time - last_access) / 60:.1f}m)"
                )
            except Exception as e:
                logger.warning(f"Error disconnecting idle session {token[:8]}...: {e}")
            # Remove from cache
            del _session_cache[token]

        if idle_tokens:
            logger.info(
                f"Cleaned up {len(idle_tokens)} idle sessions. Cache now has {len(_session_cache)} sessions"
            )


def generate_bearer_token() -> str:
    """Generate a cryptographically secure bearer token for session management."""
    # Generate 32 bytes (256-bit) of random data
    token_bytes = secrets.token_bytes(32)
    # Encode as URL-safe base64 and strip padding
    return base64.urlsafe_b64encode(token_bytes).decode().rstrip("=")


def set_request_token(token: str | None) -> None:
    """Set the bearer token for the current request context."""
    _current_token.set(token)


def get_request_token() -> str | None:
    """Return the bearer token for the current context, or None if unset (default session applies)."""
    return _current_token.get(None)


_AUTH_ERROR_SUBSTRINGS = frozenset(
    (
        "auth",
        "session",
        "unauthorized",
        "authorization",
        "password",
        "2fa",
        "code",
        "invalid",
    )
)


def _error_message_suggests_auth_issue(exc: BaseException) -> bool:
    lowered = str(exc).lower()
    return any(s in lowered for s in _AUTH_ERROR_SUBSTRINGS)


def _resolve_session_path_for_token(token: str) -> Path:
    """Map token to Telethon session path.

    When auth is disabled (stdio / http-no-auth), the configured ``session_name``
    (e.g. ``telegram``) is not a bearer token — use ``config.session_path`` directly.
    """
    config = get_config()
    if config.disable_auth and token == config.session_name:
        return config.session_path
    return validated_session_file_path(SESSION_DIR, token)


def _session_file_exists(session_path: Path) -> bool:
    """True if a Telethon session file exists for ``session_path`` (with or without .session suffix)."""
    if session_path.suffix == ".session":
        return session_path.is_file()
    with_suffix = session_path.with_suffix(".session")
    return with_suffix.is_file() or session_path.is_file()


def _unlink_session_file(session_path: Path) -> None:
    """Remove the on-disk Telethon session file for ``session_path``."""
    if session_path.suffix == ".session":
        session_path.unlink(missing_ok=True)
        return
    session_path.with_suffix(".session").unlink(missing_ok=True)
    if session_path.is_file():
        session_path.unlink(missing_ok=True)


async def _safe_disconnect_after_verify_failure(client: TelegramClient) -> None:
    try:
        if client.is_connected():
            await client.disconnect()
    except Exception as disc_e:
        logger.debug("Disconnect after failed session verification: %s", disc_e)


async def _connect_client_and_verify_or_cleanup(
    client: TelegramClient, token: str, bot_api_token: str = ""
) -> None:
    try:
        # If bot_api_token is set, client.start() handles both connection
        # and non-interactive authentication (no OTP needed).
        # Otherwise, connect explicitly and verify the existing session.
        if bot_api_token:
            result = client.start(bot_token=bot_api_token)
            if inspect.isawaitable(result):
                await result
        else:
            await client.connect()

        await verify_authorized_connection(client)

        if bot_api_token:
            logger.info("Bot API token authentication succeeded!")
    except SessionNotAuthorizedError as e:
        await _safe_disconnect_after_verify_failure(client)
        logger.error(
            f"Session not authorized for token {token[:8]}... Please authenticate first"
        )
        raise SessionNotAuthorizedError(
            f"Session not authorized for token {token[:8]}..."
        ) from e
    except Exception:
        await _safe_disconnect_after_verify_failure(client)
        raise


async def _evict_lru_if_session_cache_full() -> None:
    """Evict least-recently-used session if cache is at capacity. Caller must hold _cache_lock."""
    if len(_session_cache) < MAX_ACTIVE_SESSIONS:
        return
    logger.warning(
        f"Session cache full ({len(_session_cache)}/{MAX_ACTIVE_SESSIONS}), performing LRU eviction"
    )
    oldest_token = min(_session_cache.keys(), key=lambda k: _session_cache[k][1])
    oldest_client, last_access = _session_cache[oldest_token]
    try:
        await oldest_client.disconnect()
        logger.info(
            f"Disconnected LRU client for token {oldest_token[:8]}... (last accessed {time.ctime(last_access)})"
        )
    except Exception as e:
        logger.warning(
            f"Error disconnecting LRU client for token {oldest_token[:8]}...: {e}"
        )
    del _session_cache[oldest_token]
    logger.info(
        f"Evicted LRU session for token {oldest_token[:8]}... Cache now has {len(_session_cache)} sessions"
    )


async def _build_telegram_client_for_token(
    session_path: Path, token: str
) -> TelegramClient:
    _cfg = get_config()
    raw_api = (_cfg.api_id or "").strip()
    if not raw_api:
        raise ValueError(
            "Telegram API_ID is missing or empty. Set API_ID in .env at the project root "
            f"({PROJECT_ROOT}) and restart the MCP server "
            f"(process cwd was {Path.cwd()})."
        )
    try:
        api_id_int = int(raw_api)
    except ValueError as e:
        raise ValueError(
            f"Telegram API_ID must be a non-empty integer string; got {_cfg.api_id!r}."
        ) from e
    raw_hash = (_cfg.api_hash or "").strip()
    if not raw_hash:
        raise ValueError(
            "Telegram API_HASH is missing or empty. Set API_HASH in .env at the project root "
            f"({PROJECT_ROOT}) and restart the MCP server "
            f"(process cwd was {Path.cwd()})."
        )
    client_kwargs = {
        "session": session_path,
        "api_id": api_id_int,
        "api_hash": raw_hash,
        "entity_cache_limit": _cfg.entity_cache_limit,
        "app_version": _get_app_version(),
        "device_model": _get_device_model(),
    }
    client_kwargs |= build_mtproto_client_args(_cfg.mtproto_proxy, logger.info)
    client = TelegramClient(**client_kwargs)
    await _connect_client_and_verify_or_cleanup(client, token, _cfg.bot_api_token)
    return client


def _log_client_creation_failed(
    session_path: Path, token: str, exc: BaseException
) -> None:
    logger.error(
        f"Failed to create client for token {token[:8]}...",
        extra={
            "diagnostic_info": format_diagnostic_info(
                {
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                    "token": f"{token[:8]}...",
                    "session_path": str(session_path),
                }
            )
        },
    )


async def _get_client_by_token(token: str) -> TelegramClient:
    """Get or create a TelegramClient instance for the given token."""
    async with _cache_lock:
        current_time = time.time()
        if token in _session_cache:
            client, _ = _session_cache[token]
            _session_cache[token] = (client, current_time)
            return client

        try:
            session_path = _resolve_session_path_for_token(token)
        except InvalidSessionTokenError as e:
            raise SessionNotAuthorizedError("Invalid bearer token") from e

        try:
            client = await _build_telegram_client_for_token(session_path, token)
            await _evict_lru_if_session_cache_full()
            _session_cache[token] = (client, current_time)
            logger.info(f"Created new session for token {token[:8]}...")
            return client
        except Exception as e:
            if _error_message_suggests_auth_issue(e):
                logger.warning(
                    f"Session file for token {token[:8]}... is invalid — "
                    "keep file for re-authorization via setup page"
                )
            _log_client_creation_failed(session_path, token, e)
            raise


async def get_connected_client() -> TelegramClient:
    """
    Get a connected Telegram client, ensuring the connection is established.
    Supports both legacy singleton mode and token-based sessions via unified cache.

    Returns:
        Connected TelegramClient instance

    Raises:
        Exception: If connection cannot be established
    """
    # Check for current token context
    token = _current_token.get(None)

    if token is None:
        # Legacy/Default behavior: use configured session name as token
        token = get_config().session_name

    # Get client for token (default or specific)
    client = await _get_client_by_token(token)

    if not await ensure_connection(client, token):
        raise ConnectionError("Failed to establish connection to Telegram")
    return client


async def ensure_connection(client: TelegramClient, token: str) -> bool:
    """Ensure client connection with exponential backoff and circuit breaker."""
    async with _failure_lock:
        current_time = time.time()
        failure_count, last_failure_time = _connection_failures.get(token, (0, 0))

        # Circuit breaker: if too many recent failures, don't attempt connection
        if (
            failure_count >= 5 and (current_time - last_failure_time) < 300
        ):  # 5 failures in 5 minutes
            logger.warning(
                f"Circuit breaker open for token {token[:8]}... - too many recent failures"
            )
            return False

        # Exponential backoff: wait before retrying
        if failure_count > 0:
            backoff_time = min(2**failure_count, 60)
            wait_time = backoff_time - (current_time - last_failure_time)

            if wait_time > 0:
                logger.info(
                    f"Exponential backoff: waiting {wait_time:.1f}s before retry for token {token[:8]}..."
                )
                await asyncio.sleep(wait_time)

    try:
        if not client.is_connected():
            logger.warning(
                f"Client disconnected for token {token[:8]}..., attempting to reconnect..."
            )
            await client.connect()
            await verify_authorized_connection(client)
            logger.info(f"Successfully reconnected client for token {token[:8]}...")

            # Reset failure count on successful connection
            async with _failure_lock:
                _connection_failures.pop(token, None)

            # Touch session file so mtime reflects last-active (for inactivity cleanup)
            with contextlib.suppress(InvalidSessionTokenError, OSError):
                _resolve_session_path_for_token(token).with_suffix(".session").touch(
                    exist_ok=True
                )

        return client.is_connected()
    except SessionNotAuthorizedError:
        logger.error(f"Client reconnected but not authorized for token {token[:8]}...")
        await _record_connection_failure(token)
        raise
    except TelegramTransportError:
        await _record_connection_failure(token)
        raise
    except Exception as e:
        # Check for fatal session errors that shouldn't be retried
        error_msg = str(e).lower()
        is_fatal = any(
            pattern in error_msg
            for pattern in [
                "wrong session id",
                "server replied with a wrong session id",
                "auth_key_unregistered",
                "session_revoked",
                "user_deactivated",
            ]
        )

        if is_fatal:
            logger.critical(
                f"Fatal session error for token {token[:8]}...: {e}. "
                "Session file kept for re-authorization via setup page."
            )

            # Remove from cache so caller gets a fresh client attempt next time
            async with _cache_lock:
                _session_cache.pop(token, None)

            # Don't record as a connection failure, just fail immediately
            return False

        await _record_connection_failure(token)
        logger.error(
            f"Error ensuring connection for token {token[:8]}...: {e}",
            extra={
                "diagnostic_info": format_diagnostic_info(
                    {
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e),
                            "traceback": traceback.format_exc(),
                        }
                    }
                )
            },
        )
        return False


async def _record_connection_failure(token: str) -> None:
    """Record a connection failure for backoff and circuit breaker logic."""
    async with _failure_lock:
        current_time = time.time()
        failure_count, _ = _connection_failures.get(token, (0, 0))
        _connection_failures[token] = (failure_count + 1, current_time)
        logger.warning(
            f"Recorded connection failure #{failure_count + 1} for token {token[:8]}..."
        )


async def _cleanup_inactive_sessions() -> int:
    """Delete .session files not modified in >inactive_session_days days.

    Skips the configured default session. Uses file mtime to determine
    inactivity. Returns count of deleted sessions.
    Set TELEGRAM_INACTIVE_SESSION_DAYS=0 (env var) to disable.
    """
    config = get_config()
    inactive_days = config.inactive_session_days
    if inactive_days <= 0:
        return 0

    cutoff = time.time() - inactive_days * 86400
    default_session = config.session_name
    deleted = 0

    for session_file in SESSION_DIR.glob("*.session"):
        if not session_file.is_file():
            continue

        # Never delete the configured default session
        if session_file.stem == default_session:
            continue

        try:
            mtime = session_file.stat().st_mtime
        except OSError:
            continue

        if mtime > cutoff:
            continue

        # Re-check mtime just before delete (TOCTOU guard)
        try:
            current_mtime = session_file.stat().st_mtime
            if current_mtime > cutoff:
                continue
        except OSError:
            continue

        try:
            session_file.unlink()
            logger.info(
                f"Deleted inactive session file: {session_file.name} "
                f"(mtime: {time.ctime(mtime)})"
            )
            deleted += 1
        except OSError as e:
            logger.warning(
                f"Error deleting inactive session file {session_file.name}: {e}"
            )

    if deleted:
        logger.info(f"Cleaned up {deleted} inactive session(s)")
    return deleted


async def cleanup_session_cache():
    """Clean up all cached client sessions."""
    async with _cache_lock:
        for token, (client, _) in _session_cache.items():
            try:
                await client.disconnect()
                logger.info(f"Disconnected cached client for token {token[:8]}...")
            except Exception as e:
                logger.warning(
                    f"Error disconnecting cached client for token {token[:8]}...: {e}"
                )

    _session_cache.clear()
    logger.info("Cleaned up all session cache entries")


async def get_session_health_stats() -> dict:
    """Get health statistics for all sessions."""
    async with _failure_lock:
        current_time = time.time()
        stats = {
            "total_sessions": len(_session_cache),
            "failed_sessions": len(_connection_failures),
            "failure_details": {},
        }

        for token, (failure_count, last_failure_time) in _connection_failures.items():
            stats["failure_details"][f"{token[:8]}..."] = {
                "failure_count": failure_count,
                "hours_since_last_failure": (current_time - last_failure_time) / 3600,
                "circuit_breaker_open": failure_count >= 5
                and (current_time - last_failure_time) < 300,
            }

        return stats
