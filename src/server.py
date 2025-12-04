"""
Main server module for the Telegram MCP server functionality.
Provides API endpoints and core bot features.
"""

import asyncio
import traceback
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from loguru import logger

from src.client.connection import (
    cleanup_client,
    cleanup_failed_sessions,
    cleanup_idle_sessions,
)
from src.config.logging import setup_logging
from src.config.server_config import get_config
from src.server_components.health import register_health_routes
from src.server_components.mtproto_api import register_mtproto_api_routes
from src.server_components.tools_register import register_tools
from src.server_components.web_setup import register_web_setup_routes

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
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    await cleanup_client()


# Initialize MCP server and logging
mcp = FastMCP("Telegram MCP Server", lifespan=lifespan)
setup_logging()

# Register routes and tools immediately (no on_startup hook available)
register_health_routes(mcp)
register_web_setup_routes(mcp)
register_mtproto_api_routes(mcp)
register_tools(mcp)


def shutdown_procedure():
    """Synchronously performs async cleanup."""
    logger.info("Starting cleanup procedure.")

    try:
        # If running with lifespan, cleanup is handled there
        # This function is a fallback for direct script execution without lifespan support
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup_client())
        loop.close()
        logger.info("Cleanup successful.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}\n{traceback.format_exc()}")


def main():
    """Entry point for console script; runs the MCP server and ensures cleanup."""

    run_args = {"transport": config.transport}
    if config.transport == "http":
        run_args.update(
            {"host": config.host, "port": config.port, "stateless_http": True}
        )

    try:
        mcp.run(**run_args)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Initiating shutdown.")
    finally:
        shutdown_procedure()


# Run the server if this file is executed directly
if __name__ == "__main__":
    main()
