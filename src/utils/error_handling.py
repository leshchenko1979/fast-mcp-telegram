"""
DRY Error Handling Utilities for Telegram MCP Server.

This module provides standardized error handling patterns to eliminate code duplication
across all tools and server components.
"""

import logging
import traceback
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_current_token = None


def _get_current_token() -> str | None:
    """Safely get current token from connection module."""
    global _current_token
    if _current_token is None:
        try:
            from src.client.connection import _current_token as token_var

            _current_token = token_var
        except ImportError:
            return None
    return _current_token.get(None) if _current_token else None


def _log_at_level(log_level: str, message: str, extra: dict | None = None) -> None:
    """
    Log a message at the specified level using stdlib logging.

    Args:
        log_level: The log level ('error', 'warning', 'info', 'debug')
        message: The message to log
        extra: Extra data to include in the log record
    """
    level_map = {
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }
    numeric_level = level_map.get(log_level.upper(), logging.DEBUG)
    logger.log(numeric_level, message, extra=extra)


def sanitize_params_for_logging(params: dict[str, Any] | None) -> dict[str, Any]:
    """
    Sanitize and truncate parameters for safe logging.

    Args:
        params: Dictionary of parameters to sanitize

    Returns:
        Sanitized parameters safe for logging
    """
    if not params:
        return {}

    # Pre-compile common patterns for performance
    phone_keys = {"phone", "phone_number", "mobile"}
    message_keys = {"message", "new_text", "text"}

    sanitized = {}

    for key, value in params.items():
        key_lower = key.lower()

        # Optimized phone number masking
        if any(phone_key in key_lower for phone_key in phone_keys) and isinstance(
            value, str
        ):
            if len(value) > 5:
                sanitized[key] = f"{value[:3]}***{value[-2:]}"
            else:
                sanitized[key] = "***"
        # Optimized message content truncation
        elif key in message_keys and isinstance(value, str) and len(value) > 100:
            sanitized[key] = f"{value[:100]}... (truncated)"
        # Optimized long text truncation
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = f"{value[:200]}... (truncated)"
        # Optimized other value handling
        else:
            try:
                # Fast path for simple types
                if isinstance(value, int | float | bool | type(None)):
                    sanitized[key] = value
                else:
                    str_value = str(value)
                    if len(str_value) > 500:
                        sanitized[key] = f"{str_value[:500]}... (truncated)"
                    else:
                        sanitized[key] = value
            except Exception:
                sanitized[key] = f"<{type(value).__name__}>"

    return sanitized


def add_logging_metadata(params: dict[str, Any]) -> dict[str, Any]:
    """
    Add consistent metadata to parameter dictionaries for logging.

    Args:
        params: Original parameters

    Returns:
        Parameters with added metadata
    """
    enhanced_params = params.copy()
    enhanced_params.update(
        {
            "timestamp": datetime.now().isoformat(),
            "param_count": len(params),
        }
    )
    return enhanced_params


def is_error_response(result: Any) -> bool:
    """
    Check if a result is an error response.

    Args:
        result: The result to check

    Returns:
        True if result is a structured error response, False otherwise
    """
    return isinstance(result, dict) and "ok" in result and not result["ok"]


def is_list_error_response(result: Any) -> tuple[bool, dict[str, Any] | None]:
    """
    Check if a list result contains an error response.

    Args:
        result: The list result to check

    Returns:
        Tuple of (is_error, error_dict) where error_dict is None if not an error
    """
    if (
        isinstance(result, list)
        and len(result) == 1
        and isinstance(result[0], dict)
        and "ok" in result[0]
        and not result[0]["ok"]
    ):
        return True, result[0]
    return False, None


