import asyncio
import contextlib
import logging
import time
from typing import Any

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest, GetSearchCountersRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.tlobject import TLObject
from telethon.tl.types import InputMessagesFilterEmpty, PeerChannel, PeerChat, PeerUser

from ..client.connection import get_connected_client

logger = logging.getLogger(__name__)

# -------------------------
# Manual caches (key-safe)
# -------------------------

# Cache normalized chat type per entity key
_ENTITY_TYPE_CACHE: dict[tuple, str | None] = {}

# Cache built entity dict per entity key
_ENTITY_DICT_CACHE: dict[tuple, dict | None] = {}

# -------------------------
# Folder list cache
# -------------------------

# Cache for folder list: key is session_id or id(session), value is (folders_list, timestamp)
_FOLDER_LIST_CACHE: dict[str | int, tuple[list[dict], float]] = {}
_FOLDER_CACHE_TTL_SECONDS = 300  # 5 minutes


def _extract_filter_flags(filter_obj) -> dict:
    """Extract boolean flags from DialogFilter/DialogFilterChatlist into flat dict."""
    return {
        "id": getattr(filter_obj, "id", None),
        "title": getattr(filter_obj, "title", None),
        "contacts": getattr(filter_obj, "contacts", False),
        "non_contacts": getattr(filter_obj, "non_contacts", False),
        "groups": getattr(filter_obj, "groups", False),
        "broadcasts": getattr(filter_obj, "broadcasts", False),
        "bots": getattr(filter_obj, "bots", False),
        "exclude_muted": getattr(filter_obj, "exclude_muted", False),
        "exclude_read": getattr(filter_obj, "exclude_read", False),
        "exclude_archived": getattr(filter_obj, "exclude_archived", False),
        "include_peers": getattr(filter_obj, "include_peers", []),
        "exclude_peers": getattr(filter_obj, "exclude_peers", []),
    }


async def get_dialog_filters(client) -> list[dict]:
    """Fetch user's dialog filters from Telegram with 5-minute caching.

    Uses client(functions.messages.GetDialogFiltersRequest()) via Telethon.

    Returns list of flat dicts with filter metadata and flags:
    - id, title, contacts, non_contacts, groups, broadcasts, bots,
      exclude_muted, exclude_read, exclude_archived, include_peers, exclude_peers

    Note: Folder title is a TextWithEntities object - extract .text
    """
    global _FOLDER_LIST_CACHE

    # Prefer stable session_id, fall back to object id for cache key
    try:
        cache_key = client.session.session_id
    except AttributeError:
        cache_key = id(client.session)

    # Check cache
    if cache_key in _FOLDER_LIST_CACHE:
        filters, timestamp = _FOLDER_LIST_CACHE[cache_key]
        if time.time() - timestamp < _FOLDER_CACHE_TTL_SECONDS:
            return filters

    # Fetch from Telegram
    filters = []
    try:
        from telethon import functions

        result = await client(functions.messages.GetDialogFiltersRequest())
        for f in result.filters:
            # title is TextWithEntities object - extract .text
            title_obj = getattr(f, "title", None)
            title_text = getattr(title_obj, "text", None) if title_obj else None
            filter_dict = _extract_filter_flags(f)
            filter_dict["title"] = title_text
            filters.append(filter_dict)
    except asyncio.CancelledError:
        # Let cancellation propagate so shutdown/timeout behavior works correctly
        raise
    except Exception as e:
        logger.debug(f"GetDialogFiltersRequest failed: {e}")
        # Don't cache empty result on failure - allows retry instead of long-lived empty cache
        return filters

    # Update cache only on success
    _FOLDER_LIST_CACHE[cache_key] = (filters, time.time())
    return filters


async def get_available_folders(client) -> list[dict]:
    """Deprecated alias for get_dialog_filters."""
    return await get_dialog_filters(client)


