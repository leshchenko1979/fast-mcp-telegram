import asyncio
import base64
import logging
import secrets
import time
import traceback
from contextvars import ContextVar

from telethon import TelegramClient

from ..config.logging import format_diagnostic_info
from ..config.server_config import get_config
from ..config.settings import API_HASH, API_ID, SESSION_DIR

logger = logging.getLogger(__name__)


class SessionNotAuthorizedError(Exception):
    """Exception raised when a Telegram session is not authorized."""


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


async def _get_client_by_token(token: str) -> TelegramClient:
    """Get or create a TelegramClient instance for the given token."""
    async with _cache_lock:
        current_time = time.time()

        # Check if client is already cached
        if token in _session_cache:
            client, _ = _session_cache[token]
            # Update access time
            _session_cache[token] = (client, current_time)
            return client

        # Create new client for token
        session_path = SESSION_DIR / f"{token}.session"

        try:
            client = TelegramClient(
                session_path,
                API_ID,
                API_HASH,
                entity_cache_limit=get_config().entity_cache_limit,
            )
            await client.connect()

            if not await client.is_user_authorized():
                logger.error(
                    f"Session not authorized for token {token[:8]}... Please authenticate first"
                )
                raise SessionNotAuthorizedError(
                    f"Session not authorized for token {token[:8]}..."
                )

            # Implement LRU eviction if cache is full
            if len(_session_cache) >= MAX_ACTIVE_SESSIONS:
                logger.warning(
                    f"Session cache full ({len(_session_cache)}/{MAX_ACTIVE_SESSIONS}), performing LRU eviction"
                )

                # Find oldest entry (LRU)
                oldest_token = min(
                    _session_cache.keys(), key=lambda k: _session_cache[k][1]
                )

                # Disconnect oldest client
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

                # Remove from cache
                del _session_cache[oldest_token]
                logger.info(
                    f"Evicted LRU session for token {oldest_token[:8]}... Cache now has {len(_session_cache)} sessions"
                )

            # Store new client in cache
            _session_cache[token] = (client, current_time)
            logger.info(f"Created new session for token {token[:8]}...")

            return client

        except Exception as e:
            # Auto-delete invalid session files on auth errors
            error_message = str(e).lower()
            is_auth_error = any(
                keyword in error_message
                for keyword in [
                    "auth",
                    "session",
                    "unauthorized",
                    "authorization",
                    "password",
                    "2fa",
                    "code",
                    "invalid",
                ]
            )

            if is_auth_error and session_path.exists():
                try:
                    session_path.unlink()
                    logger.warning(
                        f"Auto-deleted invalid session file for token {token[:8]}... due to auth error"
                    )
                except Exception as delete_error:
                    logger.warning(
                        f"Failed to delete invalid session file: {delete_error}"
                    )

            logger.error(
                f"Failed to create client for token {token[:8]}...",
                extra={
                    "diagnostic_info": format_diagnostic_info(
                        {
                            "error": {
                                "type": type(e).__name__,
                                "message": str(e),
                                "traceback": traceback.format_exc(),
                            },
                            "token": token[:8] + "...",
                            "session_path": str(session_path),
                            "auto_deleted": is_auth_error and session_path.exists(),
                        }
                    )
                },
            )
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
        raise Exception("Failed to establish connection to Telegram")
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
            if not await client.is_user_authorized():
                logger.error(
                    f"Client reconnected but not authorized for token {token[:8]}..."
                )
                await _record_connection_failure(token)
                return False
            logger.info(f"Successfully reconnected client for token {token[:8]}...")

            # Reset failure count on successful connection
            async with _failure_lock:
                _connection_failures.pop(token, None)

        return client.is_connected()
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
                f"Fatal session error for token {token[:8]}...: {e}. Removing session and stopping retries."
            )
            # Remove session file immediately to prevent loop
            session_path = SESSION_DIR / f"{token}.session"
            if session_path.exists():
                try:
                    session_path.unlink()
                    logger.info(f"Removed fatal session file for token {token[:8]}...")
                except Exception as del_e:
                    logger.warning(f"Failed to remove fatal session file: {del_e}")

            # Remove from cache to force re-initialization (which will fail auth check)
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


async def cleanup_failed_sessions():
    """Clean up sessions that have too many connection failures."""
    async with _failure_lock:
        current_time = time.time()
        failed_tokens = []

        for token, (failure_count, last_failure_time) in _connection_failures.items():
            # If more than 10 failures and last failure was more than 1 hour ago, clean up
            if failure_count >= 10 and (current_time - last_failure_time) > 3600:
                failed_tokens.append(token)

        for token in failed_tokens:
            # Remove from failure tracking
            _connection_failures.pop(token, None)

            # Remove from session cache and disconnect
            if token in _session_cache:
                client, _ = _session_cache.pop(token)
                try:
                    await client.disconnect()
                    logger.info(f"Disconnected failed session for token {token[:8]}...")
                except Exception as e:
                    logger.warning(
                        f"Error disconnecting failed session {token[:8]}...: {e}"
                    )

            # Remove session file
            session_path = SESSION_DIR / f"{token}.session"
            if session_path.exists():
                try:
                    session_path.unlink()
                    logger.info(f"Removed failed session file for token {token[:8]}...")
                except Exception as e:
                    logger.warning(
                        f"Error removing failed session file {token[:8]}...: {e}"
                    )

            logger.info(
                f"Cleaned up failed session for token {token[:8]}... (had {failure_count} failures)"
            )


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
            stats["failure_details"][token[:8] + "..."] = {
                "failure_count": failure_count,
                "hours_since_last_failure": (current_time - last_failure_time) / 3600,
                "circuit_breaker_open": failure_count >= 5
                and (current_time - last_failure_time) < 300,
            }

        return stats
