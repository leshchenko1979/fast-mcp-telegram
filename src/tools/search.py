from typing import Dict, List, Any, Optional
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty
from loguru import logger
import time
import json
from datetime import datetime
import traceback
from ..client.connection import connection_pool
from ..config.logging import format_diagnostic_info

async def search_telegram(
    query: str,
    chat_id: str = None,
    limit: int = 20,
    min_date: str = None,  # ISO format date string
    max_date: str = None   # ISO format date string
) -> List[Dict[str, Any]]:
    """
    Search for messages in Telegram chats using Telegram's global search functionality.

    Args:
        query: Search query string
        chat_id: Optional chat ID to search in specific chat. Can be:
                - Username/link (e.g. "@username" or "t.me/username")
                - Channel/Supergroup ID (e.g. "-100123456789")
                - Group ID (e.g. "-123456789")
                - Raw integer ID for direct chats
        limit: Maximum number of results to return
        min_date: Optional minimum date for search results (ISO format string)
        max_date: Optional maximum date for search results (ISO format string)

    Returns:
        List of dictionaries containing message information
    """
    if not query or not query.strip():
        raise ValueError("Search query must not be empty.")
    request_id = f"search_{int(time.time()*1000)}"

    # Convert date strings to datetime objects if provided
    min_datetime = datetime.fromisoformat(min_date) if min_date else None
    max_datetime = datetime.fromisoformat(max_date) if max_date else None

    logger.debug(
        f"[{request_id}] Starting Telegram search",
        extra={
            "search_params": {
                "query": query,
                "chat_id": chat_id,
                "limit": limit,
                "min_date": min_date,
                "max_date": max_date
            }
        }
    )

    async with connection_pool as client:
        try:
            results = []

            if chat_id:
                # Search in specific chat
                try:
                    # Handle different chat ID formats
                    try:
                        # Try parsing as integer first (for raw IDs)
                        chat_id_int = int(chat_id)
                        # Handle supergroup/channel format (-100...)
                        if str(chat_id).startswith('-100'):
                            chat_id_int = int(str(chat_id)[4:])
                        # Handle group format (-)
                        elif str(chat_id).startswith('-'):
                            chat_id_int = int(str(chat_id)[1:])
                        entity = await client.get_entity(chat_id_int)
                    except ValueError:
                        # If not an integer, try as username/link
                        entity = await client.get_entity(chat_id)

                    async for message in client.iter_messages(entity, search=query, limit=limit):
                        if message and message.text:
                            results.append({
                                "id": message.id,
                                "date": message.date.isoformat(),
                                "chat_id": message.chat_id,
                                "chat_name": entity.title if hasattr(entity, 'title') else str(entity.id),
                                "text": message.text,
                                "reply_to_msg_id": message.reply_to_msg_id if hasattr(message, 'reply_to_msg_id') else None
                            })
                except Exception as e:
                    logger.error(f"Error searching in specific chat: {str(e)}")
                    logger.debug(f"Full error details for chat {chat_id}:", exc_info=True)
                    raise
            else:
                # Global search
                try:
                    result = await client(SearchGlobalRequest(
                        q=query,
                        filter=InputMessagesFilterEmpty(),
                        min_date=min_datetime,
                        max_date=max_datetime,
                        offset_rate=0,
                        offset_peer=InputPeerEmpty(),
                        offset_id=0,
                        limit=limit
                    ))

                    if hasattr(result, 'messages'):
                        for message in result.messages:
                            if message and hasattr(message, 'message') and message.message:
                                try:
                                    chat = await client.get_entity(message.peer_id)
                                    chat_name = chat.title if hasattr(chat, 'title') else str(getattr(chat, 'id', 'Unknown'))

                                    results.append({
                                        "id": message.id,
                                        "date": message.date.isoformat(),
                                        "chat_id": getattr(message.peer_id, 'channel_id',
                                                 getattr(message.peer_id, 'chat_id',
                                                 getattr(message.peer_id, 'user_id', None))),
                                        "chat_name": chat_name,
                                        "text": message.message,
                                        "reply_to_msg_id": message.reply_to.reply_to_msg_id if hasattr(message, 'reply_to') else None
                                    })
                                except Exception as e:
                                    logger.warning(f"Error processing message: {e}")
                                    continue

                except Exception as e:
                    logger.error(f"Error in global search: {e}")
                    raise

            logger.info(f"[{request_id}] Found {len(results)} messages matching query: {query}")
            return results[:limit]

        except Exception as e:
            error_info = {
                "request_id": request_id,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                "search_params": {
                    "query": query,
                    "chat_id": chat_id,
                    "limit": limit,
                    "min_date": min_date,
                    "max_date": max_date
                }
            }
            logger.error(f"[{request_id}] Error searching Telegram", extra=error_info)
            raise

