"""get_messages entry point and mode dispatch."""

import logging
from typing import Any

from src.client.connection import get_connected_client
from src.tools.messages import read_messages_by_ids
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.message_format import response_attachment_warning
from src.utils.message_order import apply_ascending_message_order

from .context_enrichment import _enrich_with_context
from .replies import _handle_reply_mode
from .search_mode import _DEFAULT_MAX_CONCURRENT, _handle_query_mode
from .types import MessageRetrievalMode, ThreadScope, resolve_mode

logger = logging.getLogger(__name__)


def _build_search_params(
    *,
    query: str | None,
    chat_id: str | None,
    message_ids: list[int] | None,
    reply_to_id: int | None,
    thread_scope: ThreadScope,
    limit: int,
    min_date: str | None,
    max_date: str | None,
    chat_type: str | None,
    public: bool | None,
    auto_expand_batches: int,
    include_total_count: bool,
    max_concurrent: int | None = None,
    from_user: str | None = None,
    context: int = 0,
    include_replies: bool = False,
) -> dict[str, Any]:
    return {
        "query": query,
        "chat_id": chat_id,
        "message_ids": message_ids,
        "reply_to_id": reply_to_id,
        "thread_scope": thread_scope,
        "limit": limit,
        "min_date": min_date,
        "max_date": max_date,
        "chat_type": chat_type,
        "public": public,
        "auto_expand_batches": auto_expand_batches,
        "include_total_count": include_total_count,
        "max_concurrent": max_concurrent,
        "from_user": from_user,
        "context": context,
        "include_replies": include_replies,
        "is_global_search": chat_id is None,
        "has_query": bool(query and query.strip()),
        "has_date_filter": bool(min_date or max_date),
        "message_count": len(message_ids) if message_ids else 0,
    }


def _unsupported_date_filter_error(
    params: dict[str, Any], mode_label: str
) -> dict[str, Any] | None:
    if not params.get("has_date_filter"):
        return None
    return log_and_build_error(
        operation="get_messages",
        error_message=f"min_date and max_date are not supported for {mode_label} mode",
        params=params,
        exception=ValueError(f"Date filters not supported for {mode_label} mode"),
    )


async def _dispatch_search_mode(
    mode: MessageRetrievalMode,
    params: dict[str, Any],
    *,
    query: str | None,
    chat_id: str | None,
    message_ids: list[int] | None,
    reply_to_id: int | None,
    limit: int,
    min_date: str | None,
    max_date: str | None,
    chat_type: str | None,
    public: bool | None,
    auto_expand_batches: int,
    include_total_count: bool,
    thread_scope: ThreadScope,
    from_user: str | None = None,
    context: int = 0,
    include_replies: bool = False,
) -> dict[str, Any]:
    if mode is MessageRetrievalMode.MESSAGE_IDS:
        if chat_id is None or message_ids is None:
            return log_and_build_error(
                operation="get_messages",
                error_message="chat_id and message_ids required for message_ids mode",
                params=params,
                exception=ValueError("Missing required params"),
            )
        if err := _unsupported_date_filter_error(params, "message_ids"):
            return err
        return await _handle_ids_mode(chat_id, message_ids, params)

    if mode is MessageRetrievalMode.REPLIES:
        if chat_id is None or reply_to_id is None:
            return log_and_build_error(
                operation="get_messages",
                error_message="chat_id and reply_to_id required for replies mode",
                params=params,
                exception=ValueError("Missing required params"),
            )
        return await _handle_reply_mode(
            chat_id,
            reply_to_id,
            limit,
            query,
            params,
            thread_scope,
            min_date=min_date,
            max_date=max_date,
        )

    result = await _handle_query_mode(
        query=query,
        chat_id=chat_id,
        limit=limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=chat_type,
        public=public,
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
        params=params,
        from_user=from_user,
    )

    # Apply context enrichment if requested and results available
    if (context > 0 or include_replies) and chat_id and "messages" in result:
        try:
            client = await get_connected_client()
            entity = await get_entity_by_id(chat_id)
            if entity:
                messages, ctx_warning = await _enrich_with_context(
                    client=client,
                    entity=entity,
                    messages=result["messages"],
                    context=context,
                    include_replies=include_replies,
                )
                result["messages"] = messages
                if ctx_warning:
                    existing = result.get("_warning", "")
                    result["_warning"] = f"{existing}\n{ctx_warning}".strip()
        except Exception as e:
            logger.warning(
                "Context enrichment failed, returning results without context: %s", e
            )

    return result


