from typing import Dict, List, Any
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty
from loguru import logger
import time
from datetime import datetime
import traceback
from ..client.connection import get_client
from src.tools.links import generate_telegram_links
from src.utils.entity import build_entity_dict

async def search_telegram(
    query: str,
    chat_id: str = None,
    limit: int = 20,
    min_date: str = None,  # ISO format date string
    max_date: str = None,  # ISO format date string
    offset: int = 0,       # Offset for pagination
    chat_type: str = None, # 'private', 'group', 'channel', or None
    auto_expand_batches: int = 2  # Maximum additional batches to fetch if not enough filtered results
) -> List[Dict[str, Any]]:
    """
    Search for messages in Telegram chats using Telegram's global or per-chat search functionality with pagination, optional chat type filtering, and auto-expansion for filtered results.

    Args:
        query: Search query string. If chat_id is provided, query may be empty to fetch all messages from that chat (optionally filtered by min_date and max_date). If chat_id is not provided (global search), query must not be empty.
        chat_id: Optional chat ID to search in a specific chat. If not provided, performs a global search.
        limit: Maximum number of results to return
        min_date: Optional minimum date for search results (ISO format string)
        max_date: Optional maximum date for search results (ISO format string)
        offset: Number of messages to skip (for pagination)
        chat_type: Optional filter for chat type ('private', 'group', 'channel')
        auto_expand_batches: Maximum additional batches to fetch if not enough filtered results (default 2)

    Returns:
        List of dictionaries containing message information

    Note:
        - For per-chat search (chat_id provided), an empty query returns all messages in the specified chat (optionally filtered by date).
        - For global search (no chat_id), query must not be empty.
    """
    if (not query or not query.strip()) and not chat_id:
        raise ValueError("Search query must not be empty for global search.")
    request_id = f"search_{int(time.time()*1000)}"
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
                "max_date": max_date,
                "offset": offset,
                "chat_type": chat_type
            }
        }
    )
    client = await get_client()
    try:
        if chat_id:
            # Search in a specific chat
            try:
                # Handle different chat ID formats
                try:
                    chat_id_int = int(chat_id)
                    if str(chat_id).startswith('-100'):
                        chat_id_int = int(str(chat_id)[4:])
                    elif str(chat_id).startswith('-'):
                        chat_id_int = int(str(chat_id)[1:])
                    entity = await client.get_entity(chat_id_int)
                except ValueError:
                    entity = await client.get_entity(chat_id)
                results = await _search_in_single_chat(client, entity, query, limit, offset, chat_type, auto_expand_batches)
            except Exception as e:
                logger.error(f"Error searching in specific chat: {str(e)}")
                logger.debug(f"Full error details for chat {chat_id}:", exc_info=True)
                raise
        else:
            # Global search
            try:
                results = await _search_global(client, query, limit, min_datetime, max_datetime, offset, chat_type, auto_expand_batches)
            except Exception as e:
                logger.error(f"Error in global search: {e}")
                raise
        logger.info(f"[{request_id}] Found {len(results)} messages matching query: {query}")
        return results
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
                "max_date": max_date,
                "offset": offset,
                "chat_type": chat_type
            }
        }
        logger.error(f"[{request_id}] Error searching Telegram", extra=error_info)
        raise

async def _search_in_single_chat(client, entity, query, limit, offset, chat_type, auto_expand_batches):
    results = []
    count = 0
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0
    while batch_count < max_batches and len(results) < limit:
        batch = []
        async for message in client.iter_messages(entity, search=query, offset_id=next_offset_id):
            if not message or not getattr(message, 'text', None):
                continue
            if count < offset:
                count += 1
                continue
            batch.append(message)
            if len(batch) >= limit * 2:
                break
        if not batch:
            break
        for message in batch:
            identifier = getattr(entity, 'username', None)
            if not identifier and hasattr(entity, 'id'):
                if str(entity.id).startswith('-100'):
                    identifier = str(entity.id)
                elif entity.__class__.__name__ in ['Channel', 'Chat', 'ChannelForbidden']:
                    identifier = f'-100{entity.id}'
                else:
                    identifier = str(entity.id)
            links = await generate_telegram_links(identifier, [message.id])
            link = links.get('message_links', [None])[0]
            if chat_type:
                if (chat_type == 'private' and entity.__class__.__name__ == 'User') or \
                   (chat_type == 'group' and entity.__class__.__name__ == 'Chat') or \
                   (chat_type == 'channel' and entity.__class__.__name__ in ['Channel', 'ChannelForbidden']):
                    results.append(await _build_result(client, message, entity, link))
            else:
                results.append(await _build_result(client, message, entity, link))
            if len(results) >= limit:
                break
        if batch:
            next_offset_id = batch[-1].id
        batch_count += 1
    return results[:limit]

async def _search_global(client, query, limit, min_datetime, max_datetime, offset, chat_type, auto_expand_batches):
    results = []
    batch_count = 0
    max_batches = 1 + auto_expand_batches if chat_type else 1
    next_offset_id = 0
    while batch_count < max_batches and len(results) < limit:
        offset_id = next_offset_id
        result = await client(SearchGlobalRequest(
            q=query,
            filter=InputMessagesFilterEmpty(),
            min_date=min_datetime,
            max_date=max_datetime,
            offset_rate=0,
            offset_peer=InputPeerEmpty(),
            offset_id=offset_id,
            limit=limit * 2
        ))
        if not hasattr(result, 'messages') or not result.messages:
            break
        for message in result.messages:
            if message and hasattr(message, 'message') and message.message:
                try:
                    chat = await client.get_entity(message.peer_id)
                    identifier = getattr(chat, 'username', None)
                    if not identifier and hasattr(chat, 'id'):
                        if str(chat.id).startswith('-100'):
                            identifier = str(chat.id)
                        elif chat.__class__.__name__ in ['Channel', 'Chat', 'ChannelForbidden']:
                            identifier = f'-100{chat.id}'
                        else:
                            identifier = str(chat.id)
                    links = await generate_telegram_links(identifier, [message.id])
                    link = links.get('message_links', [None])[0]
                    if chat_type:
                        if (chat_type == 'private' and chat.__class__.__name__ == 'User') or \
                           (chat_type == 'group' and chat.__class__.__name__ == 'Chat') or \
                           (chat_type == 'channel' and chat.__class__.__name__ in ['Channel', 'ChannelForbidden']):
                            results.append(await _build_result(client, message, chat, link))
                    else:
                        results.append(await _build_result(client, message, chat, link))
                    if len(results) >= limit:
                        break
                except Exception as e:
                    logger.warning(f"Error processing message: {e}")
                    continue
        if result.messages:
            next_offset_id = result.messages[-1].id
        batch_count += 1
    return results[:limit]

async def _build_result(client, message, entity_or_chat, link):
    sender = await _get_sender_info(client, message)
    chat = build_entity_dict(entity_or_chat)
    return {
        "id": message.id,
        "date": message.date.isoformat(),
        "chat": chat,
        "text": getattr(message, 'text', None) or getattr(message, 'message', None),
        "reply_to_msg_id": getattr(message, 'reply_to_msg_id', None) or getattr(getattr(message, 'reply_to', None), 'reply_to_msg_id', None),
        "link": link,
        "sender": sender
    }

async def _get_sender_info(client, message):
    if hasattr(message, 'sender_id') and message.sender_id:
        try:
            sender = await client.get_entity(message.sender_id)
            return build_entity_dict(sender)
        except Exception:
            return {"id": message.sender_id}
    return None
