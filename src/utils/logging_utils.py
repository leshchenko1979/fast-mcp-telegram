"""
DRY Logging Utilities for Telegram MCP Server.

This module provides centralized logging utilities that eliminate code duplication
across all tools and server components. These utilities handle consistent formatting,
parameter sanitization, and metadata addition for all logging operations.
"""

import logging
import traceback
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def mask_phone_number_for_log(phone: str) -> str:
    """
    Mask a phone number for safe logging.

    Uses the same rules as sanitize_params_for_logging for phone_* keys.
    """
    if not isinstance(phone, str) or not phone:
        return "***"
    return "***" if len(phone) <= 5 else f"{phone[:3]}***{phone[-2:]}"


def _add_logging_metadata(params: dict[str, Any]) -> dict[str, Any]:
    """Add consistent metadata to parameter dictionaries for logging."""
    return params | {
        "timestamp": datetime.now().isoformat(),
        "param_count": len(params),
    }


def sanitize_params_for_logging(params: dict[str, Any] | None) -> dict[str, Any]:
    """
    Sanitize and truncate parameters for safe logging.
    """
    if not params:
        return {}

    phone_keys = {"phone", "phone_number", "mobile"}
    message_keys = {"message", "new_text", "text"}

    sanitized = {}

    for key, value in params.items():
        key_lower = key.lower()

        if any(phone_key in key_lower for phone_key in phone_keys) and isinstance(
            value, str
        ):
            sanitized[key] = mask_phone_number_for_log(value)
        elif key in message_keys and isinstance(value, str) and len(value) > 100:
            sanitized[key] = f"{value[:100]}... (truncated)"
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = f"{value[:200]}... (truncated)"
        else:
            try:
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


def log_operation_start(operation: str, params: dict[str, Any] | None = None) -> None:
    """
    Log the start of an operation with consistent format.

    Args:
        operation: Name of the operation being started
        params: Dictionary of parameters for the operation
    """
    if not params:
        logger.debug(operation)
        return

    safe_params = sanitize_params_for_logging(params)
    enhanced_params = _add_logging_metadata(safe_params)
    logger.debug(operation, extra={"params": enhanced_params})


def log_operation_success(operation: str, chat_id: str | None = None) -> None:
    """
    Log successful completion of an operation.

    Args:
        operation: Name of the operation that completed successfully
        chat_id: Optional chat ID for context in the success message
    """
    if chat_id:
        logger.info(f"{operation} successfully in chat {chat_id}")
    else:
        logger.info(f"{operation} successfully")


def log_operation_error(
    operation: str,
    error: Exception,
    params: dict[str, Any] | None = None,
    log_level: str = "error",
) -> None:
    """
    Log operation errors with consistent format.

    Args:
        operation: Name of the operation that failed
        error: The exception that was raised
        params: Original parameters for context
        log_level: Logging level ('error', 'warning', 'info', 'debug')
    """
    if params is None:
        params = {}

    safe_params = sanitize_params_for_logging(params)
    log_extra = {
        "operation": operation,
        "params": safe_params,
        "error_type": type(error).__name__,
        "exception_message": str(error),
        "traceback": traceback.format_exc(),
    }

    log_message = f"Error in {operation}"
    numeric_level = {
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }.get(log_level.upper(), logging.DEBUG)
    logger.log(numeric_level, log_message, extra=log_extra)
