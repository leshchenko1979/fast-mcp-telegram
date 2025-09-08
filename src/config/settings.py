import os
from pathlib import Path

from dotenv import load_dotenv

from src._version import __version__

# Load environment variables
load_dotenv()

# Base paths
SCRIPT_DIR = Path(__file__).parent.parent.parent
PROJECT_DIR = SCRIPT_DIR


# Always use persistent directory for session storage
def get_session_directory():
    """Get persistent session directory for all installation methods."""
    # If SESSION_DIR is explicitly set, use it (for advanced users)
    if session_dir := os.getenv("SESSION_DIR"):
        return Path(session_dir)

    # Always use persistent user config directory for consistency, security, and cross-installation compatibility
    config_dir = Path.home() / ".config" / "fast-mcp-telegram"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


SESSION_DIR = get_session_directory()
LOG_DIR = PROJECT_DIR / "logs"

# Create directories
LOG_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Telegram configuration
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram")
SESSION_PATH = SESSION_DIR / SESSION_NAME

# Connection pool settings
MAX_CONCURRENT_CONNECTIONS = 10


# Server info
SERVER_NAME = "MCP Telegram Server"
SERVER_VERSION = __version__

# Authentication configuration
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() in ("true", "1", "yes")