def _entity_cache_key(entity) -> tuple:
    """Build a hashable cache key for an entity.

    Uses a stable tuple based on class name, id and username when available,
    avoiding passing Telethon objects directly as dict keys.
    """
    try:
        entity_class = entity.__class__.__name__ if hasattr(entity, "__class__") else ""
        entity_id = getattr(entity, "id", None)
        username = getattr(entity, "username", None)
        return (entity_class, entity_id, username)
    except Exception:
        # Fallback to object identity to avoid unhashable errors
        return ("object", id(entity))


def is_ambiguous_peer_scalar(value: Any) -> bool:
    """True if `value` is a bare numeric id where get_input_entity may pick the wrong peer type.

    Excludes bool (subclasses int). Usernames and non-numeric strings are not ambiguous.
    """
    if type(value) is int:
        return True
    if not isinstance(value, str):
        return False
    s = value.strip()
    if s in ("me", "self"):
        return False
    if s.isdigit():
        return True
    return bool(s.startswith("-") and len(s) > 1 and s[1:].isdigit())


async def get_entity_by_id(entity_id, *, client: TelegramClient | None = None):
    """
    A wrapper around client.get_entity to handle numeric strings and log errors.
    Special handling for 'me' identifier for Saved Messages.
    Tries multiple peer types (raw ID, PeerChannel, PeerUser, PeerChat) for better resolution.

    Args:
        entity_id: Username, ``me``, numeric id, or numeric string.
        client: Optional Telethon client; if omitted, ``get_connected_client()`` is used.
    """
    if client is None:
        client = await get_connected_client()
    peer = None
    try:
        # Special handling for 'me' identifier (Saved Messages)
        if entity_id == "me":
            return await client.get_me()

        # Try to convert entity_id to an integer if it's a numeric string
        try:
            peer = int(entity_id)
        except (ValueError, TypeError):
            peer = entity_id

        if not peer:
            raise ValueError("Entity ID cannot be null or empty")

        candidates: list = [peer]
        if isinstance(peer, int):
            candidates.extend([PeerChannel(peer), PeerUser(peer), PeerChat(peer)])

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                return await client.get_entity(candidate)
            except Exception as err:
                last_error = err
                logger.debug("get_entity failed for %r: %s", candidate, last_error)
        if last_error:
            raise last_error

    except Exception as e:
        logger.warning(
            f"Could not get entity for '{entity_id}' (parsed as '{peer}') after trying all peer types. Error: {e}"
        )
        return None


def _cache_channel_normalized_type(entity, cache_key: tuple) -> str:
    """Map Channel / ChannelForbidden to 'group' (megagroup) or 'channel'."""
    resolved = "group" if bool(getattr(entity, "megagroup", False)) else "channel"
    _ENTITY_TYPE_CACHE[cache_key] = resolved
    return resolved


def get_normalized_chat_type(entity) -> str | None:
    """Return normalized chat type: 'private', 'bot', 'group', or 'channel'."""
    if not entity:
        return None
    # Check manual cache first
    key = _entity_cache_key(entity)
    if key in _ENTITY_TYPE_CACHE:
        return _ENTITY_TYPE_CACHE[key]
    try:
        entity_class = entity.__class__.__name__
    except Exception:
        _ENTITY_TYPE_CACHE[key] = None
        return _ENTITY_TYPE_CACHE[key]

    if entity_class == "User":
        # Check if this user is a bot (bot field is boolean true/false)
        with contextlib.suppress(AttributeError):
            if getattr(entity, "bot", False):
                _ENTITY_TYPE_CACHE[key] = "bot"
                return _ENTITY_TYPE_CACHE[key]
        _ENTITY_TYPE_CACHE[key] = "private"
        return _ENTITY_TYPE_CACHE[key]
    if entity_class == "Chat":
        _ENTITY_TYPE_CACHE[key] = "group"
        return _ENTITY_TYPE_CACHE[key]
    if entity_class in ["Channel", "ChannelForbidden"]:
        return _cache_channel_normalized_type(entity, key)
    _ENTITY_TYPE_CACHE[key] = None
    return _ENTITY_TYPE_CACHE[key]


