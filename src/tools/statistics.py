from typing import Dict, Any, Optional
from loguru import logger
import time
from datetime import datetime
import traceback
from ..client.connection import get_client
from ..config.logging import format_diagnostic_info

async def get_chat_statistics(
    chat_id: str,
    include_message_stats: bool = True,
    include_member_stats: bool = True,
    time_range: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get detailed statistics for a specific chat.

    Args:
        chat_id: The ID of the chat to analyze
        include_message_stats: Whether to include message statistics
        include_member_stats: Whether to include member activity statistics
        time_range: Optional time range with 'start' and 'end' dates in ISO format
    """
    request_id = f"stats_{int(time.time()*1000)}"
    logger.debug(
        f"[{request_id}] Getting chat statistics",
        extra={
            "params": {
                "chat_id": chat_id,
                "include_message_stats": include_message_stats,
                "include_member_stats": include_member_stats,
                "time_range": time_range
            }
        }
    )

    client = await get_client()
    try:
        # Get chat entity
        chat = await client.get_entity(chat_id)

        # Initialize statistics
        stats = {
            "chat_id": chat_id,
            "chat_name": chat.title if hasattr(chat, 'title') else str(chat_id),
            "chat_type": chat.__class__.__name__,
            "timestamp": datetime.now().isoformat()
        }

        # Process time range
        start_date = None
        end_date = None
        if time_range:
            start_date = datetime.fromisoformat(time_range.get('start')) if time_range.get('start') else None
            end_date = datetime.fromisoformat(time_range.get('end')) if time_range.get('end') else None

        if include_message_stats:
            stats["message_stats"] = await _collect_message_stats(
                client, chat, start_date, end_date
            )

        if include_member_stats:
            stats["member_stats"] = await _collect_member_stats(
                client, chat, start_date, end_date
            )

        logger.info(f"[{request_id}] Successfully gathered statistics for chat {chat_id}")
        return stats

    except Exception as e:
        error_info = {
            "request_id": request_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            },
            "params": {
                "chat_id": chat_id,
                "time_range": time_range
            }
        }
        logger.error(f"[{request_id}] Error getting chat statistics", extra={"diagnostic_info": format_diagnostic_info(error_info)})
        raise

async def _collect_message_stats(client, chat, start_date, end_date) -> Dict[str, Any]:
    """Collect message statistics for a chat."""
    message_stats = {
        "total_messages": 0,
        "message_types": {
            "text": 0,
            "photo": 0,
            "video": 0,
            "document": 0,
            "voice": 0,
            "other": 0
        },
        "daily_activity": {},
        "hourly_activity": {str(i): 0 for i in range(24)}
    }

    async for message in client.iter_messages(chat, limit=1000):
        # Apply time range filter
        if start_date and message.date < start_date:
            continue
        if end_date and message.date > end_date:
            continue

        message_stats["total_messages"] += 1

        # Count message types
        if message.photo:
            message_stats["message_types"]["photo"] += 1
        elif message.video:
            message_stats["message_types"]["video"] += 1
        elif message.document:
            message_stats["message_types"]["document"] += 1
        elif message.voice:
            message_stats["message_types"]["voice"] += 1
        elif message.text:
            message_stats["message_types"]["text"] += 1
        else:
            message_stats["message_types"]["other"] += 1

        # Track activity patterns
        date_str = message.date.date().isoformat()
        hour_str = str(message.date.hour)

        message_stats["daily_activity"][date_str] = message_stats["daily_activity"].get(date_str, 0) + 1
        message_stats["hourly_activity"][hour_str] = message_stats["hourly_activity"].get(hour_str, 0) + 1

    return message_stats

async def _collect_member_stats(client, chat, start_date, end_date) -> Dict[str, Any]:
    """Collect member statistics for a chat."""
    member_stats = {
        "total_members": 0,
        "active_members": set(),
        "member_activity": {},
        "top_contributors": []
    }

    # Get total member count
    try:
        full_chat = await client.get_entity(chat.id)
        member_stats["total_members"] = full_chat.participants_count if hasattr(full_chat, 'participants_count') else 0
    except Exception as e:
        logger.warning(f"Could not get total member count: {e}")

    # Analyze member activity
    async for message in client.iter_messages(chat, limit=1000):
        if start_date and message.date < start_date:
            continue
        if end_date and message.date > end_date:
            continue

        if message.from_id:
            sender_id = str(message.from_id.user_id if hasattr(message.from_id, 'user_id') else message.from_id)
            member_stats["active_members"].add(sender_id)
            member_stats["member_activity"][sender_id] = member_stats["member_activity"].get(sender_id, 0) + 1

    # Calculate top contributors
    sorted_contributors = sorted(
        member_stats["member_activity"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]  # Top 10 contributors

    for user_id, message_count in sorted_contributors:
        try:
            user = await client.get_entity(int(user_id))
            member_stats["top_contributors"].append({
                "id": user_id,
                "name": user.first_name,
                "username": user.username,
                "message_count": message_count
            })
        except Exception as e:
            logger.warning(f"Could not get user info for {user_id}: {e}")
            member_stats["top_contributors"].append({
                "id": user_id,
                "name": "Unknown User",
                "message_count": message_count
            })

    # Convert active_members set to count for JSON serialization
    member_stats["active_members"] = len(member_stats["active_members"])

    return member_stats
