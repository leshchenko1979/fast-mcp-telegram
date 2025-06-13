"""
Main server module for the Telegram bot functionality.
Provides API endpoints and core bot features.
"""

import os
import time
from loguru import logger
from mcp.server.fastmcp import FastMCP
import traceback
import asyncio
import sys
import atexit
from pydantic import BaseModel, Field

from src.config.logging import setup_logging
from src.tools.search import search_telegram
from src.tools.messages import send_message, list_dialogs
from src.tools.statistics import get_chat_statistics
from src.tools.links import generate_telegram_links
from src.tools.export import export_chat_data
from src.tools.mtproto import invoke_mtproto_method

IS_TEST_MODE = '--test-mode' in sys.argv

if IS_TEST_MODE:
    transport = "http"
    host = "127.0.0.1"
    port = 8000
else:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))

if transport == "http":
    mcp = FastMCP("Telegram MCP Server", transport="http", host=host, port=port)
else:
    mcp = FastMCP("Telegram MCP Server", transport="stdio")

# Set up logging
setup_logging()

# Register tools with the MCP server
@mcp.tool()
async def search_messages(
    query: str,
    chat_id: str = None,
    limit: int = 100,
    offset: int = 0,
    chat_type: str = None,
    min_date: str = None,
    max_date: str = None,
    auto_expand_batches: int = 2,
):
    """
    Search Telegram messages with pagination, date range, chat type filter, and auto-expansion.

    Args:
        query: The search query string.
        chat_id: Optional chat ID to search in a specific chat.
        limit: Maximum number of results to return.
        offset: Number of results to skip (for pagination).
        chat_type: Filter by chat type: 'private', 'group', 'channel', or None for all.
        min_date: Minimum date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
        max_date: Maximum date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
        auto_expand_batches: Maximum additional batches to fetch if not enough filtered results are found (default 2).
    """
    try:
        request_id = f"search_{int(time.time())}"
        logger.info(f"[{request_id}] Searching messages with query: {query}, chat_id: {chat_id}, limit: {limit}, offset: {offset}, chat_type: {chat_type}, min_date: {min_date}, max_date: {max_date}, auto_expand_batches: {auto_expand_batches}")
        results = await search_telegram(
            query,
            chat_id,
            limit,
            min_date=min_date,
            max_date=max_date,
            offset=offset,
            chat_type=chat_type,
            auto_expand_batches=auto_expand_batches
        )
        logger.info(f"[{request_id}] Found {len(results)} messages (offset: {offset}, chat_type: {chat_type}, min_date: {min_date}, max_date: {max_date}, auto_expand_batches: {auto_expand_batches})")
        return results
    except Exception as e:
        logger.error(f"[{request_id}] Error searching messages: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def send_telegram_message(chat_id: str, message: str, reply_to_msg_id: int = None):
    """Send a message to a Telegram chat, optionally as a reply."""
    try:
        request_id = f"send_{int(time.time())}"
        logger.info(f"[{request_id}] Sending message to chat: {chat_id}")
        result = await send_message(chat_id, message, reply_to_msg_id)
        logger.info(f"[{request_id}] Message sent successfully")
        return result
    except Exception as e:
        logger.error(f"[{request_id}] Error sending message: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def get_dialogs(limit: int = 100, offset: int = 0):
    """List available Telegram dialogs (chats) with pagination."""
    try:
        request_id = f"dialogs_{int(time.time())}"
        logger.info(f"[{request_id}] Fetching dialogs, limit: {limit}, offset: {offset}")
        results = await list_dialogs(limit, offset)
        logger.info(f"[{request_id}] Found {len(results)} dialogs (offset: {offset})")
        return results
    except Exception as e:
        logger.error(f"[{request_id}] Error listing dialogs: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def get_statistics(chat_id: str):
    """Get statistics for a specific Telegram chat."""
    try:
        request_id = f"stats_{int(time.time())}"
        logger.info(f"[{request_id}] Getting statistics for chat: {chat_id}")
        stats = await get_chat_statistics(chat_id)
        logger.info(f"[{request_id}] Statistics retrieved successfully")
        return stats
    except Exception as e:
        logger.error(f"[{request_id}] Error getting statistics: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def generate_links(chat_id: str, message_ids: list[int]):
    """Generate Telegram links for specific messages in a chat."""
    try:
        request_id = f"links_{int(time.time())}"
        logger.info(f"[{request_id}] Generating links for chat: {chat_id}, messages: {message_ids}")
        links = await generate_telegram_links(chat_id, message_ids)
        logger.info(f"[{request_id}] Links generated successfully")
        return links
    except Exception as e:
        logger.error(f"[{request_id}] Error generating links: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def export_data(chat_id: str, format: str = "json"):
    """Export chat data in the specified format (default: JSON)."""
    try:
        request_id = f"export_{int(time.time())}"
        logger.info(f"[{request_id}] Exporting data for chat: {chat_id}, format: {format}")
        data = await export_chat_data(chat_id, format)
        logger.info(f"[{request_id}] Data exported successfully")
        return data
    except Exception as e:
        logger.error(f"[{request_id}] Error exporting data: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def invoke_mtproto(method_full_name: str, params: dict):
    """Invoke any MTProto method by full name and parameters."""
    try:
        request_id = f"mtproto_{int(time.time())}"
        logger.info(f"[{request_id}] Invoking MTProto method: {method_full_name} with params: {params}")
        result = await invoke_mtproto_method(method_full_name, params)
        logger.info(f"[{request_id}] MTProto method invoked successfully")
        return result
    except Exception as e:
        logger.error(f"[{request_id}] Error invoking MTProto method: {str(e)}\n{traceback.format_exc()}")
        raise

def _sync_cleanup():
    """Synchronous cleanup for atexit (for stdio transport)."""
    import asyncio
    from src.client.connection import cleanup_client
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule cleanup in running loop
            loop.create_task(cleanup_client())
        else:
            loop.run_until_complete(cleanup_client())
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Run the server if this file is executed directly
if __name__ == "__main__":
    if transport == "http":
        try:
            asyncio.run(mcp.run_sse_async())
        finally:
            # Ensure cleanup on HTTP server shutdown
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                try:
                    from src.client.connection import cleanup_client
                    loop.run_until_complete(cleanup_client())
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")
    else:
        # For stdio, use atexit to ensure cleanup
        atexit.register(_sync_cleanup)
        mcp.run()