def build_entity_dict(entity) -> dict | None:
    """
    Build a uniform chat/user representation used across all tools.

    Fields:
    - id: numeric or string identifier
    - title: preferred display label; falls back to full name or @username
    - type: one of "private", "group", "channel" (when determinable)
    - username: public username if available
    - first_name, last_name: present for users when available
    """
    if not entity:
        return None

    # Check manual cache first
    key = _entity_cache_key(entity)
    if key in _ENTITY_DICT_CACHE:
        return _ENTITY_DICT_CACHE[key]

    first_name = getattr(entity, "first_name", None)
    last_name = getattr(entity, "last_name", None)
    username = getattr(entity, "username", None)

    # Derive a robust title: explicit title → full name → @username
    raw_title = getattr(entity, "title", None)
    full_name = f"{first_name or ''} {last_name or ''}".strip()
    title = raw_title or (full_name or (f"@{username}" if username else None))

    normalized_type = get_normalized_chat_type(entity)
    computed_type = normalized_type or (
        entity.__class__.__name__ if hasattr(entity, "__class__") else None
    )

    # Opportunistic counts: available only on certain entity variants
    members_count = None
    subscribers_count = None
    try:
        if computed_type == "group":
            # Some group entities expose participants_count directly
            members_count = getattr(entity, "participants_count", None)
        elif computed_type == "channel":
            # Channels may expose subscribers_count or participants_count depending on context
            subscribers_count = getattr(entity, "subscribers_count", None) or getattr(
                entity, "participants_count", None
            )
    except Exception:
        members_count = None
        subscribers_count = None

    is_forum = bool(getattr(entity, "forum", False))

    result = {
        "id": getattr(entity, "id", None),
        "title": title,
        "type": computed_type,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        # Counts (only when available on the given entity instance)
        "members_count": members_count,
        "subscribers_count": subscribers_count,
        # Present only for forum-enabled channels/supergroups
        "is_forum": True if is_forum else None,
    }

    # Prune None values for a compact, uniform schema
    compact = {k: v for k, v in result.items() if v is not None}
    _ENTITY_DICT_CACHE[key] = compact
    return compact


def _forward_peer_id_and_type_label(peer) -> tuple[object | None, str]:
    """Return a stable id and Telethon-style type label for TL Peer-like objects."""
    if peer is None:
        return None, "Unknown"
    if hasattr(peer, "user_id"):
        return peer.user_id, "User"
    if hasattr(peer, "channel_id"):
        return peer.channel_id, "Channel"
    if hasattr(peer, "chat_id"):
        return peer.chat_id, "Chat"
    return str(peer), "Unknown"


def _forward_stub_entity_dict(entity_id: object, type_label: str) -> dict:
    """Minimal entity-shaped dict when full resolution is unavailable."""
    return {
        "id": entity_id,
        "title": None,
        "type": type_label,
        "username": None,
        "first_name": None,
        "last_name": None,
    }


async def _extract_forward_info(message) -> dict | None:
    """
    Extract forward information from a Telegram message in minimal format.

    Args:
        message: Telegram message object

    Returns:
        dict: Forward information dictionary containing:
            - sender: Original sender information (if available)
            - date: Original message date in ISO format
            - chat: Source chat information (if available)
        None: If the message is not forwarded
    """
    if not message:
        return None

    forward = getattr(message, "forward", None)
    if not forward:
        return None

    original_date = None
    if forward_date := getattr(forward, "date", None):
        try:
            original_date = forward_date.isoformat()
        except Exception:
            original_date = str(forward_date)

    sender = None
    if from_id := getattr(forward, "from_id", None):
        sender_id, type_label = _forward_peer_id_and_type_label(from_id)
        if sender_id:
            try:
                sender_entity = await get_entity_by_id(sender_id)
                sender = (
                    build_entity_dict(sender_entity)
                    if sender_entity
                    else _forward_stub_entity_dict(sender_id, type_label)
                )
            except Exception as e:
                logger.warning(
                    f"Failed to resolve forwarded sender entity {sender_id}: {e}"
                )
                sender = _forward_stub_entity_dict(sender_id, type_label)

    chat = None
    if saved_from_peer := getattr(forward, "saved_from_peer", None):
        chat_id, type_label = _forward_peer_id_and_type_label(saved_from_peer)
        if chat_id:
            try:
                chat_entity = await get_entity_by_id(chat_id)
                chat = (
                    build_entity_dict(chat_entity)
                    if chat_entity
                    else _forward_stub_entity_dict(chat_id, type_label)
                )
            except Exception as e:
                logger.warning(
                    f"Failed to resolve forwarded chat entity {chat_id}: {e}"
                )
                chat = _forward_stub_entity_dict(chat_id, type_label)

    return {"sender": sender, "date": original_date, "chat": chat}


