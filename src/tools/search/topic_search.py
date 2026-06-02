"""Shared Telethon SearchRequest helpers for thread/topic scoped search."""

from telethon.tl.functions.messages import SearchRequest
from telethon.tl.types import InputMessagesFilterEmpty

from .types import THREAD_SEARCH_CHUNK


def topic_search_request(
    peer,
    *,
    top_msg_id: int,
    offset_id: int = 0,
    query: str | None = None,
    limit: int = THREAD_SEARCH_CHUNK,
    min_date=None,
    max_date=None,
) -> SearchRequest:
    """Build SearchRequest with top_msg_id for supergroup or forum topic windows."""
    return SearchRequest(
        peer=peer,
        q=query or "",
        filter=InputMessagesFilterEmpty(),
        min_date=min_date,
        max_date=max_date,
        offset_id=offset_id,
        add_offset=0,
        limit=limit,
        max_id=0,
        min_id=0,
        hash=0,
        top_msg_id=top_msg_id,
    )
