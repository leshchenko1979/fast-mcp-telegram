import json
import logging
import logging.config
import time
from typing import Any

from .server_config import get_config
from .settings import SERVER_VERSION, SESSION_PATH

# Module-level configuration flag
_configured = False

# Global logger instance for the module
logger = logging.getLogger(__name__)

# Filtered endpoints for AccessFilter optimization
_FILTERED_ENDPOINTS = frozenset(["/health", "/metrics", "/status"])


class AccessFilter(logging.Filter):
    """Filter out noisy access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out health/metric/status endpoint access logs."""
        if record.name != "uvicorn.access":
            return True
        message = record.getMessage()
        return not any(endpoint in message for endpoint in _FILTERED_ENDPOINTS)


def create_logging_config(log_level: str) -> dict[str, Any]:
    """Create the logging configuration dictionary."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "custom": {
                "()": "src.config.logging.CustomFormatter",
                "format": "%(message)s",
                "datefmt": "%H:%M:%S",
            }
        },
        "filters": {"access": {"()": "src.config.logging.AccessFilter"}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "custom",
                "stream": "ext://sys.stderr",
                "filters": ["access"],
            }
        },
        "loggers": {
            # Third-party dependencies at WARNING level (suppress DEBUG noise)
            # NOTE: These are functionally redundant with root WARNING level, but kept explicit for:
            # - Documentation: Clear intent that these libraries should be quiet
            # - Safety: Protects against future root logger level changes
            # - Maintainability: Easy to adjust individual third-party loggers
            # - Clarity: Self-documenting code showing logging strategy
            "uvicorn": {"level": "WARNING"},
            "uvicorn.error": {"level": "WARNING"},
            "uvicorn.access": {"level": "WARNING"},
            "mcp.server.lowlevel.server": {"level": "WARNING"},
            "asyncio": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "aiohttp": {"level": "WARNING"},
            "telethon": {"level": "WARNING"},
            "sse_starlette.sse": {"level": "WARNING"},
            "fastmcp": {"level": "WARNING"},
            "logging": {"level": "WARNING"},
            # Application code at DEBUG level (catch-all for src.* hierarchy)
            # NOTE: Explicit opt-in for verbosity - secure by default, explicit for clarity
            "src": {"level": "DEBUG"},
        },
        "root": {"level": "WARNING", "handlers": ["console"]},
    }


class CustomFormatter(logging.Formatter):
    """Custom formatter matching loguru console format."""

    def formatTime(self, record, datefmt=None):  # noqa: N802
        """Format time with milliseconds."""
        ct = time.localtime(record.created)
        # Format as HH:mm:ss.SSS (milliseconds)
        return time.strftime("%H:%M:%S", ct) + f".{int(record.msecs):03d}"

    def format(self, record):
        """Format log record to match loguru console output."""
        # Use custom formatTime for time formatting
        time_str = self.formatTime(record)
        # Level name left-aligned to 8 characters
        level = record.levelname.ljust(8)
        # Include logger name, function, and line number
        name = record.name
        func = record.funcName
        line = record.lineno
        message = record.getMessage()
        return f"{time_str} | {level} | {name}:{func}:{line} | {message}"


def setup_logging():
    """Configure logging with stdlib logging using canonical patterns (console only)."""
    global _configured

    # Prevent repeated setup by checking module-level flag
    if _configured:
        return

    # Get configuration
    cfg = get_config()

    # Create logging configuration
    config = create_logging_config(cfg.log_level.upper())

    # Apply configuration - dictConfig handles everything for synchronous logging
    logging.config.dictConfig(config)

    # Mark as configured
    _configured = True

    # Log server startup information
    startup_lines = [
        "=== Telegram MCP Server Starting ===",
        f"Version: {SERVER_VERSION}",
        f"Mode: {cfg.server_mode.value}",
        f"Transport: {cfg.transport}",
    ]

    if cfg.transport == "http":
        startup_lines.append(f"Bind: {cfg.host}:{cfg.port}")

    startup_lines.extend(
        [
            f"Session file path: {SESSION_PATH.absolute()}",
            "=====================================",
        ]
    )

    # Log all startup information
    for line in startup_lines:
        logger.info(line)


def cleanup_logging():
    """Clean up logging resources.

    No-op for synchronous logging configuration.
    """


def format_diagnostic_info(info: dict) -> str:
    """Format diagnostic information for logging."""
    return json.dumps(info, indent=2, default=str)