def build_error_response(
    error_message: str,
    operation: str,
    params: dict[str, Any] | None = None,
    exception: Exception | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """
    Build a standardized error response dictionary.

    Args:
        error_message: Human-readable error message
        operation: Name of the operation that failed
        params: Original parameters for context
        exception: Exception that caused the error (for logging)
        action: Optional action to suggest to the user (e.g., "run_setup")

    Returns:
        Standardized error response dictionary
    """
    error_response = {
        "ok": False,
        "error": error_message,
        "operation": operation,
    }

    if params:
        error_response["params"] = params

    if exception:
        error_response["exception"] = {
            "type": type(exception).__name__,
            "message": str(exception),
        }

    if action:
        error_response["action"] = action

    return error_response


def log_and_build_error(
    operation: str,
    error_message: str,
    params: dict[str, Any] | None = None,
    exception: Exception | None = None,
    log_level: str = "error",
    action: str | None = None,
) -> dict[str, Any]:
    """
    Log an error and build a standardized error response.

    Args:
        operation: Name of the operation that failed
        error_message: Human-readable error message
        params: Original parameters for context
        exception: Exception that caused the error
        log_level: Logging level ('error', 'warning', 'info', etc.)
        action: Optional action to suggest to the user (e.g., "run_setup")

    Returns:
        Standardized error response dictionary
    """
    # Build flattened error info for logging
    log_extra = {
        "operation": operation,
        "error_message": error_message,
    }

    # Add token context if available
    token = _get_current_token()
    if token:
        log_extra["token_prefix"] = f"{token[:8]}..."

    if params:
        log_extra["params"] = sanitize_params_for_logging(params)

    if exception:
        log_extra["error_type"] = type(exception).__name__
        log_extra["exception_message"] = str(exception)
        log_extra["traceback"] = traceback.format_exc()

    # Log the error
    log_message = f"{operation} failed: {error_message}"
    _log_at_level(log_level, log_message, extra=log_extra)

    # Return standardized error response
    return build_error_response(
        error_message=error_message,
        operation=operation,
        params=params,
        exception=exception,
        action=action,
    )


def handle_tool_error(
    result: Any,
    operation: str,
    params: dict[str, Any] | None = None,
    log_level: str = "error",
) -> dict[str, Any] | None:
    """
    Handle error responses from tools with consistent logging and response processing.

    Args:
        result: Result from tool function
        operation: Name of the operation
        params: Original parameters for context
        log_level: Logging level for error messages

    Returns:
        Processed error response if result is an error, None otherwise
    """

    def _log_and_return_error(error_dict: dict[str, Any]) -> dict[str, Any]:
        """Helper function to log an error and return the error dict."""
        log_message = (
            f"{operation} returned error: {error_dict.get('error', 'Unknown error')}"
        )
        _log_at_level(log_level, log_message)
        return error_dict

    # Check for dict error response
    if is_error_response(result):
        return _log_and_return_error(result)

    # Check for list error response (e.g., search_contacts)
    is_list_error, error_dict = is_list_error_response(result)
    if is_list_error:
        return _log_and_return_error(error_dict)

    return None


def check_connection_error(error_text: str) -> dict[str, Any] | None:
    """
    Check for specific connection/session errors and return appropriate response.

    Args:
        error_text: Error message text to check

    Returns:
        Error response dict if connection error detected, None otherwise
    """
    lowered = error_text.lower()

    # Define connection error patterns and their corresponding responses
    error_patterns = [
        {
            "patterns": [
                ("authorization key" in lowered and "two different ip" in lowered),
                ("session file" in lowered and "two different ip" in lowered),
                ("auth key" in lowered and "duplicated" in lowered),
            ],
            "message": "Your Telegram session was invalidated due to concurrent use from different IPs. Please run setup to re-authenticate: python3 setup_telegram.py",
            "action": "run_setup",
        },
        {
            "patterns": [
                ("wrong session id" in lowered),
                ("server replied with a wrong session id" in lowered),
                ("security error" in lowered and "session id" in lowered),
            ],
            "message": "Session ID mismatch detected. Your session may be corrupted or used from multiple locations. Please re-authenticate to get a fresh session.",
            "action": "reauthenticate",
        },
        {
            "patterns": [
                ("connection" in lowered and "failed" in lowered),
                ("network" in lowered and "timeout" in lowered),
            ],
            "message": "Connection error occurred. Please check your internet connection and try again.",
            "action": None,
        },
    ]

    # Check each error pattern
    for error_config in error_patterns:
        if any(error_config["patterns"]):
            return build_error_response(
                error_message=error_config["message"],
                operation="connection_check",
                action=error_config["action"],
            )

    return None


def handle_telegram_errors(
    operation: str, params_key: str = "params", params_func=None
):
    """
    Decorator to handle common Telegram-related exceptions and return standardized error responses.

    This decorator catches common exceptions that can occur during Telegram operations and
    converts them to user-friendly error messages with appropriate actions.

    Args:
        operation: The operation name for error reporting
        params_key: The parameter name in the function that contains the params dict (default: "params")

    Returns:
        Decorated function that handles common Telegram exceptions

    Example:
        @handle_telegram_errors(operation="send_message")
        async def send_message_impl(chat_id: str, message: str, ...):
            # function body - exceptions will be caught and handled
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract params from function arguments or use custom function
            params = None
            if params_func:
                params = params_func(*args, **kwargs)
            elif params_key in kwargs:
                params = kwargs[params_key]
            elif len(args) > 0 and hasattr(args[0], params_key):
                # Check if first arg is self and has params attribute
                params = getattr(args[0], params_key, None)

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if "SessionNotAuthorizedError" in str(type(e)):
                    return log_and_build_error(
                        operation=operation,
                        error_message="Session not authorized. Please authenticate your Telegram session first.",
                        params=params,
                        exception=e,
                        action="authenticate_session",
                    )

                # Handle other common Telegram errors with better messages
                error_msg = str(e).lower()

                # Database/connection errors
                if (
                    "readonly database" in error_msg
                    or "database is locked" in error_msg
                ):
                    return log_and_build_error(
                        operation=operation,
                        error_message="Database error occurred. This may be a temporary server issue. Please try again later.",
                        params=params,
                        exception=e,
                        action="retry",
                    )

                # Network/connection errors
                if any(
                    pattern in error_msg
                    for pattern in ["connection", "network", "timeout", "unreachable"]
                ):
                    return log_and_build_error(
                        operation=operation,
                        error_message="Connection error occurred. Please check your internet connection and try again.",
                        params=params,
                        exception=e,
                        action="retry",
                    )

                # Peer resolution errors
                if "cannot cast" in error_msg or "peer" in error_msg:
                    return log_and_build_error(
                        operation=operation,
                        error_message="Unable to resolve or access the specified chat/user. Please verify the ID is correct and accessible.",
                        params=params,
                        exception=e,
                    )

                # Generic fallback
                return log_and_build_error(
                    operation=operation,
                    error_message=f"Operation failed: {e!s}",
                    params=params,
                    exception=e,
                )
                # Handle other common Telegram errors with better messages
                error_msg = str(e).lower()

                # Database/connection errors
                if (
                    "readonly database" in error_msg
                    or "database is locked" in error_msg
                ):
                    return log_and_build_error(
                        operation=operation,
                        error_message="Database error occurred. This may be a temporary server issue. Please try again later.",
                        params=params,
                        exception=e,
                        action="retry",
                    )

                # Network/connection errors
                if any(
                    pattern in error_msg
                    for pattern in ["connection", "network", "timeout", "unreachable"]
                ):
                    return log_and_build_error(
                        operation=operation,
                        error_message="Connection error occurred. Please check your internet connection and try again.",
                        params=params,
                        exception=e,
                        action="retry",
                    )

                # Peer resolution errors
                if "cannot cast" in error_msg or "peer" in error_msg:
                    return log_and_build_error(
                        operation=operation,
                        error_message="Unable to resolve or access the specified chat/user. Please verify the ID is correct and accessible.",
                        params=params,
                        exception=e,
                    )

                # Generic fallback
                return log_and_build_error(
                    operation=operation,
                    error_message=f"Operation failed: {e!s}",
                    params=params,
                    exception=e,
                )

        return wrapper

    return decorator
