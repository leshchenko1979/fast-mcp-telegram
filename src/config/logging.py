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
    logger.remove()

    # File sink with full tracebacks and diagnostics
    logger.add(
        LOG_PATH,
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        backtrace=True,
        diagnose=True,
        enqueue=True,
        # Clean format - emitter info is now in the message
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
    )
    # Console sink for quick visibility (DEBUG with full backtraces)
    logger.add(
        sys.stderr,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
        enqueue=True,
        # Clean format - emitter info is now in the message
        format="{time:HH:mm:ss.SSS} | {level:<8} | {message}",
    )

    # Bridge standard logging (uvicorn, telethon, etc.) to loguru
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                level = logger.level(record.levelname).name
            except Exception:
                level = record.levelno
            frame, depth = logging.currentframe(), 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            # Include original emitter info in clean format
            emitter_logger = getattr(record, "name", "unknown")
            emitter_func = getattr(record, "funcName", "unknown")
            emitter_line = getattr(record, "lineno", "?")

            # Keep full logger name for proper debugging context
            formatted_message = f"{emitter_logger}:{emitter_func}:{emitter_line} - {record.getMessage()}"

            try:
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, formatted_message
                )
            except Exception:
                # Fallback if anything fails
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, f"[logging_error] {record.getMessage()}"
                )

    # Install a single root handler
    root_logger = logging.getLogger()
    root_logger.handlers = [InterceptHandler()]
    root_logger.setLevel(0)

    # Configure specific library logger levels (no extra handlers so root handler applies)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)

    # Keep Telethon visible but reduce noise by module-level levels
    # Default Telethon at DEBUG for diagnostics
    telethon_root = logging.getLogger("telethon")
    telethon_root.setLevel(logging.DEBUG)
    telethon_root.propagate = True

    # Noisy submodules lowered to INFO (suppress their DEBUG flood)
    noisy_modules = [
        "telethon.network.mtprotosender",  # _send_loop, _recv_loop, _handle_update, etc.
        "telethon.extensions.messagepacker",  # packing/debug spam
        "telethon.network",  # any other network internals
    ]
    for name in noisy_modules:
        logging.getLogger(name).setLevel(logging.INFO)

    # Log server startup information
    cfg = get_config()
    logger.info("=== Telegram MCP Server Starting ===")
    logger.info(f"Version: {SERVER_VERSION}")
    logger.info(f"Mode: {cfg.server_mode.value}")
    logger.info(f"Transport: {cfg.transport}")
    if cfg.transport == "http":
        logger.info(f"Bind: {cfg.host}:{cfg.port}")
    logger.info(f"Session file path: {SESSION_PATH.absolute()}")
    logger.info(f"Log file path: {LOG_PATH.absolute()}")
    logger.info("=====================================")


def format_diagnostic_info(info: dict) -> str:
    """Format diagnostic information for logging."""
    try:
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return f"Error formatting diagnostic info: {e!s}"
