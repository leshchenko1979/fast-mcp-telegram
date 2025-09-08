import asyncio
import base64
import secrets
import time
import traceback
from contextvars import ContextVar

from loguru import logger
from telethon import TelegramClient

from ..config.logging import format_diagnostic_info
from ..config.server_config import get_config
from ..config.settings import API_HASH, API_ID, SESSION_DIR, SESSION_PATH

_singleton_client = None

# Token-based session management (use unified server config)
MAX_ACTIVE_SESSIONS = get_config().max_active_sessions

_current_token: ContextVar[str | None] = ContextVar("_current_token", default=None)
_session_cache: dict[str, tuple[TelegramClient, float]] = {}
_cache_lock = asyncio.Lock()


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
            client = TelegramClient(session_path, API_ID, API_HASH)
            await client.connect()

            if not await client.is_user_authorized():
                logger.error(
                    f"Session not authorized for token {token[:8]}... Please authenticate first"
                )
                raise Exception(f"Session not authorized for token {token[:8]}...")

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


async def get_client() -> TelegramClient:
    global _singleton_client
    if _singleton_client is None:
        try:
            client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                logger.error("Session not authorized. Please run cli_setup.py first")
                raise Exception("Session not authorized")
            _singleton_client = client
        except Exception as e:
            logger.error(
                "Failed to create Telegram client",
                extra={
                    "diagnostic_info": format_diagnostic_info(
                        {
                            "error": {
                                "type": type(e).__name__,
                                "message": str(e),
                                "traceback": traceback.format_exc(),
                            },
                            "config": {
                                "session_path": str(SESSION_PATH),
                                "api_id_set": bool(API_ID),
                                "api_hash_set": bool(API_HASH),
                            },
                        }
                    )
                },
            )
            raise
    return _singleton_client


async def get_connected_client() -> TelegramClient:
    """
    Get a connected Telegram client, ensuring the connection is established.
    Supports both legacy singleton mode and token-based sessions.

    Returns:
        Connected TelegramClient instance

    Raises:
        Exception: If connection cannot be established
    """
    # Check for current token context
    token = _current_token.get(None)

    if token is None:
        # Legacy behavior: use singleton client
        client = await get_client()
    else:
        # Token-based behavior: get client for specific token
        client = await _get_client_by_token(token)

    if not await ensure_connection(client):
        raise Exception("Failed to establish connection to Telegram")
    return client


async def ensure_connection(client: TelegramClient) -> bool:
    try:
        if not client.is_connected():
            logger.warning("Client disconnected, attempting to reconnect...")
            await client.connect()
            if not await client.is_user_authorized():
                logger.error("Client reconnected but not authorized")
                return False
            logger.info("Successfully reconnected client")
        return client.is_connected()
    except Exception as e:
        logger.error(
            f"Error ensuring connection: {e}",
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


async def cleanup_client():
    """Clean up the singleton client (legacy behavior)."""
    global _singleton_client
    if _singleton_client is not None:
        try:
            await _singleton_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting singleton client: {e}")
        _singleton_client = None


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


async def cleanup_all_clients():
    """Clean up both singleton and cached clients."""
    await cleanup_client()
    await cleanup_session_cache()