async def advanced_search_telegram(
    query: str,
    filters: str = None,
    date_range: str = None,
    chat_ids: str = None,
    message_types: str = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Advanced search for messages with filtering options.
    """
    request_id = f"adv_search_{int(time.time()*1000)}"

    # Parse parameters
    try:
        filters_dict = json.loads(filters) if filters else {}
        date_range_dict = json.loads(date_range) if date_range else {}
        chat_ids_list = [str(x).strip() for x in chat_ids.split(',')] if chat_ids else None
        message_types_list = [x.strip() for x in message_types.split(',')] if message_types else None
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

    # Convert timestamps to datetime
    start_datetime = datetime.fromtimestamp(date_range_dict['start']) if date_range_dict.get('start') else None
    end_datetime = datetime.fromtimestamp(date_range_dict['end']) if date_range_dict.get('end') else None

    async with connection_pool as client:
        try:
            results = []
            query = query.lower()

            # Get search chats
            search_chats = []
            if chat_ids_list:
                for chat_id in chat_ids_list:
                    try:
                        entity = await client.get_entity(chat_id)
                        search_chats.append(entity)
                    except Exception as e:
                        logger.warning(f"Error getting entity for chat {chat_id}: {e}")
            else:
                async for dialog in client.iter_dialogs():
                    search_chats.append(dialog.entity)

            # Search messages
            for chat in search_chats:
                if len(results) >= limit:
                    break

                try:
                    async for message in client.iter_messages(chat, limit=limit * 2):
                        if len(results) >= limit:
                            break

                        # Apply filters
                        if not _passes_filters(message, start_datetime, end_datetime,
                                            message_types_list, filters_dict, query):
                            continue

                        # Add message to results
                        results.append(_format_message(message, chat))

                except Exception as e:
                    logger.warning(f"Error searching in chat {getattr(chat, 'title', chat.id)}: {e}")
                    continue

            return results[:limit]

        except Exception as e:
            error_info = {
                "request_id": request_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "params": {
                    "query": query,
                    "filters": filters_dict,
                    "date_range": date_range_dict,
                    "chat_ids": chat_ids_list,
                    "message_types": message_types_list
                }
            }
            logger.error(f"Error in advanced search", extra={"diagnostic_info": format_diagnostic_info(error_info)})
            raise

def _passes_filters(message, start_datetime, end_datetime, message_types_list, filters_dict, query):
    """Check if message passes all filters."""
    # Date filter
    if start_datetime and message.date < start_datetime:
        return False
    if end_datetime and message.date > end_datetime:
        return False

    # Message type filter
    if message_types_list:
        msg_type = _get_message_type(message)
        if msg_type not in message_types_list:
            return False

    # Custom filters
    if filters_dict:
        if filters_dict.get('media_only') and not message.media:
            return False
        if filters_dict.get('links_only') and not message.entities:
            return False
        if filters_dict.get('files_only') and not message.document:
            return False

    # Query filter
    if not message.text or query not in message.text.lower():
        return False

    return True

def _get_message_type(message):
    """Get message type."""
    if message.photo:
        return 'photo'
    elif message.video:
        return 'video'
    elif message.document:
        return 'document'
    elif message.voice:
        return 'voice'
    return 'text'

def _format_message(message, chat):
    """Format message for response."""
    return {
        "id": message.id,
        "date": message.date.isoformat(),
        "chat_id": message.chat_id,
        "chat_name": chat.title if hasattr(chat, 'title') else str(chat.id),
        "text": message.text,
        "type": _get_message_type(message),
        "has_media": bool(message.media),
        "reply_to_msg_id": message.reply_to_msg_id if hasattr(message, 'reply_to_msg_id') else None,
        "forward_from": str(message.forward.from_id) if message.forward else None
    }

async def pattern_search_telegram(
    pattern: str,
    chat_ids: List[str] = None,
    pattern_type: str = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Search for messages matching a specific pattern in Telegram chats.
    """
    request_id = f"pattern_{int(time.time()*1000)}"
    logger.debug(
        f"[{request_id}] Searching messages by pattern",
        extra={
            "params": {
                "pattern": pattern,
                "chat_ids": chat_ids,
                "pattern_type": pattern_type,
                "limit": limit
            }
        }
    )

    async with connection_pool as client:
        try:
            results = []
            for chat_id in (chat_ids or [None]):
                try:
                    if chat_id:
                        entity = await client.get_entity(chat_id)
                    else:
                        entity = None

                    async for message in client.iter_messages(
                        entity,
                        search=pattern,
                        limit=limit
                    ):
                        if pattern_type:
                            if pattern_type == "media" and not message.media:
                                continue
                            if pattern_type == "text" and not message.text:
                                continue
                            if pattern_type == "file" and not message.file:
                                continue

                        results.append({
                            'id': message.id,
                            'date': message.date.isoformat(),
                            'text': message.text,
                            'from_user': str(message.from_id) if message.from_id else None,
                            'chat_id': str(message.chat_id) if message.chat_id else None,
                            'has_media': bool(message.media),
                            'has_file': bool(message.file)
                        })

                        if len(results) >= limit:
                            break

                except Exception as e:
                    logger.warning(f"Error searching in chat {chat_id}: {e}")
                    continue

            logger.info(f"[{request_id}] Found {len(results)} matching messages", extra={"response": results})
            return results[:limit] if limit else results

        except Exception as e:
            error_info = {
                "request_id": request_id,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                "params": {
                    "pattern": pattern,
                    "chat_ids": chat_ids,
                    "pattern_type": pattern_type,
                    "limit": limit
                }
            }
            logger.error(f"[{request_id}] Error searching messages by pattern", extra={"diagnostic_info": format_diagnostic_info(error_info)})
            raise