async def _handle_ids_mode(
    chat_id: str,
    message_ids: list[int],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle reading specific messages by IDs with unified output format."""
    messages_list = await read_messages_by_ids(chat_id, message_ids)

    if len(messages_list) == 1 and messages_list[0].get("ok") is False:
        return messages_list[0]

    result: dict[str, Any] = {
        "messages": messages_list,
        "has_more": False,
    }

    if warning := response_attachment_warning(messages_list):
        result["_warning"] = warning

    return result


async def search_messages_impl(
    query: str | None = None,
    chat_id: str | None = None,
    message_ids: list[int] | None = None,
    reply_to_id: int | None = None,
    limit: int = 20,
    min_date: str | None = None,
    max_date: str | None = None,
    chat_type: str | None = None,
    public: bool | None = None,
    auto_expand_batches: int = 1,
    include_total_count: bool = False,
    thread_scope: ThreadScope = "auto",
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
    from_user: str | None = None,
    context: int = 0,
    include_replies: bool = False,
) -> dict[str, Any]:
    """
    Unified message retrieval: search, browse, read by IDs, or list replies.

    Modes: per-chat search/browse (optional query); message_ids; reply_to_id;
    global search (non-empty query required). message_ids cannot combine with
    query or reply_to_id.

    Args:
        max_concurrent: Max parallel SearchGlobal requests (default: 2).
        from_user: Sender filter (per-chat only). Accepts user id, @username,
            phone, or 'me'. Uses Telegram's native from_id server-side filter.
    """
    params = _build_search_params(
        query=query,
        chat_id=chat_id,
        message_ids=message_ids,
        reply_to_id=reply_to_id,
        thread_scope=thread_scope,
        limit=limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=chat_type,
        public=public,
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
        max_concurrent=max_concurrent,
        from_user=from_user,
        context=context,
        include_replies=include_replies,
    )

    if thread_scope in ("full", "direct") and reply_to_id is None:
        return log_and_build_error(
            operation="get_messages",
            error_message="thread_scope requires reply_to_id",
            params=params,
            exception=ValueError("thread_scope requires reply_to_id"),
        )

    try:
        mode = resolve_mode(
            chat_id=chat_id,
            query=query,
            message_ids=message_ids,
            reply_to_id=reply_to_id,
        )
    except ValueError as e:
        return log_and_build_error(
            operation="get_messages",
            error_message=str(e),
            params=params,
            exception=e,
        )

    # Validate from_user early
    if from_user is not None:
        from_user = from_user.strip()
        if not from_user:
            return log_and_build_error(
                operation="get_messages",
                error_message="from_user must not be empty",
                params=params,
                exception=ValueError("from_user must not be empty"),
            )
        params["from_user"] = from_user  # update with stripped value

    if from_user and chat_id is None:
        return log_and_build_error(
            operation="get_messages",
            error_message="from_user requires chat_id; it only works with per-chat search",
            params=params,
            exception=ValueError("from_user requires chat_id"),
        )

    mode_names = {
        MessageRetrievalMode.MESSAGE_IDS: "message_ids",
        MessageRetrievalMode.REPLIES: "reply",
    }
    if from_user and mode in mode_names:
        mode_name = mode_names[mode]
        return log_and_build_error(
            operation="get_messages",
            error_message=f"from_user is not supported with {mode_name} mode; it only works with per-chat search (chat_id + query or chat_id alone)",
            params=params,
            exception=ValueError(f"from_user incompatible with {mode_name} mode"),
        )

    result = await _dispatch_search_mode(
        mode,
        params,
        query=query,
        chat_id=chat_id,
        message_ids=message_ids,
        reply_to_id=reply_to_id,
        limit=limit,
        min_date=min_date,
        max_date=max_date,
        chat_type=chat_type,
        public=public,
        auto_expand_batches=auto_expand_batches,
        include_total_count=include_total_count,
        thread_scope=thread_scope,
        from_user=from_user,
        context=context,
        include_replies=include_replies,
    )

    # Owner order 2026-10-01: every message list a tool returns is ordered by
    # ascending date-time. Applied AFTER the newest-N window was selected, so
    # membership and has_more are unaffected — only presentation order changes.
    return apply_ascending_message_order(result)
