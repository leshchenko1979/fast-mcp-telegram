"""
Main server module for the Telegram bot functionality.
Provides API endpoints and core bot features.
"""

import os
import time
from loguru import logger
from fastmcp import FastMCP
import traceback
import asyncio
import sys
import os

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.logging import setup_logging
from src.tools.search import search_messages as search_messages_impl
from src.tools.messages import send_message, edit_message, read_messages_by_ids


from src.tools.links import generate_telegram_links
from src.tools.mtproto import invoke_mtproto_method
from src.tools.contacts import get_contact_info, search_contacts_telegram

IS_TEST_MODE = '--test-mode' in sys.argv

if IS_TEST_MODE:
    transport = "http"
    host = "127.0.0.1"
    port = 8000
else:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP("Telegram MCP Server")

# Set up logging
setup_logging()

# Register tools with the MCP server
@mcp.tool()
async def search_messages(
    query: str,
    chat_id: str = None,
    limit: int = 50,
    offset: int = 0,
    chat_type: str = None,
    min_date: str = None,
    max_date: str = None,
    auto_expand_batches: int = 2,
    include_total_count: bool = False,
):
    """
    Search Telegram messages with pagination, filters, and auto-expansion.
    
    ⚠️ PERFORMANCE: Keep limit at 50 or lower to prevent context overflow.
    
    SEARCH MODES:
    1. PER-CHAT: Set chat_id, query optional (gets all messages or searches content)
    2. GLOBAL: No chat_id, query required (searches across all chats)
    
    COMMON MISTAKE: Don't use contact names as query in global search.
    ✅ Use search_contacts() first to get chat_id, then search_messages(chat_id=...)
    
    TOTAL COUNT: Set include_total_count=True for per-chat searches to get total matching messages.
    
    Args:
        query: Search query (empty for all messages in per-chat search)
        chat_id: Target chat ID (per-chat search) or None (global search)
        limit: Max results (RECOMMENDED: 50 or lower)
        offset: Pagination offset
        chat_type: Filter by 'private', 'group', 'channel'
        min_date: Minimum date (ISO format)
        max_date: Maximum date (ISO format)
        auto_expand_batches: Additional batches for filtered results (default 2)
        include_total_count: Include total count in response (per-chat only)
    """
    try:
        request_id = f"search_{int(time.time())}"
        logger.info(f"[{request_id}] Searching messages with query: {query}, chat_id: {chat_id}, limit: {limit}, offset: {offset}, chat_type: {chat_type}, min_date: {min_date}, max_date: {max_date}, auto_expand_batches: {auto_expand_batches}")
        search_result = await search_messages_impl(
            query,
            chat_id,
            limit,
            min_date=min_date,
            max_date=max_date,
            offset=offset,
            chat_type=chat_type,
            auto_expand_batches=auto_expand_batches,
            include_total_count=include_total_count
        )
        
        # Handle the new response structure
        if isinstance(search_result, dict) and 'messages' in search_result:
            messages = search_result['messages']
            logger.info(f"[{request_id}] Found {len(messages)} messages (offset: {offset}, chat_type: {chat_type}, min_date: {min_date}, max_date: {max_date}, auto_expand_batches: {auto_expand_batches})")
            if not messages:
                return {"status": "No results found, custom message."}
            return search_result
        else:
            # Fallback for old response format
            logger.info(f"[{request_id}] Found {len(search_result)} messages (offset: {offset}, chat_type: {chat_type}, min_date: {min_date}, max_date: {max_date}, auto_expand_batches: {auto_expand_batches})")
            if not search_result:
                return {"status": "No results found, custom message."}
            return search_result
    except Exception as e:
        logger.error(f"[{request_id}] Error searching messages: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def send_or_edit_message(
    chat_id: str, 
    message: str, 
    reply_to_msg_id: int = None,
    parse_mode: str = None,
    message_id: int = None
):
    """
    Send a message to a Telegram chat, optionally as a reply, or edit an existing message.
    
    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send or new text for editing
        reply_to_msg_id: ID of the message to reply to (optional, only for sending)
        parse_mode: Parse mode for message formatting (optional)
            - None: Plain text (default)
            - 'md' or 'markdown': Markdown formatting
            - 'html': HTML formatting
        message_id: ID of the message to edit (optional). If provided, edits the message instead of sending a new one.
    
    Formatting Examples:
        Markdown: *bold*, _italic_, [link](url), `code`
        HTML: <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>
    """
    if message_id is not None:
        # Edit existing message
        result = await edit_message(chat_id, message_id, message, parse_mode)
    else:
        # Send new message
        result = await send_message(chat_id, message, reply_to_msg_id, parse_mode)
    
    return result

