import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
SCRIPT_DIR = Path(__file__).parent.parent.parent
PROJECT_DIR = SCRIPT_DIR


# Determine session directory - use persistent location for uvx, project dir for local development
def get_session_directory():
    """Get appropriate session directory based on execution context."""
    # If SESSION_DIR is explicitly set, use it
    if session_dir := os.getenv("SESSION_DIR"):
        return Path(session_dir)

    # Check if we're running in a temporary/ephemeral environment (like uvx)
    script_path_str = str(SCRIPT_DIR)
    if (
        "tmp" in script_path_str
        or "temp" in script_path_str
        or ".cache/uv" in script_path_str
        or "site-packages" in script_path_str
    ):
        # Use persistent user config directory
        config_dir = Path.home() / ".config" / "fast-mcp-telegram"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    # Use project directory for local development
    return PROJECT_DIR


SESSION_DIR = get_session_directory()
LOG_DIR = PROJECT_DIR / "logs"

# Create directories
LOG_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Telegram configuration
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
SESSION_NAME = os.getenv("SESSION_NAME", "mcp_telegram")
SESSION_PATH = SESSION_DIR / SESSION_NAME

# Connection pool settings
MAX_CONCURRENT_CONNECTIONS = 10

# Server info
SERVER_NAME = "MCP Telegram Server"
SERVER_VERSION = "0.0.1"
