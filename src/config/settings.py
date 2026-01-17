from pathlib import Path

from src._version import __version__
from src.config.server_config import get_config

# Base paths
SCRIPT_DIR = Path(__file__).parent.parent.parent
PROJECT_DIR = SCRIPT_DIR

# Get configuration instance
config = get_config()

# Backward compatibility - export commonly used values
SESSION_DIR = config.session_directory
API_ID = config.api_id
API_HASH = config.api_hash
PHONE_NUMBER = config.phone_number
SESSION_NAME = (
    config.session_name
)  # Get from config (supports env vars and CLI options)
SESSION_PATH = config.session_path  # Full session path from config

# Connection pool settings
MAX_CONCURRENT_CONNECTIONS = 10

# Server info
SERVER_NAME = "MCP Telegram Server"
SERVER_VERSION = __version__

# Authentication configuration (deprecated - use config.disable_auth)
DISABLE_AUTH = config.disable_auth
