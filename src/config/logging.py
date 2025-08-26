from datetime import datetime
from loguru import logger
from .settings import LOG_DIR
import sys
import os
import logging

# Get current timestamp for log file name
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = LOG_DIR / f"mcp_server_{current_time}.log"

IS_TEST_MODE = '--test-mode' in sys.argv


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
        # Include original emitting logger/module/function/line from stdlib records
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {extra[emitter_logger]}:{extra[emitter_module]}:{extra[emitter_func]}:{extra[emitter_line]} - {message}"
    )
    # Console sink for quick visibility (DEBUG with full backtraces)
    logger.add(
        sys.stderr,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
        enqueue=True,
        # Shorter time, but keep emitter details too
        format="{time:HH:mm:ss.SSS} | {level:<8} | {extra[emitter_logger]}:{extra[emitter_module]}:{extra[emitter_func]}:{extra[emitter_line]} - {message}"
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
            # Bind original stdlib record metadata so we can display true emitter
            emitter_logger = getattr(record, "name", "?")
            emitter_module = getattr(record, "module", "?")
            emitter_func = getattr(record, "funcName", "?")
            emitter_line = getattr(record, "lineno", "?")
            logger.opt(depth=depth, exception=record.exc_info).bind(
                emitter_logger=emitter_logger,
                emitter_module=emitter_module,
                emitter_func=emitter_func,
                emitter_line=emitter_line,
            ).log(level, record.getMessage())

    # Install a single root handler
    root_logger = logging.getLogger()
    root_logger.handlers = [InterceptHandler()]
    root_logger.setLevel(0)

    # Configure specific library logger levels (no extra handlers so root handler applies)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Keep Telethon visible but reduce noise by module-level levels
    # Default Telethon at DEBUG for diagnostics
    telethon_root = logging.getLogger("telethon")
    telethon_root.setLevel(logging.DEBUG)
    telethon_root.propagate = True

    # Noisy submodules lowered to INFO (suppress their DEBUG flood)
    noisy_modules = [
        "telethon.network.mtprotosender",   # _send_loop, _recv_loop, _handle_update, etc.
        "telethon.extensions.messagepacker", # packing/debug spam
        "telethon.network",                 # any other network internals
    ]
    for name in noisy_modules:
        logging.getLogger(name).setLevel(logging.INFO)


def format_diagnostic_info(info: dict) -> str:
    """Format diagnostic information for logging."""
    try:
        import json
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return f"Error formatting diagnostic info: {str(e)}"
