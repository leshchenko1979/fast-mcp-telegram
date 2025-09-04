"""
DRY Logging Utilities for Telegram MCP Server.

This module provides centralized logging utilities that eliminate code duplication
across all tools and server components. These utilities handle consistent formatting,
parameter sanitization, and metadata addition for all logging operations.
"""

import traceback
from typing import Any

from loguru import logger

from src.utils.error_handling import (
    _log_at_level,
    add_logging_metadata,
    sanitize_params_for_logging,
)


def log_operation_start(operation: str, params: dict[str, Any] | None = None) -> None:
    """
    Log the start of an operation with consistent format.

    Args:
        operation: Name of the operation being started
        params: Dictionary of parameters for the operation
    """
    if params is None:
        params = {}

    safe_params = sanitize_params_for_logging(params)
    enhanced_params = add_logging_metadata(safe_params)
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

    # Flattened error structure for easier querying
    safe_params = sanitize_params_for_logging(params)
    log_extra = {
        "operation": operation,
        "params": safe_params,
        "error_type": type(error).__name__,
        "exception_message": str(error),
        "traceback": traceback.format_exc(),
    }

    log_message = f"Error in {operation}"
    _log_at_level(log_level, log_message, extra=log_extra)
