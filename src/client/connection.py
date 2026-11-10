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
from functools import lru_cache
from pathlib import Path

from telethon import TelegramClient
from telethon import errors as tg_errors
from telethon.tl import functions

from ..config.logging import format_diagnostic_info
from ..config.server_config import PROJECT_ROOT, ServerMode, cfg
from ..server_components.session_token_validation import (
    InvalidSessionTokenError,
    validated_session_file_path,
)
from ..utils.proxy import build_mtproto_client_args

# S3 session storage — lazy import (only when S3_SESSION_STORAGE=true)
s3_session = None  # Imported lazily in is_s3_enabled()

logger = logging.getLogger(__name__)

# Global download lock — serializes S3 downloads. Only held for S3 download (~200ms),
# NOT for Telegram I/O (2-5s). Acceptable for v1.
# Lock ordering: _download_lock → _cache_lock.
# Never acquire _download_lock while holding _cache_lock.
_download_lock = asyncio.Lock()


def validate_api_credentials() -> None:
    """Validate Telegram API credentials at startup.

    Raises ValueError if credentials are missing when required (bot token mode or HTTP auth).
    Logs warning if credentials are missing in other modes.
    """
    config = cfg()

    # Bot token mode requires API credentials for auto-authentication
    if config.bot_api_token:
        if not config.api_id or not config.api_id.strip():
            raise ValueError(
                "Telegram API_ID is required when using bot_api_token. "
                "Set API_ID in .env at the project root or via --api-id argument."
            )
        if not config.api_hash or not config.api_hash.strip():
            raise ValueError(
                "Telegram API_HASH is required when using bot_api_token. "
                "Set API_HASH in .env at the project root or via --api-hash argument."
            )
        logger.info("✓ Telegram API credentials validated")

    # HTTP auth mode should have credentials (warn if missing)
    elif config.server_mode == ServerMode.HTTP_AUTH and (
        not config.api_id or not config.api_hash
    ):
        logger.warning(
            "⚠️ HTTP_AUTH mode without API_ID/API_HASH - "
            "web setup and session creation will fail until credentials are configured"
        )


@lru_cache(maxsize=1)
def _get_app_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("fast-mcp-telegram")
    except PackageNotFoundError:
        return "0.0.0"
    except Exception:
        logger.exception(
            "Unexpected error while resolving package version for fast-mcp-telegram"
        )
        return "0.0.0"


@lru_cache(maxsize=1)
def _get_device_model() -> str:
    try:
        system = platform.uname()
        return f"{system.system} {system.machine}"
    except OSError:
        return "Unknown"
    except Exception:
        logger.exception("Unexpected error while resolving device model")
        return "Unknown"


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

_current_token: ContextVar[str | None] = ContextVar("_current_token", default=None)
_session_cache: dict[str, tuple[TelegramClient, float]] = {}
_cache_lock = asyncio.Lock()

# Per-token creation locks — serialise TelegramClient construction per session
# so two concurrent cold-start callers don't both try to open the same .session file.
_creation_locks: dict[str, asyncio.Lock] = {}
_creation_locks_lock = asyncio.Lock()

# Connection failure tracking for circuit breaker and backoff
_connection_failures: dict[
    str, tuple[int, float]
] = {}  # token -> (failure_count, last_failure_time)
_failure_lock = asyncio.Lock()


# --- S3 helpers ---


def is_s3_enabled() -> bool:
    """Check if S3 session storage is enabled. Lazy-imports s3_session on first call."""
    global s3_session
    if not cfg().s3_session_storage:
        return False
    if s3_session is None:
        from .. import s3_session as _s3

        s3_session = _s3
    return True


def _s3_local_path(token: str) -> Path:
    """Local path for S3-downloaded session files. Only used when S3 mode is active."""
    return cfg().session_directory / f"{token}.session"


async def _do_evict_io(token: str, client: TelegramClient) -> None:
    """Checkpoint, disconnect, upload. NO lock held. Always disconnects in finally."""
    local_path = _s3_local_path(token)
    s3_mode = is_s3_enabled()
    checkpoint_ok = False

    try:
        # Checkpoint BEFORE disconnect — Telethon's session file still accessible
        if s3_mode:
            checkpoint_ok = await s3_session.checkpoint_and_upload(token, local_path)
    except Exception as e:
        logger.warning(f"Checkpoint/upload failed for {token[:8]}...: {e}")
    finally:
        # Always disconnect — even if checkpoint/upload failed
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception as e:
            logger.warning(f"Disconnect failed for {token[:8]}...: {e}")
    # Delete local file ONLY after successful checkpoint+upload (outside try/finally)
    if s3_mode and checkpoint_ok and local_path.exists():
        local_path.unlink(missing_ok=True)


