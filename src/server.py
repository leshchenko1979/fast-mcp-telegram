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

from src.config.logging import setup_logging
from src.tools.search import search_telegram, advanced_search_telegram, pattern_search_telegram
from src.tools.messages import send_message, list_dialogs
from src.tools.statistics import get_chat_statistics
from src.tools.links import generate_telegram_links
from src.tools.export import export_chat_data

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
async def search_messages(query: str, chat_id: str = None, limit: int = 100, offset: int = 0):
    """Search for messages in Telegram chats with pagination."""
    try:
        request_id = f"search_{int(time.time())}"
        logger.info(f"[{request_id}] Searching messages with query: {query}, chat_id: {chat_id}, limit: {limit}, offset: {offset}")
        results = await search_telegram(query, chat_id, limit, offset=offset)
        logger.info(f"[{request_id}] Found {len(results)} messages (offset: {offset})")
        return results
    except Exception as e:
        logger.error(f"[{request_id}] Error searching messages: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def advanced_search(query: str, chat_id: str = None, limit: int = 100, **kwargs):
    """Advanced search for messages with additional filters."""
    try:
        request_id = f"adv_search_{int(time.time())}"
        logger.info(f"[{request_id}] Advanced search with query: {query}, chat_id: {chat_id}, limit: {limit}, filters: {kwargs}")
        results = await advanced_search_telegram(query, chat_id, limit, **kwargs)
        logger.info(f"[{request_id}] Found {len(results)} messages")
        return results
    except Exception as e:
        logger.error(f"[{request_id}] Error in advanced search: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def pattern_search(pattern: str, chat_id: str = None, limit: int = 100):
    """Search messages using regex patterns."""
    try:
        request_id = f"pattern_{int(time.time())}"
        logger.info(f"[{request_id}] Pattern search with pattern: {pattern}, chat_id: {chat_id}, limit: {limit}")
        results = await pattern_search_telegram(pattern, chat_id, limit)
        logger.info(f"[{request_id}] Found {len(results)} messages")
        return results
    except Exception as e:
        logger.error(f"[{request_id}] Error in pattern search: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def send_telegram_message(chat_id: str, message: str, reply_to_msg_id: int = None):
    """Send a message to a Telegram chat."""
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
    """List available Telegram dialogs with pagination."""
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
    """Get statistics for a Telegram chat."""
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
    """Generate Telegram links for messages."""
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
    """Export chat data in specified format."""
    try:
        request_id = f"export_{int(time.time())}"
        logger.info(f"[{request_id}] Exporting data for chat: {chat_id}, format: {format}")
        data = await export_chat_data(chat_id, format)
        logger.info(f"[{request_id}] Data exported successfully")
        return data
    except Exception as e:
        logger.error(f"[{request_id}] Error exporting data: {str(e)}\n{traceback.format_exc()}")
        raise

# Run the server if this file is executed directly
if __name__ == "__main__":
    if transport == "http":
        asyncio.run(mcp.run_sse_async())
    else:
        mcp.run()