def compute_entity_identifier(entity) -> str | None:
    """
    Compute a stable identifier string for a chat/entity suitable for link generation.
    Prefers public username; falls back to channel/chat numeric id with '-100' prefix when required.
    """
    if entity is None:
        return None
    if username := getattr(entity, "username", None):
        return username
    entity_id = getattr(entity, "id", None)
    if entity_id is None:
        return None
    entity_type = entity.__class__.__name__ if hasattr(entity, "__class__") else ""
    entity_id_str = str(entity_id)
    if entity_id_str.startswith("-100"):
        return entity_id_str
    if entity_type in ["Channel", "Chat", "ChannelForbidden"]:
        return f"-100{entity_id}"
    return entity_id_str


async def _get_chat_message_count(chat_id: str) -> int | None:
    """
    Get total message count for a specific chat.
    """
    try:
        client = await get_connected_client()
        entity = await get_entity_by_id(chat_id)
        if not entity:
            return None

        result = await client(
            GetSearchCountersRequest(peer=entity, filters=[InputMessagesFilterEmpty()])
        )

        if hasattr(result, "counters") and result.counters:
            for counter in result.counters:
                if hasattr(counter, "filter") and isinstance(
                    counter.filter, InputMessagesFilterEmpty
                ):
                    return getattr(counter, "count", 0)

        return 0

    except Exception as e:
        logger.warning(f"Error getting search count for chat {chat_id}: {e!s}")
        return None


def _matches_chat_type(entity, chat_type: str) -> bool:
    """Check if entity matches the specified chat type filter.

    Supports comma-separated values (e.g., "private,group").
    Whitespace is trimmed, case-insensitive, empty values are ignored.
    """
    if not chat_type:
        return True

    # Split by comma, strip whitespace, filter out empty strings, convert to lowercase
    chat_types = [ct.strip().lower() for ct in chat_type.split(",") if ct.strip()]

    # Validate that all specified types are valid
    valid_types = {"private", "bot", "group", "channel"}
    if any(ct not in valid_types for ct in chat_types):
        return False

    normalized_type = get_normalized_chat_type(entity)
    return normalized_type in chat_types


def _matches_public_filter(entity, public: bool | None) -> bool:
    """Check if entity matches the specified public filter.

    Private chats (User entities) are never filtered by the public parameter.

    Args:
        entity: Telegram entity (User, Chat, Channel)
        public: True for entities with usernames (publicly discoverable),
               False for entities without usernames (invite-only),
               None for no filtering

    Returns:
        True if entity matches public filter, False otherwise
    """
    # Private chats and bots (User entities) are never filtered by public parameter
    if get_normalized_chat_type(entity) in ("private", "bot"):
        return True

    if public is None:
        return True

    has_username = bool(getattr(entity, "username", None))

    return has_username if public else not has_username


