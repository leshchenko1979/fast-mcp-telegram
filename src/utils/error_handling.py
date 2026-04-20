"""
DRY Error Handling Utilities for Telegram MCP Server.

This module provides standardized error handling patterns to eliminate code duplication
across all tools and server components.
"""

from __future__ import annotations

import logging
import traceback
from enum import IntEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.client.connection import SessionNotAuthorizedError, TelegramTransportError

logger = logging.getLogger(__name__)

_connection_error_types: tuple[type, type] | None = None


def _get_connection_error_types() -> tuple[type, type]:
    """Lazy-load session/transport types to avoid import cycles with connection."""
    global _connection_error_types
    if _connection_error_types is None:
        from src.client.connection import (
            SessionNotAuthorizedError,
            TelegramTransportError,
        )

        _connection_error_types = (SessionNotAuthorizedError, TelegramTransportError)
    return _connection_error_types


class MCPErrorCode(IntEnum):
    """Error codes in -32000 to -32099 per MCP spec."""

    INTERNAL_ERROR = -32000
    CONNECTION_ERROR = -32001
    SESSION_NOT_AUTHORIZED = -32002
    VALIDATION_ERROR = -32003
    AUTHORIZATION_ERROR = -32004
    NOT_FOUND_ERROR = -32005
    RATE_LIMIT_ERROR = -32006
    FORBIDDEN_ERROR = -32007
    TELEGRAM_RPC_ERROR = -32008
    INVALID_PARAMS_ERROR = -32009


class ErrorAction(IntEnum):
    """Human-readable remediation hints for the LLM."""

    RETRY = 1
    AUTHENTICATE_SESSION = 2
    RUN_SETUP = 3


def sanitize_params_for_logging(params: dict[str, Any] | None) -> dict[str, Any]:
    """Proxy to logging_utils to avoid circular imports."""
    from src.utils.logging_utils import sanitize_params_for_logging as _impl
    return _impl(params)


def is_error_response(result: Any) -> bool:
    """
    Check if a result is an error response.

    Args:
        result: The result to check

    Returns:
        True if result is a structured error response, False otherwise
    """
    return isinstance(result, dict) and result.get("ok") is False


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
        and result[0].get("ok") is False
    ):
        return True, result[0]
    return False, None


def build_error_response(
    error_message: str,
    operation: str,
    params: dict[str, Any] | None = None,
    exception: Exception | None = None,
    action: ErrorAction | None = None,
    error_code: str | None = None,
    code: MCPErrorCode | None = None,
) -> dict[str, Any]:
    """
    Build a standardized error response dictionary.

    Args:
        error_message: Human-readable error message
        operation: Name of the operation that failed
        params: Original parameters for context
        exception: Exception that caused the error (for logging)
        action: Optional action hint for the LLM (ErrorAction enum)
        error_code: Optional machine-readable Telegram RPC error code (e.g., "INVITE_HASH_EXPIRED")
        code: Optional numeric MCP error code

    Returns:
        Standardized error response dictionary
    """
    error_response: dict[str, Any] = {
        "ok": False,
        "error": error_message,
        "operation": operation,
    }

    if code is not None:
        error_response["code"] = code.value
    elif error_code:
        error_response["code"] = MCPErrorCode.TELEGRAM_RPC_ERROR.value

    if params:
        error_response["params"] = params

    if exception:
        error_response["exception"] = {
            "type": type(exception).__name__,
            "message": str(exception),
        }

    if action:
        error_response["action"] = action.name

    if error_code:
        error_response["error_code"] = error_code

    return error_response


def log_and_build_error(
    operation: str,
    error_message: str,
    params: dict[str, Any] | None = None,
    exception: Exception | None = None,
    log_level: str = "error",
    action: ErrorAction | None = None,
    error_code: str | None = None,
    code: MCPErrorCode | None = None,
) -> dict[str, Any]:
    """
    Log an error and build a standardized error response.

    Args:
        operation: Name of the operation that failed
        error_message: Human-readable error message
        params: Original parameters for context
        exception: Exception that caused the error
        log_level: Logging level ('error', 'warning', 'info', etc.)
        action: Optional action hint (ErrorAction enum)
        error_code: Optional machine-readable Telegram RPC error code
        code: Optional numeric MCP error code

    Returns:
        Standardized error response dictionary
    """
    # Build flattened error info for logging
    log_extra: dict[str, Any] = {
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
    numeric_level = {
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }.get(log_level.upper(), logging.DEBUG)
    logger.log(numeric_level, log_message, extra=log_extra)

    # Return standardized error response
    return build_error_response(
        error_message=error_message,
        operation=operation,
        params=params,
        exception=exception,
        action=action,
        error_code=error_code,
        code=code,
    )


def find_connection_exception(
    exc: BaseException,
) -> SessionNotAuthorizedError | TelegramTransportError | None:
    """Return session or transport error from exc or its __cause__ chain."""
    session_cls, transport_cls = _get_connection_error_types()
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, session_cls):
            return cur
        if isinstance(cur, transport_cls):
            return cur
        cur = cur.__cause__
    return None


def log_connection_error_response(
    operation: str,
    params: dict[str, Any] | None,
    exc: BaseException,
) -> dict[str, Any] | None:
    """
    If exc (or its __cause__ chain) is a session/transport error, log and return a tool error dict.

    Returns:
        Error response dict, or None if exc is not one of those connection errors.
    """
    session_cls, _ = _get_connection_error_types()
    resolved = find_connection_exception(exc)
    if resolved is None:
        return None
    if isinstance(resolved, session_cls):
        return log_and_build_error(
            operation=operation,
            error_message="Session not authorized. Please authenticate your Telegram session first.",
            params=params,
            exception=resolved,
            action=ErrorAction.AUTHENTICATE_SESSION,
            code=MCPErrorCode.SESSION_NOT_AUTHORIZED,
        )
    return log_and_build_error(
        operation=operation,
        error_message=str(resolved),
        params=params,
        exception=resolved,
        action=ErrorAction.RETRY,
        code=MCPErrorCode.CONNECTION_ERROR,
    )


def handle_tool_error(
    result: Any,
    operation: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Check if a tool result is an error dict. Does NOT log — logging happens upstream in with_error_handling.

    Args:
        result: Result from tool function
        operation: Name of the operation (unused, for API compat)
        params: Original parameters for context (unused, for API compat)

    Returns:
        Error dict if result is an error, None otherwise
    """
    # Check for dict error response
    if is_error_response(result):
        return result

    # Check for list error response (e.g., search_contacts)
    is_list_error, error_dict = is_list_error_response(result)
    return error_dict if is_list_error and error_dict is not None else None
