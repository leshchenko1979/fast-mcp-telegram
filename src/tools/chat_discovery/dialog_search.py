"""Local dialog iteration with client-side matching (iter_dialogs)."""

from datetime import datetime

from src.client.connection import (
    SessionNotAuthorizedError,
    TelegramTransportError,
    get_connected_client,
)
from src.utils.entity import (
    _matches_chat_type,
    _matches_public_filter,
    build_dialog_entity_dict,
    entity_matches_dialog_query,
)

from .date_helpers import _dialog_in_date_range


async def search_dialogs_impl(
    query: str | None = None,
    limit: int = 20,
    chat_type: str | None = None,
    public: bool | None = None,
    min_date_dt: datetime | None = None,
    max_date_dt: datetime | None = None,
    folder_id: int | None = None,
):
    """
    Search dialogs using client.iter_dialogs() with optional date filtering.

    Unlike search_contacts_native() which uses Telegram's SearchRequest,
    this function uses iter_dialogs() which provides dialog.date for
    last activity tracking. However, iter_dialogs() has no query parameter,
    so query matching is done client-side against entity display names.

    Note: iter_dialogs() may return pinned chats that break chronological ordering,
    so early break optimization is not safe when date filtering.

    Args:
        query: Search query (matched against title, username, first_name, phone). Optional.
        limit: Maximum number of results to return
        chat_type: Optional filter for chat type ("private"|"group"|"channel")
        public: Optional filter for public discoverability
        min_date_dt: Minimum last activity date as parsed datetime (UTC)
        max_date_dt: Maximum last activity date as parsed datetime (UTC)
        folder_id: Filter by folder ID (int). Note: folder 0 (default) shows as null on Dialog objects.

    Yields:
        Contact dictionaries one by one with last_activity_date field
    """
    try:
        client = await get_connected_client()
        query_lower = query.lower().strip() if query else ""

        count = 0
        # Fetch enough dialogs to have a reasonable chance of finding the target.
        # limit*10 alone can miss groups/channels beyond position N*10 for large accounts.
        # The +200 floor ensures at least ~200 dialogs are checked even at small limits.
        iter_limit = max(limit * 10, limit + 200)
        async for dialog in client.iter_dialogs(limit=iter_limit, folder=folder_id):  # type: ignore[arg-type]  # ty: ignore
            if count >= limit:
                break

            entity = getattr(dialog, "entity", None)
            if not entity:
                continue

            if query_lower and not entity_matches_dialog_query(entity, query_lower):
                continue

            dialog_date = getattr(dialog, "date", None)
            if not await _dialog_in_date_range(
                entity, client, dialog_date, min_date_dt, max_date_dt
            ):
                continue

            if chat_type and not _matches_chat_type(entity, chat_type):
                continue
            if not _matches_public_filter(entity, public):
                continue

            if result := build_dialog_entity_dict(dialog, entity):
                yield result
                count += 1

    except SessionNotAuthorizedError:
        raise
    except TelegramTransportError:
        raise