async def _fetch_enrichment_fields(
    client,
    entity,
    computed_type: str | None,
    entity_class: str,
) -> tuple[int | None, int | None, str | None, str | None]:
    """Load optional counts, about, and bio via Telethon full-info requests."""
    members_count: int | None = None
    subscribers_count: int | None = None
    about_value: str | None = None
    bio_value: str | None = None

    if computed_type == "group":
        if entity_class == "Chat":
            chat_id = getattr(entity, "id", None)
            if chat_id is not None:
                try:
                    full = await client(GetFullChatRequest(chat_id=chat_id))
                    full_chat = getattr(full, "full_chat", None)
                    members_count = getattr(full_chat, "participants_count", None)
                    about_value = getattr(full_chat, "about", None)
                except Exception as e:
                    logger.debug(
                        f"GetFullChatRequest failed for chat {getattr(entity, 'id', None)}: {e}"
                    )
        else:
            try:
                full = await client(GetFullChannelRequest(channel=entity))
                full_chat = getattr(full, "full_chat", None)
                members_count = getattr(full_chat, "participants_count", None)
                about_value = getattr(full_chat, "about", None)
            except Exception as e:
                logger.debug(
                    f"GetFullChannelRequest (megagroup) failed for {getattr(entity, 'id', None)}: {e}"
                )

    elif computed_type == "channel":
        try:
            full = await client(GetFullChannelRequest(channel=entity))
            full_chat = getattr(full, "full_chat", None)
            subscribers_count = getattr(full_chat, "participants_count", None)
            about_value = getattr(full_chat, "about", None)
        except Exception as e:
            logger.debug(
                f"GetFullChannelRequest (channel) failed for {getattr(entity, 'id', None)}: {e}"
            )

    elif computed_type in ("private", "bot"):
        try:
            full_user = await client(GetFullUserRequest(id=entity))
            bio_value = getattr(full_user, "about", None)
        except Exception as e:
            logger.debug(
                f"GetFullUserRequest failed for user {getattr(entity, 'id', None)}: {e}"
            )

    return members_count, subscribers_count, about_value, bio_value


async def build_entity_dict_enriched(entity_or_id) -> dict | None:
    """
    Build entity dict and include enriched fields by querying Telegram when needed.

    Adds when applicable:
    - groups: members_count, about/description
    - channels: subscribers_count, about/description
    - private users: bio

    This is the async variant that can fetch full chat/channel info via Telethon:
    - messages.GetFullChatRequest for basic groups (`Chat`)
    - channels.GetFullChannelRequest for channels/megagroups (`Channel`)
    - users.GetFullUserRequest for private users
    """
    try:
        entity = (
            entity_or_id
            if isinstance(entity_or_id, TLObject)
            else await get_entity_by_id(entity_or_id)
        )

        base = build_entity_dict(entity)
        if not base:
            return None

        computed_type = base.get("type")
        client = await get_connected_client()
        entity_class = entity.__class__.__name__ if hasattr(entity, "__class__") else ""

        (
            members_count,
            subscribers_count,
            about_value,
            bio_value,
        ) = await _fetch_enrichment_fields(client, entity, computed_type, entity_class)

        if members_count is not None:
            base["members_count"] = members_count
        if subscribers_count is not None:
            base["subscribers_count"] = subscribers_count
        if about_value is not None:
            base["about"] = about_value
        if bio_value is not None:
            base["bio"] = bio_value
        return base
    except Exception as e:
        logger.warning(f"Failed to build entity dict with counts: {e}")
        try:
            entity = (
                entity_or_id
                if isinstance(entity_or_id, TLObject)
                else await get_entity_by_id(entity_or_id)
            )
            return build_entity_dict(entity)
        except Exception:
            return None


def build_dialog_entity_dict(dialog, entity) -> dict | None:
    """
    Build an entity dict from a Dialog object, including last_activity_date.

    Dialog objects from iter_dialogs() have a .date attribute representing
    the last activity date, which is not available on regular entity objects.

    Args:
        dialog: Telethon Dialog object with .date attribute
        entity: Telethon entity object (User, Chat, or Channel)

    Returns:
        Entity dict with last_activity_date field added, or None if entity is None
    """
    base = build_entity_dict(entity)
    if not base:
        return None

    last_activity_date = None
    if dialog_date := getattr(dialog, "date", None):
        with contextlib.suppress(Exception):
            last_activity_date = dialog_date.isoformat()

    base["last_activity_date"] = last_activity_date
    return base
