"""
Main server module for the Telegram MCP server functionality.
Provides API endpoints and core bot features.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from src.client.connection import (
    cleanup_failed_sessions,
    cleanup_idle_sessions,
    cleanup_session_cache,
)
from src.config.logging import setup_logging
from src.config.server_config import get_config
from src.server_components.health import register_health_routes
from src.server_components.mtproto_api import register_mtproto_api_routes
from src.server_components.tools_register import register_tools
from src.server_components.web_setup import register_web_setup_routes

logger = logging.getLogger(__name__)

# Get configuration
config = get_config()

# Background cleanup task
_cleanup_task = None


async def cleanup_loop():
    """Background task to clean up failed and idle sessions."""
    logger.info("Starting background cleanup task")
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            await cleanup_failed_sessions()
            await cleanup_idle_sessions()
        except asyncio.CancelledError:
            logger.info("Background cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)  # Wait before retrying


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Lifecycle manager for the MCP server."""
    # Startup
    global _cleanup_task
    _cleanup_task = asyncio.create_task(cleanup_loop())

    yield

    # Shutdown
    if _cleanup_task:
        _cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _cleanup_task

    await cleanup_session_cache()


setup_logging()

# Initialize MCP server
mcp = FastMCP("Telegram MCP Server", lifespan=lifespan)

# Register routes and tools immediately (no on_startup hook available)
register_health_routes(mcp)
register_web_setup_routes(mcp)
register_mtproto_api_routes(mcp)
register_tools(mcp)


def main():
    """Entry point for console script; runs the MCP server."""

    run_args = {"transport": config.transport}
    if config.transport == "http":
        run_args.update(
            {"host": config.host, "port": config.port, "stateless_http": True}
        )

    mcp.run(**run_args)


# Run the server if this file is executed directly
if __name__ == "__main__":
    main()
