import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
SCRIPT_DIR = Path(__file__).parent.parent.parent
PROJECT_DIR = SCRIPT_DIR
LOG_DIR = SCRIPT_DIR / "logs"

# Create logs directory
LOG_DIR.mkdir(exist_ok=True)

# Telegram configuration
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'mcp_telegram')
SESSION_PATH = PROJECT_DIR / SESSION_NAME

# Connection pool settings
MAX_CONCURRENT_CONNECTIONS = 10

# Server info
SERVER_NAME = "MCP Telegram Server"
SERVER_VERSION = "0.0.1"
