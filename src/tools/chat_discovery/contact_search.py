"""Telegram global contact search via contacts.SearchRequest."""

import logging
from typing import Any

from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import SearchRequest

from src.client.connection import (
    SessionNotAuthorizedError,
    TelegramTransportError,
    get_connected_client,
)
from src.utils.entity import (
    _matches_chat_type,
    _matches_public_filter,
    build_entity_dict,
)
from src.utils.error_handling import log_and_build_error

logger = logging.getLogger(__name__)


async def search_contacts_native(
    query: str,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
):
    """
    Search contacts using Telegram's native contacts.SearchRequest method via async generator.

    Yields contact dictionaries one by one for memory efficiency.

    Args:
        query: The search query (name, username, or phone number)
        limit: Maximum number of results to return
        chat_type: Optional filter for chat type ("private"|"group"|"channel")
        public: Optional filter for public discoverability (True=with username, False=without username)

    Yields:
        Contact dictionaries one by one
    """
    try:
        client = await get_connected_client()
        result = await client(SearchRequest(q=query, limit=limit))

        count = 0

        if hasattr(result, "users") and result.users:
            for user in result.users:
                if count >= limit:
                    break
                if chat_type and not _matches_chat_type(user, chat_type):
                    continue
                if not _matches_public_filter(user, public):
                    continue
                if info := build_entity_dict(user):
                    yield info
                    count += 1

        if hasattr(result, "chats") and result.chats and count < limit:
            for chat in result.chats:
                if count >= limit:
                    break
                if chat_type and not _matches_chat_type(chat, chat_type):
                    continue
                if not _matches_public_filter(chat, public):
                    continue
                if info := build_entity_dict(chat):
                    yield info
                    count += 1

    except FloodWaitError as e:
        logger.warning(
            "FloodWait on SearchRequest for '%s': %ds (~%.1fh)",
            query,
            e.seconds,
            e.seconds / 3600,
        )
        raise
    except SessionNotAuthorizedError:
        raise
    except TelegramTransportError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to search contacts: {e!s}") from e


async def _search_contacts_as_list(
    query: str,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Wrapper to collect generator results into a list for backward compatibility."""
    results = []
    params = {
        "query": query,
        "limit": limit,
        "chat_type": chat_type,
        "public": public,
    }

    async for item in search_contacts_native(query, limit, chat_type, public):
        results.append(item)

    if not results:
        return log_and_build_error(
            operation="search_contacts",
            error_message=f"No contacts found matching query '{query}'",
            params=params,
            exception=ValueError(f"No contacts found matching query '{query}'"),
        )

    logger.info(f"Found {len(results)} contacts using Telegram search for '{query}'")
    return results
