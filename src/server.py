"""
Main server module for the Telegram MCP server functionality.
Provides API endpoints and core bot features.
"""

import asyncio
import os
import sys
import traceback

from fastmcp import FastMCP
from loguru import logger

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.client.connection import cleanup_client
from src.config.logging import setup_logging
from src.config.settings import DISABLE_AUTH
from src.server_components.routes_health import register_health_routes
from src.server_components.routes_web_setup import register_web_setup_routes
from src.server_components.tools_register import register_tools

IS_TEST_MODE = "--test-mode" in sys.argv

if IS_TEST_MODE:
    transport = "http"
    host = "127.0.0.1"
    port = 8000
else:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))


# Development token generation for testing
if DISABLE_AUTH:
    logger.info("🔓 Authentication DISABLED for development mode")
else:
    logger.info("🔐 Authentication ENABLED")
    if transport == "http":
        logger.info("🚨 HTTP transport: Bearer token authentication is MANDATORY")
        logger.info(
            "💡 For development, you can generate a token by calling generate_dev_token()"
        )
    else:
        logger.info(
            "📝 Stdio transport: Bearer token optional (fallback to default session)"
        )

# Initialize MCP server and logging
mcp = FastMCP("Telegram MCP Server", stateless_http=True)
setup_logging()

# Register routes and tools immediately (no on_startup hook available)
register_health_routes(mcp)
register_web_setup_routes(mcp)
register_tools(mcp)


def shutdown_procedure():
    """Synchronously performs async cleanup."""
    logger.info("Starting cleanup procedure.")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup_client())
        loop.close()
        logger.info("Cleanup successful.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}\n{traceback.format_exc()}")


def main():
    """Entry point for console script; runs the MCP server and ensures cleanup."""

    run_args = {"transport": transport}
    if transport == "http":
        run_args.update({"host": host, "port": port})

    try:
        mcp.run(**run_args)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Initiating shutdown.")
    finally:
        shutdown_procedure()


# Run the server if this file is executed directly
if __name__ == "__main__":
    main()
