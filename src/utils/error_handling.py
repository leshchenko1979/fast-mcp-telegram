"""
DRY Error Handling Utilities for Telegram MCP Server.

This module provides standardized error handling patterns to eliminate code duplication
across all tools and server components.
"""

import traceback
from datetime import datetime
from typing import Any

from loguru import logger


def _log_at_level(log_level: str, message: str, extra: dict | None = None) -> None:
    """
    Log a message at the specified level using loguru.

    Args:
        log_level: The log level ('error', 'warning', 'info', 'debug')
        message: The message to log
        extra: Extra data to include in the log record
    """
    if log_level.upper() == "ERROR":
        logger.error(message, extra=extra)
    elif log_level.upper() == "WARNING":
        logger.warning(message, extra=extra)
    elif log_level.upper() == "INFO":
        logger.info(message, extra=extra)
    else:
        logger.debug(message, extra=extra)


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

    sanitized = {}

    for key, value in params.items():
        # Mask phone numbers
        if "phone" in key.lower() and isinstance(value, str):
            if len(value) > 5:
                sanitized[key] = f"{value[:3]}***{value[-2:]}"
            else:
                sanitized[key] = "***"
        # Truncate long text values
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = f"{value[:200]}... (truncated)"
        # Truncate large message content
        elif (
            key in ["message", "new_text", "text"]
            and isinstance(value, str)
            and len(value) > 100
        ):
            sanitized[key] = f"{value[:100]}... (truncated)"
        # Keep other values as-is but convert to string if too complex
        else:
            try:
                # Ensure value is JSON serializable
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