@mcp.tool()
async def read_messages(chat_id: str, message_ids: list[int]):
    """
    Read specific messages by their IDs in a given chat.
    
    Args:
        chat_id: Target chat identifier (username like '@channel', numeric ID, or '-100...' form)
        message_ids: List of message IDs to fetch
    """
    results = await read_messages_by_ids(chat_id, message_ids)
    return results





@mcp.tool()
async def generate_links(chat_id: str, message_ids: list[int]):
    """Generate Telegram links for specific messages in a chat."""
    links = await generate_telegram_links(chat_id, message_ids)
    return links

# Removed export_data tool as export functionality has been deprecated

@mcp.tool()
async def search_contacts(query: str, limit: int = 20):
    """
    Search contacts using Telegram's native search functionality.
    
    This tool uses Telegram's built-in contacts.SearchRequest method to find
    users and chats by name, username, or phone number. This searches through your contacts and global Telegram users.
    
    ⚠️ PERFORMANCE NOTE: 
    - Contact searches typically return fewer results than message searches
    - Default limit of 20 is usually sufficient for contact resolution
    - Only increase limit if you need to find contacts with very common names
    
    IMPORTANT: This is the recommended method for finding specific contacts.
    
    FEATURES:
    - Searches through your contacts and global Telegram users
    - Supports search by name, username, or phone number
    - Returns detailed contact information including chat_id, username, phone
    
    WORKFLOW:
    1. User asks: "Find messages from @username or John Doe"
    2. Use this tool: search_contacts(query="username") or search_contacts(query="John Doe")
    3. Get the chat_id from the result
    4. Use search_messages(chat_id=chat_id, query="your_search_term")
    
    Example:
    - search_contacts("Евдокимов") → finds all contacts with "Евдокимов" in name
    - search_contacts("@username") → finds specific user by username
    - search_contacts("+1234567890") → finds contact by phone number
    
    Args:
        query: The search query (name, username, or phone number)
        limit: Maximum number of results to return (RECOMMENDED: 20 or lower)
    """
    result = await search_contacts_telegram(query, limit)
    return result

@mcp.tool()
async def get_contact_details(chat_id: str):
    """
    Get detailed information about a specific contact.
    
    Use this tool to get more information about a contact after finding their chat_id.
    
    Args:
        chat_id: The chat ID of the contact
    """
    result = await get_contact_info(chat_id)
    return result



@mcp.tool()
async def invoke_mtproto(method_full_name: str, params: dict):
    """Invoke any MTProto method by full name and parameters."""
    result = await invoke_mtproto_method(method_full_name, params)
    return result

def shutdown_procedure():
    """Synchronously performs async cleanup."""
    logger.info("Starting cleanup procedure.")
    from src.client.connection import cleanup_client

    # Create a new event loop for cleanup to avoid conflicts.
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup_client())
        loop.close()
        logger.info("Cleanup successful.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}\n{traceback.format_exc()}")

# Run the server if this file is executed directly
if __name__ == "__main__":
    if transport == "http":
        try:
            mcp.run(transport="http", host=host, port=port)
        finally:
            # Ensure cleanup on HTTP server shutdown
            shutdown_procedure()
    else:
        # For stdio transport, just run directly
        # FastMCP handles the stdio communication automatically
        try:
            mcp.run(transport="stdio")
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Initiating shutdown.")
        finally:
            shutdown_procedure()
