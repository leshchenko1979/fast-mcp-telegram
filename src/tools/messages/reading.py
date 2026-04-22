"""Message reading functionality."""

from __future__ import annotations

import logging
from typing import Any

from src.client.connection import get_connected_client
from src.tools.links import generate_telegram_links
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_message_result, transcribe_voice_messages

logger = logging.getLogger(__name__)


async def _build_message_link_mapping(
    chat_id: str, message_ids: list[int], resolved_entity=None
) -> dict[int, str]:
    """
    Build mapping of message IDs to their Telegram links.

    Args:
        chat_id: Chat identifier
        message_ids: List of message IDs to generate links for
        resolved_entity: Pre-resolved entity object to avoid API calls

    Returns empty dict if link generation fails.
    """
    try:
        links_info = await generate_telegram_links(
            chat_id, message_ids, resolved_entity=resolved_entity
        )
        message_links = links_info.get("message_links", []) or []
        return {
            mid: message_links[idx]
            for idx, mid in enumerate(message_ids)
            if idx < len(message_links)
        }
    except Exception:
        return {}


def _find_message_by_id(messages: list, requested_id: int, idx: int):
    """Find message by ID in fetched messages list."""
    if idx < len(messages):
        candidate = messages[idx]
        if candidate is not None and getattr(candidate, "id", None) == requested_id:
            return candidate

    return next(
        (
            m
            for m in messages
            if m is not None and getattr(m, "id", None) == requested_id
        ),
        None,
    )


async def _build_message_results(
    client,
    messages: list,
    message_ids: list[int],
    entity,
    id_to_link: dict,
    chat_dict: dict,
) -> list[dict[str, Any]]:
    """Build result dictionaries for all requested messages."""
    results: list[dict[str, Any]] = []

    for idx, requested_id in enumerate(message_ids):
        msg = _find_message_by_id(messages, requested_id, idx)

        if not msg:
            results.append(
                {
                    "id": requested_id,
                    "chat": chat_dict,
                    "error": "Message not found or inaccessible",
                }
            )
            continue

        link = id_to_link.get(getattr(msg, "id", requested_id))
        built = await build_message_result(
            client, msg, entity, link, include_chat_entity=False
        )
        results.append(built)

    return results


async def read_messages_by_ids(
    chat_id: str, message_ids: list[int]
) -> list[dict[str, Any]]:
    """
    Read specific messages by their IDs from a given chat.

    Args:
        chat_id: Target chat identifier (username like '@channel', numeric ID, or '-100...' form)
        message_ids: List of message IDs to fetch

    Returns:
        List of message dictionaries consistent with search results format
    """
    params = {
        "chat_id": chat_id,
        "message_ids": message_ids,
        "message_count": len(message_ids) if message_ids else 0,
    }
    log_operation_start("Reading messages by IDs", params)

    if not message_ids or not isinstance(message_ids, list):
        return [
            log_and_build_error(
                operation="read_messages",
                error_message="message_ids must be a non-empty list of integers",
                params=params,
                exception=ValueError(
                    "message_ids must be a non-empty list of integers"
                ),
            )
        ]

    client = await get_connected_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            return [
                log_and_build_error(
                    operation="read_messages",
                    error_message=f"Cannot find any entity corresponding to '{chat_id}'",
                    params=params,
                    exception=ValueError(
                        f"Cannot find any entity corresponding to '{chat_id}'"
                    ),
                )
            ]

        messages = await client.get_messages(entity, ids=message_ids)
        if not isinstance(messages, list):
            messages = [messages]

        id_to_link = await _build_message_link_mapping(
            chat_id, message_ids, resolved_entity=entity
        )
        chat_dict = build_entity_dict(entity) or {}

        results = await _build_message_results(
            client, messages, message_ids, entity, id_to_link, chat_dict
        )

        successful_results = [r for r in results if "error" not in r]
        if successful_results:
            await transcribe_voice_messages(successful_results, entity)

        successful_count = len(successful_results)
        log_operation_success(
            f"Retrieved {successful_count} messages out of {len(message_ids)} requested",
        )
        return results

    except Exception as e:
        error_response = log_and_build_error(
            operation="read_messages",
            error_message=f"Failed to read messages: {e!s}",
            params=params,
            exception=e,
        )
        return [error_response]
