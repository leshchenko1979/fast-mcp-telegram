import json
import logging
import sys
from datetime import datetime

from loguru import logger

from .server_config import get_config
from .settings import LOG_DIR, SERVER_VERSION, SESSION_PATH

# Get current timestamp for log file name
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = LOG_DIR / f"mcp_server_{current_time}.log"


def setup_logging():
    """Configure logging with loguru."""
    # Prevent repeated setup by checking if already configured
    if hasattr(setup_logging, "_configured"):
        return
    setup_logging._configured = True

    # Get configuration
    cfg = get_config()

    logger.remove()

    # File sink with full tracebacks and diagnostics
    logger.add(
        LOG_PATH,
        rotation="1 day",
        retention="7 days",
        level="DEBUG",  # Always keep full logs in file
        backtrace=True,
        diagnose=True,
        enqueue=True,
        # Clean format - emitter info is now in the message
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
    )
    # Console sink with configurable level
    logger.add(
        sys.stderr,
        level=cfg.log_level.upper(),  # Use configured log level
        backtrace=True,
        diagnose=True,
        enqueue=True,
        # Clean format - emitter info is now in the message
        format="{time:HH:mm:ss.SSS} | {level:<8} | {message}",
    )

    # Bridge standard logging (uvicorn, telethon, etc.) to loguru
    class InterceptHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            # Cache level mappings for performance
            self._level_cache = {}

        def emit(self, record: logging.LogRecord) -> None:
            message = record.getMessage()

            # Filter out noisy access logs to reduce log spam
            if record.name == "uvicorn.access" and any(
                endpoint in message for endpoint in ["/health", "/metrics", "/status"]
            ):
                return

            # Optimized level resolution with caching
            level_name = record.levelname
            if level_name not in self._level_cache:
                try:
                    self._level_cache[level_name] = logger.level(level_name).name
                except Exception:
                    self._level_cache[level_name] = record.levelno
            level = self._level_cache[level_name]

            # Optimized frame walking - only when needed
            depth = 2
            if record.exc_info:
                frame = logging.currentframe()
                while frame and frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1

            # Optimized message formatting - avoid f-strings when possible
            emitter_logger = record.name or "unknown"
            emitter_func = record.funcName or "unknown"
            emitter_line = record.lineno or "?"
            message = record.getMessage()

            # Use string concatenation for better performance
            formatted_message = (
                f"{emitter_logger}:{emitter_func}:{emitter_line} - {message}"
            )

            try:
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, formatted_message
                )
            except Exception:
                # Fallback if anything fails
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, f"[logging_error] {message}"
                )

    # Install a single root handler
    root_logger = logging.getLogger()
    root_logger.handlers = [InterceptHandler()]
    root_logger.setLevel(0)

    # Configure specific library logger levels (no extra handlers so root handler applies)
    # Batch logger configuration for better performance
    logger_configs = [
        ("uvicorn", logging.INFO),
        ("uvicorn.error", logging.ERROR),
        ("uvicorn.access", logging.WARNING),
        ("mcp.server.lowlevel.server", logging.WARNING),
        ("asyncio", logging.WARNING),
        ("urllib3", logging.WARNING),
        ("httpx", logging.WARNING),
        ("aiohttp", logging.WARNING),
        # Telethon configuration - keep root at DEBUG for diagnostics
        ("telethon", logging.DEBUG),
        # Noisy Telethon submodules lowered to INFO (suppress their DEBUG flood)
        (
            "telethon.network.mtprotosender",
            logging.INFO,
        ),  # _send_loop, _recv_loop, _handle_update, etc.
        ("telethon.extensions.messagepacker", logging.INFO),  # packing/debug spam
        ("telethon.network", logging.INFO),  # any other network internals
        ("telethon.network.connection", logging.INFO),  # connection management noise
        ("telethon.client.telegramclient", logging.INFO),  # client connection noise
        ("telethon.tl", logging.INFO),  # TL layer noise
        ("telethon.client.updates", logging.INFO),  # Update loop timeout spam
        # Suppress SSE ping messages completely
        ("sse_starlette.sse", logging.WARNING),
    ]

    for logger_name, level in logger_configs:
        logging.getLogger(logger_name).setLevel(level)

    # Log server startup information (optimized batch logging)
    cfg = get_config()
    startup_info = [
        "=== Telegram MCP Server Starting ===",
        f"Version: {SERVER_VERSION}",
        f"Mode: {cfg.server_mode.value}",
        f"Transport: {cfg.transport}",
    ]

    if cfg.transport == "http":
        startup_info.append(f"Bind: {cfg.host}:{cfg.port}")

    startup_info.extend(
        [
            f"Session file path: {SESSION_PATH.absolute()}",
            f"Log file path: {LOG_PATH.absolute()}",
            "=====================================",
        ]
    )

    # Batch log startup information
    for info_line in startup_info:
        logger.info(info_line)


def format_diagnostic_info(info: dict) -> str:
    """Format diagnostic information for logging."""
    try:
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return f"Error formatting diagnostic info: {e!s}"
