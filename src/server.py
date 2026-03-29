"""
Main server module for the Telegram MCP server functionality.
Provides API endpoints and core bot features.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastmcp import FastMCP

from src.client.connection import (
    cleanup_failed_sessions,
    cleanup_idle_sessions,
    cleanup_session_cache,
)
from src.config.logging import setup_logging
from src.config.server_config import get_config
from src.server_components.attachment_routes import register_attachment_routes
from src.server_components.auth_middleware import UrlTokenMiddleware
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

# Auth provider only for http-auth mode; stdio and http-no-auth have no auth
_auth_provider = None
if config.require_auth:
    from src.server_components.session_token_verifier import SessionFileTokenVerifier

    _auth_provider = SessionFileTokenVerifier(config)

# Initialize MCP server
mcp = FastMCP("Telegram MCP Server", auth=_auth_provider, lifespan=lifespan)

# Register routes and tools immediately (no on_startup hook available)
register_health_routes(mcp)
register_web_setup_routes(mcp)
register_mtproto_api_routes(mcp)
register_attachment_routes(mcp)
register_tools(mcp)


def main():
    """Entry point for console script; runs the MCP server."""
    transport: Literal["stdio", "http"] = config.transport
    if transport == "http":
        # Use http_app() to get the Starlette application so we can add middleware
        app = mcp.http_app(
            path="/v1/mcp",
            stateless_http=True,
        )

        # Add URL token middleware for clients that can't set headers
        if config.require_auth:
            app = UrlTokenMiddleware(app, config)

        # Run with uvicorn
        import uvicorn

        uvicorn.run(
            app,
            host=config.host,
            port=config.port,
            log_level="info",
        )
    else:
        mcp.run(transport=transport)


# Run the server if this file is executed directly
if __name__ == "__main__":
    main()
