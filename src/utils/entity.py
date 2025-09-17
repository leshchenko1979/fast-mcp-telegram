from loguru import logger
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest, GetSearchCountersRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputMessagesFilterEmpty

from ..client.connection import get_connected_client


async def get_entity_by_id(entity_id):
    """
    A wrapper around client.get_entity to handle numeric strings and log errors.
    Special handling for 'me' identifier for Saved Messages.
    """
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

        return await client.get_entity(peer)
    except Exception as e:
        logger.warning(
            f"Could not get entity for '{entity_id}' (parsed as '{peer}'). Error: {e}"
        )
        return None


def get_normalized_chat_type(entity) -> str | None:
    """Return normalized chat type: 'private', 'group', or 'channel'."""
    if not entity:
        return None
    try:
        entity_class = entity.__class__.__name__
    except Exception:
        return None

    if entity_class == "User":
        return "private"
    if entity_class == "Chat":
        return "group"
    if entity_class in ["Channel", "ChannelForbidden"]:
        is_megagroup = bool(getattr(entity, "megagroup", False))
        is_broadcast = bool(getattr(entity, "broadcast", False))
        if is_megagroup:
            return "group"
        if is_broadcast:
            return "channel"
        return "channel"
    return None


def build_entity_dict(entity) -> dict:
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

    first_name = getattr(entity, "first_name", None)
    last_name = getattr(entity, "last_name", None)
    username = getattr(entity, "username", None)

    # Derive a robust title: explicit title → full name → @username
    raw_title = getattr(entity, "title", None)
    full_name = f"{first_name or ''} {last_name or ''}".strip()
    title = raw_title or (
        full_name if full_name else (f"@{username}" if username else None)
    )

    normalized_type = get_normalized_chat_type(entity)
    computed_type = (
        normalized_type
        if normalized_type
        else (entity.__class__.__name__ if hasattr(entity, "__class__") else None)
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
    }

    # Prune None values for a compact, uniform schema
    return {k: v for k, v in result.items() if v is not None}


async def _extract_forward_info(message) -> dict:
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

    # Extract forward date and convert to ISO format if present
    forward_date = getattr(forward, "date", None)
    original_date = None
    if forward_date:
        try:
            original_date = forward_date.isoformat()
        except Exception:
            original_date = str(forward_date)

    # Extract original sender information with full entity resolution
    sender = None
    from_id = getattr(forward, "from_id", None)
    if from_id:
        # Extract user ID from PeerUser or other peer types
        sender_id = None
        if hasattr(from_id, "user_id"):
            sender_id = from_id.user_id
        elif hasattr(from_id, "channel_id"):
            sender_id = from_id.channel_id
        elif hasattr(from_id, "chat_id"):
            sender_id = from_id.chat_id
        else:
            sender_id = str(from_id)

        # Try to resolve the full entity information
        if sender_id:
            try:
                sender_entity = await get_entity_by_id(sender_id)
                if sender_entity:
                    sender = build_entity_dict(sender_entity)
                else:
                    # Fallback to basic info if entity resolution fails
                    sender = {
                        "id": sender_id,
                        "title": None,
                        "type": "User"
                        if hasattr(from_id, "user_id")
                        else "Channel"
                        if hasattr(from_id, "channel_id")
                        else "Chat"
                        if hasattr(from_id, "chat_id")
                        else "Unknown",
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }
            except Exception as e:
                logger.warning(
                    f"Failed to resolve forwarded sender entity {sender_id}: {e}"
                )
                # Fallback to basic info
                sender = {
                    "id": sender_id,
                    "title": None,
                    "type": "User"
                    if hasattr(from_id, "user_id")
                    else "Channel"
                    if hasattr(from_id, "channel_id")
                    else "Chat"
                    if hasattr(from_id, "chat_id")
                    else "Unknown",
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                }

    # Extract source chat information with full entity resolution
    chat = None
    saved_from_peer = getattr(forward, "saved_from_peer", None)
    if saved_from_peer:
        # Extract chat ID from peer types
        chat_id = None
        if hasattr(saved_from_peer, "user_id"):
            chat_id = saved_from_peer.user_id
        elif hasattr(saved_from_peer, "channel_id"):
            chat_id = saved_from_peer.channel_id
        elif hasattr(saved_from_peer, "chat_id"):
            chat_id = saved_from_peer.chat_id
        else:
            chat_id = str(saved_from_peer)

        # Try to resolve the full entity information
        if chat_id:
            try:
                chat_entity = await get_entity_by_id(chat_id)
                if chat_entity:
                    chat = build_entity_dict(chat_entity)
                else:
                    # Fallback to basic info if entity resolution fails
                    chat = {
                        "id": chat_id,
                        "title": None,
                        "type": "User"
                        if hasattr(saved_from_peer, "user_id")
                        else "Channel"
                        if hasattr(saved_from_peer, "channel_id")
                        else "Chat"
                        if hasattr(saved_from_peer, "chat_id")
                        else "Unknown",
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }
            except Exception as e:
                logger.warning(
                    f"Failed to resolve forwarded chat entity {chat_id}: {e}"
                )
                # Fallback to basic info
                chat = {
                    "id": chat_id,
                    "title": None,
                    "type": "User"
                    if hasattr(saved_from_peer, "user_id")
                    else "Channel"
                    if hasattr(saved_from_peer, "channel_id")
                    else "Chat"
                    if hasattr(saved_from_peer, "chat_id")
                    else "Unknown",
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                }

    return {"sender": sender, "date": original_date, "chat": chat}


