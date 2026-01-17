"""
Bot session restrictions for MCP tools.

This module provides decorators to restrict non-bridge tools for bot sessions,
ensuring bots can only use the MTProto bridge functionality.
"""

import logging
from functools import wraps

from src.client.connection import get_connected_client
from src.utils.error_handling import log_and_build_error

logger = logging.getLogger(__name__)


def restrict_non_bridge_for_bot_sessions(operation_name: str):
    """
    Decorator to restrict non-bridge tools for bot sessions.

    This decorator checks if the current session is a bot account.
    If it is, it returns a structured error instead of executing the tool.
    Only the MTProto bridge should be accessible to bots.

    Args:
        operation_name: Name of the operation being restricted (for error reporting)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                client = await get_connected_client()

                # Create a stable cache key from the session filename
                # This avoids repeated get_me() calls for the same session
                cache_key = "unknown"
                try:
                    if hasattr(client.session, "filename") and client.session.filename:
                        cache_key = str(client.session.filename)
                except Exception:
                    # Fallback to a generic key if we can't get the filename
                    cache_key = f"session_{id(client.session)}"

                # Check if this is a bot session using cached function
                is_bot = await _is_bot_session_async(cache_key, client)

                if is_bot:
                    logger.info(
                        f"Blocking {operation_name} for bot session",
                        extra={"operation": operation_name, "cache_key": cache_key},
                    )
                    return log_and_build_error(
                        operation=operation_name,
                        error_message="This tool is disabled for bot sessions. Use the MTProto bridge instead.",
                        params=None,
                    )

                # Not a bot session - proceed with the original function
                return await func(*args, **kwargs)

            except Exception as e:
                logger.error(
                    f"Error in bot restriction check for {operation_name}: {e}"
                )
                # If there's an error in the bot check, allow the operation to proceed
                # This ensures we don't break functionality due to bot detection issues
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# Cache to avoid repeated get_me() calls for the same session
# Using a simple dict since functools.cache doesn't work with async functions
_is_bot_cache: dict[str, bool] = {}


async def _is_bot_session_async(cache_key: str, client) -> bool:
    """
    Check if a session is a bot session with manual caching for async operations.

    This function uses manual caching since functools.cache doesn't work with async functions.
    functools.cache would cache coroutine objects instead of the actual boolean results.
    """
    # Check cache first
    if cache_key in _is_bot_cache:
        logger.debug(f"Cache hit for bot detection: {cache_key}")
        return _is_bot_cache[cache_key]

    try:
        # Cache miss - need to check if this is a bot session
        me = await client.get_me()
        is_bot = bool(getattr(me, "bot", False))
        _is_bot_cache[cache_key] = is_bot

        logger.debug(
            f"Detected {'bot' if is_bot else 'user'} session for {cache_key}",
            extra={"cache_key": cache_key, "is_bot": is_bot},
        )

        return is_bot
    except Exception as e:
        logger.warning(f"Failed to get user info for bot check: {e}")
        # If we can't determine, assume it's a user session (safer)
        is_bot = False
        _is_bot_cache[cache_key] = is_bot
        return is_bot


def clear_bot_cache():
    """Clear the bot detection cache. Useful for testing."""
    global _is_bot_cache
    _is_bot_cache.clear()
    logger.debug("Cleared bot detection cache")
