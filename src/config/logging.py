from datetime import datetime
from loguru import logger
from .settings import LOG_DIR

# Get current timestamp for log file name
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = LOG_DIR / f"mcp_server_{current_time}.log"

def setup_logging():
    """Configure logging with loguru."""
    # Remove all existing handlers
    logger.remove()

    # Configure logging with absolute path
    logger.add(
        LOG_PATH,
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        enqueue=True,
        backtrace=True,
        diagnose=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message} | {extra}"
    )

    logger.info(f"Starting server, logging to: {LOG_PATH}")

def format_diagnostic_info(info: dict) -> str:
    """Format diagnostic information for logging."""
    try:
        import json
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return f"Error formatting diagnostic info: {str(e)}"