def compute_entity_identifier(entity) -> str:
    """
    Compute a stable identifier string for a chat/entity suitable for link generation.
    Prefers public username; falls back to channel/chat numeric id with '-100' prefix when required.
    """
    if entity is None:
        return None
    username = getattr(entity, "username", None)
    if username:
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
    """Check if entity matches the specified chat type filter."""
    if not chat_type:
        return True
    normalized_type = get_normalized_chat_type(entity)
    return normalized_type == chat_type


async def build_entity_dict_enriched(entity_or_id) -> dict:
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
        # Resolve if an id/username was provided
        entity = entity_or_id
        if not getattr(entity_or_id, "__class__", None):
            entity = await get_entity_by_id(entity_or_id)

        base = build_entity_dict(entity)
        if not base:
            return None

        computed_type = base.get("type")
        members_count: int | None = None
        subscribers_count: int | None = None
        about_value: str | None = None
        bio_value: str | None = None

        client = await get_connected_client()

        # Distinguish Chat vs Channel classes to pick proper request
        entity_class = entity.__class__.__name__ if hasattr(entity, "__class__") else ""

        if computed_type == "group":
            # Regular small groups use GetFullChatRequest with chat_id
            if entity_class == "Chat":
                try:
                    full = await client(
                        GetFullChatRequest(chat_id=getattr(entity, "id", None))
                    )
                    full_chat = getattr(full, "full_chat", None)
                    members_count = getattr(full_chat, "participants_count", None)
                    about_value = getattr(full_chat, "about", None)
                except Exception as e:
                    logger.debug(
                        f"GetFullChatRequest failed for chat {getattr(entity, 'id', None)}: {e}"
                    )
            else:
                # Megagroups are Channels with megagroup=True; use GetFullChannelRequest
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
            # Broadcast channels via GetFullChannelRequest
            try:
                full = await client(GetFullChannelRequest(channel=entity))
                full_chat = getattr(full, "full_chat", None)
                subscribers_count = getattr(full_chat, "participants_count", None)
                about_value = getattr(full_chat, "about", None)
            except Exception as e:
                logger.debug(
                    f"GetFullChannelRequest (channel) failed for {getattr(entity, 'id', None)}: {e}"
                )

        elif computed_type == "private":
            # Users: get bio via GetFullUserRequest
            try:
                full_user = await client(GetFullUserRequest(id=entity))
                bio_value = getattr(full_user, "about", None)
            except Exception as e:
                logger.debug(
                    f"GetFullUserRequest failed for user {getattr(entity, 'id', None)}: {e}"
                )

        # Merge counts into the base dict, pruning None
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
        # Fallback to simple version without counts
        try:
            entity = entity_or_id
            if not getattr(entity_or_id, "__class__", None):
                entity = await get_entity_by_id(entity_or_id)
            return build_entity_dict(entity)
        except Exception:
            return None
