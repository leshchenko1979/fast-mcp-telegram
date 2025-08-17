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
from src.tools.search import search_telegram
from src.tools.messages import send_message, list_dialogs
from src.tools.statistics import get_chat_statistics
from src.tools.links import generate_telegram_links
from src.tools.export import export_chat_data
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
    limit: int = 100,
    offset: int = 0,
    chat_type: str = None,
    min_date: str = None,
    max_date: str = None,
    auto_expand_batches: int = 2,
):
    """
    Search Telegram messages with pagination, date range, chat type filter, and auto-expansion.
    
    IMPORTANT: This tool supports two distinct search modes. Choose the correct mode based on your intent:
    
    1. PER-CHAT SEARCH (Recommended for contact-specific requests):
       - Use when you want to search within a specific contact's chat
       - Set chat_id to the target contact's chat ID
       - query can be empty (to get all messages) or specific (to search for content)
       - Example: "Find messages from John about project" → use chat_id=John's_chat_id, query="project"
    
    2. GLOBAL SEARCH (Use only for content across all chats):
       - Use when you want to find messages containing specific content across all chats
       - Do NOT set chat_id (leave as None)
       - query must contain the content you're searching for
       - Example: "Find all messages about project X" → use query="project X", chat_id=None
    
    COMMON MISTAKE TO AVOID:
    ❌ DON'T use contact names as query in global search
    ❌ Example: query="John" with chat_id=None (this searches for "John" in all chats)
    ✅ DO use chat_id to target specific contacts
    ✅ Example: chat_id=John's_chat_id with query="" (this gets all messages from John)
    
    RECOMMENDED WORKFLOW FOR CONTACT-SPECIFIC SEARCHES:
    1. Use search_contacts() to find the contact's chat ID by name/username
    2. Use the returned chat_id in this search function
    3. Set query to empty string or specific content you want to find
    
    ALTERNATIVE WORKFLOW (if search_contacts doesn't work):
    1. Use get_dialogs() to get a list of available chats/dialogs
    2. Find the contact you're looking for in the returned list
    3. Use the contact's chat_id in this search function
    
    Args:
        query: The search query string. For per-chat search, can be empty to get all messages.
               For global search, must contain the content you're searching for.
        chat_id: Chat ID to search within a specific chat. If provided, performs per-chat search.
                 If None, performs global search across all chats.
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
        if not results:
            return {"status": "No results found, custom message."}
        return results
    except Exception as e:
        logger.error(f"[{request_id}] Error searching messages: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def send_telegram_message(
    chat_id: str, 
    message: str, 
    reply_to_msg_id: int = None,
    parse_mode: str = None
):
    """
    Send a message to a Telegram chat, optionally as a reply.
    
    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send
        reply_to_msg_id: ID of the message to reply to (optional)
        parse_mode: Parse mode for message formatting (optional)
            - None: Plain text (default)
            - 'md' or 'markdown': Markdown formatting
            - 'html': HTML formatting
    
    Formatting Examples:
        Markdown: *bold*, _italic_, [link](url), `code`
        HTML: <b>bold</b>, <i>italic</i>, <a href="url">link</a>, <code>code</code>
    """
    try:
        request_id = f"send_{int(time.time())}"
        logger.info(f"[{request_id}] Sending message to chat: {chat_id}, parse_mode: {parse_mode}")
        result = await send_message(chat_id, message, reply_to_msg_id, parse_mode)
        logger.info(f"[{request_id}] Message sent successfully")
        return result
    except Exception as e:
        logger.error(f"[{request_id}] Error sending message: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def get_dialogs(limit: int = 100, offset: int = 0):
    """
    List available Telegram dialogs (chats) with pagination.
    
    IMPORTANT: This is an alternative tool for finding chat IDs. For better contact search, use search_contacts() first.
    
    RECOMMENDED WORKFLOW FOR CONTACT-SPECIFIC SEARCHES:
    1. Use search_contacts() to find the contact's chat ID by name/username (preferred method)
    2. Use the returned chat_id in search_messages() for targeted search
    
    ALTERNATIVE WORKFLOW (if search_contacts doesn't work):
    1. Use this tool to get a list of available chats/dialogs
    2. Find the contact you're looking for in the returned list
    3. Use the contact's chat_id in search_messages() for targeted search
    
    The returned data includes:
    - chat_id: Use this ID in search_messages() to target specific contacts
    - title/name: The contact or chat name
    - type: Whether it's a private chat, group, or channel
    
    Example workflow:
    1. User asks: "Find messages from John about the project"
    2. Use search_contacts("John") to find John's chat_id (preferred)
    3. Or use get_dialogs() to find John's chat_id (alternative)
    4. Use search_messages(chat_id=John's_chat_id, query="project")
    
    Args:
        limit: Maximum number of dialogs to return.
        offset: Number of dialogs to skip (for pagination).
    """
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
async def search_contacts(query: str, limit: int = 20):
    """
    Search contacts using Telegram's native search functionality.
    
    This tool uses Telegram's built-in contacts.SearchRequest method to find
    users and chats by name, username, or phone number. This is more powerful
    than get_dialogs() as it searches through your contacts and global Telegram users.
    
    IMPORTANT: This is the recommended method for finding specific contacts.
    
    FEATURES:
    - Searches through your contacts and global Telegram users
    - Supports search by name, username, or phone number
    - Returns detailed contact information including chat_id, username, phone
    - More accurate than manual search through dialogs
    
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
        limit: Maximum number of results to return
    """
    try:
        request_id = f"search_contacts_{int(time.time())}"
        logger.info(f"[{request_id}] Searching contacts: {query}, limit: {limit}")
        result = await search_contacts_telegram(query, limit)
        logger.info(f"[{request_id}] Found {len(result)} contacts")
        return result
    except Exception as e:
        logger.error(f"[{request_id}] Error searching contacts: {str(e)}\n{traceback.format_exc()}")
        raise

@mcp.tool()
async def get_contact_details(chat_id: str):
    """
    Get detailed information about a specific contact.
    
    Use this tool to get more information about a contact after finding their chat_id.
    
    Args:
        chat_id: The chat ID of the contact
    """
    try:
        request_id = f"contact_details_{int(time.time())}"
        logger.info(f"[{request_id}] Getting contact details for: {chat_id}")
        result = await get_contact_info(chat_id)
        logger.info(f"[{request_id}] Contact details retrieved successfully")
        return result
    except Exception as e:
        logger.error(f"[{request_id}] Error getting contact details: {str(e)}\n{traceback.format_exc()}")
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
