from pathlib import Path

from src._version import __version__
from src.config.server_config import get_config

# Base paths
SCRIPT_DIR = Path(__file__).parent.parent.parent
PROJECT_DIR = SCRIPT_DIR
LOG_DIR = PROJECT_DIR / "logs"

# Create directories
LOG_DIR.mkdir(exist_ok=True)

# Get configuration instance
config = get_config()

# Backward compatibility - export commonly used values
SESSION_DIR = config.session_directory
API_ID = config.api_id
API_HASH = config.api_hash
PHONE_NUMBER = config.phone_number
SESSION_NAME = "telegram"  # Default session name
SESSION_PATH = SESSION_DIR / SESSION_NAME

# Connection pool settings
MAX_CONCURRENT_CONNECTIONS = 10

# Server info
SERVER_NAME = "MCP Telegram Server"
SERVER_VERSION = __version__

# Authentication configuration (deprecated - use config.disable_auth)
DISABLE_AUTH = config.disable_auth