async def _evict_session(token: str) -> None:
    """Pop from cache, checkpoint, disconnect, upload to S3, clean up."""
    async with _cache_lock:
        cached = _session_cache.pop(token, None)
    if cached is None:
        return
    client, _ = cached
    await _do_evict_io(token, client)


async def cleanup_idle_sessions():
    """Disconnect sessions that haven't been used for max_idle_time_seconds.

    Snapshot idle tokens under lock, then do I/O outside lock to avoid
    blocking cache operations during disconnect/S3 upload.
    """
    # Phase 1: identify and pop idle tokens under lock
    evict_list: list[tuple[str, TelegramClient, float]] = []
    async with _cache_lock:
        config = cfg()
        max_idle_time = config.max_idle_time_seconds
        if max_idle_time <= 0:
            return
        current_time = time.time()
        default_token = config.session_name

        idle_tokens = [
            token
            for token, (_, last_access) in _session_cache.items()
            if token != default_token and current_time - last_access > max_idle_time
        ]

        for token in idle_tokens:
            client, last_access = _session_cache.pop(token)
            evict_list.append((token, client, last_access))

    # Phase 2: disconnect + S3 upload outside lock
    for token, client, last_access in evict_list:
        try:
            await _do_evict_io(token, client)
            logger.info(
                f"Disconnected idle session for token {token[:8]}... (idle for {(time.time() - last_access) / 60:.1f}m)"
            )
        except Exception as e:
            logger.warning(f"Error disconnecting idle session {token[:8]}...: {e}")

    if evict_list:
        logger.info(
            f"Cleaned up {len(evict_list)} idle sessions. Cache now has {len(_session_cache)} sessions"
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
    config = cfg()
    if config.disable_auth and token == config.session_name:
        return config.session_path
    return validated_session_file_path(config.session_directory, token)


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


async def _build_telegram_client_for_token(
    session_path: Path, token: str
) -> TelegramClient:
    _cfg = cfg()
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


async def _load_session_file_for_token(token: str) -> Path:
    """Resolve or download the session file for *token*.

    In S3 mode: acquire _download_lock, double-check cache, download from S3
    with local fallback, verify integrity. In file mode: just resolve the path.

    Lock discipline: _download_lock is acquired/released here. The caller
    must NOT hold _download_lock when calling this function.
    """
    if is_s3_enabled():
        async with _download_lock:
            # Double-check cache after acquiring download lock
            async with _cache_lock:
                if token in _session_cache:
                    client, _ = _session_cache[token]
                    _session_cache[token] = (client, time.time())
                    return None  # type: ignore[return-value]  # sentinel: cache hit

            try:
                local_path = _resolve_session_path_for_token(token)
            except InvalidSessionTokenError as e:
                raise SessionNotAuthorizedError("Invalid bearer token") from e

            local_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                await s3_session.download(token, local_path)
            except FileNotFoundError as exc:
                raise SessionNotAuthorizedError(token) from exc
            except Exception as e:
                # S3 unavailable — fall back to local file if it exists
                logger.warning(
                    f"S3 download failed for {token[:8]}..., trying local fallback: {e}"
                )
                if not local_path.exists():
                    raise SessionNotAuthorizedError(token) from e
                if not await s3_session.verify_session_integrity(local_path):
                    local_path.unlink(missing_ok=True)
                    raise SessionNotAuthorizedError(token) from e
                logger.info(f"Using local fallback for {token[:8]}...")
            else:
                if not await s3_session.verify_session_integrity(local_path):
                    local_path.unlink(missing_ok=True)
                    raise TelegramTransportError("Downloaded session file is corrupt")
            return local_path
    else:
        try:
            return _resolve_session_path_for_token(token)
        except InvalidSessionTokenError as e:
            raise SessionNotAuthorizedError("Invalid bearer token") from e


async def _get_or_create_creation_lock(token: str) -> asyncio.Lock:
    """Get a per-token lock for serialising client construction.

    Only *building* a new client is serialised per token (whereas the fast
    cache check under ``_cache_lock`` is always concurrent).  Different
    tokens may still build clients in parallel.
    """
    async with _creation_locks_lock:
        if token not in _creation_locks:
            _creation_locks[token] = asyncio.Lock()
        return _creation_locks[token]


async def _get_client_by_token(token: str) -> TelegramClient:
    """Get or create a TelegramClient instance for the given token.

    Concurrency-safe: two concurrent cold-start callers for the same token
    do **not** both create a TelegramClient — the per-token creation lock
    serialises client construction so only one copy of the session file is
    ever opened.
    """
    # ── Fast path: cache hit ──────────────────────────────────────────────
    async with _cache_lock:
        current_time = time.time()
        if token in _session_cache:
            client, _ = _session_cache[token]
            _session_cache[token] = (client, current_time)
            return client

    # ── Per-token lock around the slow path ──────────────────────────────
    # Only one coroutine per token may enter this section at a time.
    # Different tokens may still create clients in parallel.
    creation_lock = await _get_or_create_creation_lock(token)
    async with creation_lock:
        # Double-check cache after acquiring the per-token lock
        async with _cache_lock:
            if token in _session_cache:
                return _session_cache[token][0]

        # Cache miss — load session file (may download from S3)
        local_path = await _load_session_file_for_token(token)
        if local_path is None:
            # Cache hit inside _load_session_file_for_token (double-check after download lock)
            async with _cache_lock:
                return _session_cache[token][0]

        # Build client — safe now (only one coroutine per token)
        try:
            client = await _build_telegram_client_for_token(local_path, token)
        except Exception as e:
            if _error_message_suggests_auth_issue(e):
                logger.warning(
                    f"Session file for token {token[:8]}... is invalid — "
                    "keep file for re-authorization via setup page"
                )
            _log_client_creation_failed(local_path, token, e)
            raise

        # Insert into cache with LRU eviction (double-check for concurrent inserts)
        async with _cache_lock:
            if token in _session_cache:
                existing_client, _ = _session_cache[token]
                if existing_client is not client:
                    logger.info(
                        f"Concurrent request already cached token {token[:8]}..., "
                        "discarding duplicate"
                    )
                    try:
                        if client.is_connected():
                            await client.disconnect()
                    except Exception:
                        pass
                return _session_cache[token][0]

            max_active = cfg().max_active_sessions
            evicted = None
            if len(_session_cache) >= max_active:
                oldest_token = min(_session_cache, key=lambda k: _session_cache[k][1])
                evicted = (oldest_token, _session_cache.pop(oldest_token, None))
                _creation_locks.pop(oldest_token, None)  # cleanup per-token lock
                if evicted[1]:
                    logger.info(f"Evicting LRU session: {oldest_token[:8]}...")
            _session_cache[token] = (client, time.time())

    # ── Eviction I/O outside both locks ──────────────────────────────
    # Catch exceptions so the requesting caller doesn't see an unrelated
    # S3 error for a different session.
    if evicted and evicted[1]:
        evict_token, (evict_client, _) = evicted
        try:
            await _do_evict_io(evict_token, evict_client)
        except Exception as e:
            logger.warning(f"LRU eviction I/O failed for {evict_token[:8]}...: {e}")

    logger.info(f"Created new session for token {token[:8]}...")
    return client


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
        token = cfg().session_name

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
            # In S3 mode, skip — Telethon's mtime isn't meaningful for session persistence
            if not is_s3_enabled():
                with contextlib.suppress(InvalidSessionTokenError, OSError):
                    _resolve_session_path_for_token(token).with_suffix(
                        ".session"
                    ).touch(exist_ok=True)

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

            # Evict from cache (disconnect + S3 upload if enabled)
            await _evict_session(token)

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
    config = cfg()
    inactive_days = config.inactive_session_days
    if inactive_days <= 0:
        return 0

    # S3 mode: skip inactive cleanup. S3 LastModified reflects upload time,
    # not session activity — using it would incorrectly delete active sessions.
    if is_s3_enabled():
        return 0

    cutoff = time.time() - inactive_days * 86400
    default_session = config.session_name
    deleted = 0

    for session_file in config.session_directory.glob("*.session"):
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
    """Clean up all cached client sessions.

    Snapshot all entries + clear under one _cache_lock acquisition, then
    do disconnect I/O outside lock to avoid blocking new cache operations.
    """
    # Phase 1: snapshot + clear under lock
    async with _cache_lock:
        entries = list(_session_cache.items())
        _session_cache.clear()

    # Phase 2: disconnect (and S3 upload if enabled) outside lock
    for token, (client, _) in entries:
        try:
            await _do_evict_io(token, client)
            logger.info(f"Disconnected cached client for token {token[:8]}...")
        except Exception as e:
            logger.warning(
                f"Error disconnecting cached client for token {token[:8]}...: {e}"
            )

    logger.info("Cleaned up all session cache entries")


async def disconnect_and_evict_session(token: str) -> None:
    """Disconnect and remove a single session from the cache by token.

    Used by session deletion flows (e.g. web setup delete) where the
    caller needs the cached client disconnected before removing the
    on-disk session file.
    """
    await _evict_session(token)


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


def get_active_session_count() -> int:
    """Return approximate count of currently cached active Telegram sessions.

    Thread-safe: ``len()`` on a dict is atomic under the GIL; the caller does
    NOT need ``_cache_lock`` for a best-effort read (telemetry purposes).
    """
    return len(_session_cache)
