from datetime import datetime
from loguru import logger
from .settings import LOG_DIR
import sys
import os

# Get current timestamp for log file name
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = LOG_DIR / f"mcp_server_{current_time}.log"

IS_TEST_MODE = '--test-mode' in sys.argv

def setup_logging():
    """Configure logging with loguru."""
    if IS_TEST_MODE or os.environ.get("MCP_TRANSPORT") == "http":
        logger.remove()
        logger.add(LOG_PATH, rotation="1 day", retention="7 days")
    else:
        logger.remove()
        logger.add(sys.stdout, level="INFO")
        logger.add(LOG_PATH, rotation="1 day", retention="7 days")

def format_diagnostic_info(info: dict) -> str:
    """Format diagnostic information for logging."""
    try:
        import json
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return f"Error formatting diagnostic info: {str(e)}"
