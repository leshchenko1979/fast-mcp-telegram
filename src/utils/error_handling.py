"""
DRY Error Handling Utilities for Telegram MCP Server.

This module provides standardized error handling patterns to eliminate code duplication
across all tools and server components.
"""

import time
import traceback
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


def generate_request_id(prefix: str) -> str:
    """Generate a unique request ID with timestamp."""
    return f"{prefix}_{int(time.time() * 1000)}"


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
    request_id: str | None = None,
    params: dict[str, Any] | None = None,
    exception: Exception | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """
    Build a standardized error response dictionary.

    Args:
        error_message: Human-readable error message
        operation: Name of the operation that failed
        request_id: Unique request identifier (auto-generated if None)
        params: Original parameters for context
        exception: Exception that caused the error (for logging)
        action: Optional action to suggest to the user (e.g., "run_setup")

    Returns:
        Standardized error response dictionary
    """
    if request_id is None:
        request_id = generate_request_id("error")

    error_response = {
        "ok": False,
        "error": error_message,
        "request_id": request_id,
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
    request_id: str,
    operation: str,
    error_message: str,
    params: dict[str, Any],
    exception: Exception | None = None,
    log_level: str = "error",
    action: str | None = None,
) -> dict[str, Any]:
    """
    Log an error and build a standardized error response.

    Args:
        request_id: Unique request identifier
        operation: Name of the operation that failed
        error_message: Human-readable error message
        params: Original parameters for context
        exception: Exception that caused the error
        log_level: Logging level ('error', 'warning', 'info', etc.)
        action: Optional action to suggest to the user (e.g., "run_setup")

    Returns:
        Standardized error response dictionary
    """
    # Build comprehensive error info for logging
    error_info = {
        "request_id": request_id,
        "operation": operation,
        "error_message": error_message,
        "params": params,
    }

    if exception:
        error_info["exception"] = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }

    # Log the error
    log_message = f"[{request_id}] {operation} failed: {error_message}"
    _log_at_level(log_level, log_message, extra={"diagnostic_info": error_info})

    # Return standardized error response
    return build_error_response(
        error_message=error_message,
        operation=operation,
        request_id=request_id,
        params=params,
        exception=exception,
        action=action,
    )


def handle_tool_error(
    result: Any,
    operation: str,
    request_id: str,
    params: dict[str, Any],
    log_level: str = "error",
) -> dict[str, Any] | None:
    """
    Handle error responses from tools with consistent logging and response processing.

    Args:
        result: Result from tool function
        operation: Name of the operation
        request_id: Unique request identifier
        params: Original parameters for context
        log_level: Logging level for error messages

    Returns:
        Processed error response if result is an error, None otherwise
    """

    def _log_and_return_error(error_dict: dict[str, Any]) -> dict[str, Any]:
        """Helper function to log an error and return the error dict."""
        log_message = (
            f"[{request_id}] {operation} returned error: "
            f"{error_dict.get('error', 'Unknown error')}"
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
