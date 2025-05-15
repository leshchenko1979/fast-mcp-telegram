from typing import Dict, Any, Optional
from loguru import logger
import time
import json
import io
import csv
from datetime import datetime
import traceback
from ..client.connection import get_client
from ..config.logging import format_diagnostic_info
from src.utils.entity import build_entity_dict

async def export_chat_data(
    chat_id: int,
    export_format: str = "json",
    time_range: Optional[Dict[str, str]] = None,
    include_media: bool = False,
    anonymize: bool = False,
    message_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Export chat data in various formats.

    Args:
        chat_id: The ID of the chat to export
        export_format: Format to export in ('json', 'csv', 'txt')
        time_range: Optional time range with 'start' and 'end' dates in ISO format
        include_media: Whether to include media information
        anonymize: Whether to anonymize user information
        message_limit: Maximum number of messages to export
    """
    request_id = f"export_{int(time.time()*1000)}"
    logger.debug(
        f"[{request_id}] Starting chat export",
        extra={
            "export_params": {
                "chat_id": chat_id,
                "format": export_format,
                "time_range": time_range,
                "include_media": include_media,
                "anonymize": anonymize,
                "message_limit": message_limit
            }
        }
    )

    client = await get_client()
    try:
        # Get chat entity
        chat = await client.get_entity(chat_id)

        # Process time range
        start_date = None
        end_date = None
        if time_range:
            start_date = datetime.fromisoformat(time_range.get('start')) if time_range.get('start') else None
            end_date = datetime.fromisoformat(time_range.get('end')) if time_range.get('end') else None

        # Collect messages
        messages = []
        message_count = 0
        async for message in client.iter_messages(chat):
            if message_limit and message_count >= message_limit:
                break

            # Apply time range filter
            if start_date and message.date < start_date:
                continue
            if end_date and message.date > end_date:
                continue

            # Process message data
            message_data = await _process_message(message, anonymize, include_media)
            messages.append(message_data)
            message_count += 1

        # Prepare export data
        export_data = {
            "chat_info": build_entity_dict(chat),
            "messages": messages
        }

        # Format data according to export_format
        formatted_data = await _format_export_data(export_data, export_format)

        logger.info(f"[{request_id}] Successfully exported {len(messages)} messages from chat {chat_id}")
        return formatted_data

    except Exception as e:
        error_info = {
            "request_id": request_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            },
            "export_params": {
                "chat_id": chat_id,
                "format": export_format,
                "time_range": time_range,
                "include_media": include_media,
                "anonymize": anonymize,
                "message_limit": message_limit
            }
        }
        logger.error(f"[{request_id}] Error exporting chat data", extra={"diagnostic_info": format_diagnostic_info(error_info)})
        raise

async def _process_message(message, anonymize: bool, include_media: bool) -> Dict[str, Any]:
    """Process a single message for export."""
    message_data = {
        "id": message.id,
        "date": message.date.isoformat(),
        "text": message.text
    }

    # Add sender information
    if message.sender:
        if anonymize:
            message_data["sender"] = f"user_{hash(str(message.sender.id)) % 10000}"
        else:
            message_data["sender"] = build_entity_dict(message.sender)

    # Add media information
    if include_media and message.media:
        media_info = {
            "type": str(message.media.__class__.__name__)
        }

        if message.photo:
            media_info["photo_id"] = message.photo.id
            media_info["dimensions"] = f"{message.photo.dc_id}x{message.photo.size}"
        elif message.document:
            media_info["document_id"] = message.document.id
            media_info["file_name"] = getattr(message.document, 'file_name', None)
            media_info["mime_type"] = getattr(message.document, 'mime_type', None)

        message_data["media"] = media_info

    # Add reply information
    if message.reply_to:
        message_data["reply_to_msg_id"] = message.reply_to.reply_to_msg_id

    return message_data

async def _format_export_data(export_data: Dict[str, Any], export_format: str) -> Dict[str, Any]:
    """Format export data according to specified format."""
    if export_format == "json":
        return {
            "format": "json",
            "data": json.dumps(export_data, ensure_ascii=False, indent=2)
        }

    elif export_format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["id", "date", "sender", "text", "media_type", "reply_to_msg_id"]
        )
        writer.writeheader()

        for msg in export_data["messages"]:
            row = {
                "id": msg["id"],
                "date": msg["date"],
                "sender": msg["sender"] if isinstance(msg["sender"], str) else msg["sender"].get("name"),
                "text": msg["text"],
                "media_type": msg.get("media", {}).get("type", ""),
                "reply_to_msg_id": msg.get("reply_to_msg_id", "")
            }
            writer.writerow(row)

        return {
            "format": "csv",
            "data": output.getvalue()
        }

    elif export_format == "txt":
        lines = []
        for msg in export_data["messages"]:
            sender = msg["sender"]
            sender_name = sender if isinstance(sender, str) else sender.get("name", "Unknown")

            lines.append(f"[{msg['date']}] {sender_name}: {msg['text']}")
            if msg.get("media"):
                lines.append(f"[Media: {msg['media']['type']}]")
            if msg.get("reply_to_msg_id"):
                lines.append(f"[Reply to message: {msg['reply_to_msg_id']}]")
            lines.append("")  # Empty line between messages

        return {
            "format": "txt",
            "data": "\n".join(lines)
        }

    else:
        raise ValueError(f"Unsupported export format: {export_format}")
