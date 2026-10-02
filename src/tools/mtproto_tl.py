"""Telegram TL construction, entity resolution, and parameter sanitization."""

from __future__ import annotations

import base64
import contextlib
import datetime
import inspect
import logging
from importlib import import_module
from typing import Any

from src.client.connection import get_connected_client
from src.utils.entity import (
    get_entity_by_id,
    is_ambiguous_peer_scalar,
    parse_telegram_url,
)
from src.utils.json_ids import stringify_int64

logger = logging.getLogger(__name__)


def _construct_tl_object_from_dict(data: Any) -> Any:
    """
    Recursively construct Telethon TL objects from dictionaries.

    Handles dictionaries with '_' key containing the TL object type name.
    Supports case-insensitive type name lookup.
    Recursively processes nested dictionaries and lists.
    """
    if not isinstance(data, dict) or "_" not in data:
        return data

    requested_name = data["_"]
    # Import types dynamically to avoid circular imports
    from telethon.tl import types

    # Case-insensitive lookup: build mapping if not already built (module-level cache)
    _name_mapping: dict[str, str] = getattr(
        _construct_tl_object_from_dict,
        "_name_mapping",
        _construct_tl_object_from_dict.__dict__.setdefault("_name_mapping", {}),
    )
    if not _name_mapping:
        for name in dir(types):
            cls = getattr(types, name)
            # Only include TL object classes (they have CONSTRUCTOR_ID)
            if hasattr(cls, "CONSTRUCTOR_ID"):
                _name_mapping[name.lower()] = name

    # Try case-insensitive lookup first
    name_mapping = _name_mapping
    if requested_name.lower() in name_mapping:
        class_name = name_mapping[requested_name.lower()]
        logger.debug(f"Resolved TL type '{requested_name}' to '{class_name}'")
    else:
        class_name = requested_name

    if not hasattr(types, class_name):
        logger.warning(f"Unknown TL type: {requested_name} (resolved to: {class_name})")
        return data

    cls = getattr(types, class_name)
    if not hasattr(cls, "__init__"):
        return data

    try:
        # Get the constructor signature
        sig = inspect.signature(cls.__init__)
        params = {}

        for param_name in sig.parameters:
            if param_name == "self":
                continue
            if param_name in data:
                value = data[param_name]
                # Recursively construct nested objects
                if isinstance(value, dict) and "_" in value:
                    params[param_name] = _construct_tl_object_from_dict(value)
                elif isinstance(value, list):
                    params[param_name] = [
                        _construct_tl_object_from_dict(item) for item in value
                    ]
                else:
                    # Coerce numeric strings back to int only for int-annotated
                    # params.  After int64 stringification, access_hash and large
                    # ids arrive as strings; phone/first_name must stay str.
                    annotation = sig.parameters[param_name].annotation
                    if annotation is int and isinstance(value, str):
                        with contextlib.suppress(ValueError, TypeError):
                            value = int(value)
                    params[param_name] = value
            else:
                # Fill missing required int params with 0 so callers that
                # omit offset_id / offset_date / add_offset / hash etc.
                # don't crash the constructor.
                annotation = sig.parameters[param_name].annotation
                if annotation is int:
                    params[param_name] = 0

        return cls(**params)
    except Exception as e:
        logger.warning(f"Failed to construct TL object {class_name}: {e}")
        return data


def _json_safe(value: Any) -> Any:
    """Recursively convert value into a JSON- and UTF-8-safe structure.

    - bytes -> base64 ascii string
    - set/tuple -> list
    - objects with to_dict -> recurse into to_dict()
    - other non-serializable -> str(value)
    - ensure all strings are UTF-8 encodable (replace errors if needed)
    """
    try:
        if value is None or isinstance(value, bool | float):
            return value
        if isinstance(value, int):
            # 64-bit Telegram ids (document_id, access_hash, peer ids, ...) lose
            # precision when JSON-decoded as doubles; emit out-of-range ints as
            # strings. Small ints (offsets, flags, lengths) stay numeric.
            return stringify_int64(value)
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        if isinstance(value, datetime.datetime):
            # Datetime objects (e.g. Updates.date) must be int Unix timestamps,
            # not strings. MCP output schema validates date as integer.
            return int(value.timestamp())
        if isinstance(value, str):
            try:
                value.encode("utf-8", "strict")
                return value
            except Exception:
                return value.encode("utf-8", "replace").decode("utf-8")
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [_json_safe(v) for v in value]
        if hasattr(value, "to_dict") and callable(value.to_dict):
            try:
                return _json_safe(value.to_dict())
            except Exception:
                return str(value)
        return str(value)
    except Exception:
        return str(value)


def _construct_tl_params(params: dict[str, Any]) -> dict[str, Any]:
    """Construct Telethon TL objects from all nested dicts in *params*.

    Recursively converts dictionaries with ``_`` key
    (e.g. ``{"_": "inputChat", "chat_id": 123, "access_hash": "456"}``)
    into proper Telethon TL objects (``InputChat``).  Handles lists, nested
    dicts, and mixed structures.  Already-constructed TL objects pass through
    unchanged.

    This runs unconditionally (before the ``resolve`` check) so that TL dicts
    work even when entity resolution is disabled.
    """
    if not params:
        return {}

    def _process_value(value: Any) -> Any:
        if isinstance(value, dict):
            constructed = _construct_tl_object_from_dict(value)
            if constructed is not value:  # Construction succeeded
                return constructed
            return {k: _process_value(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [_process_value(item) for item in value]
        return value

    return {k: _process_value(v) for k, v in params.items()}


async def _resolve_params(params: dict[str, Any]) -> dict[str, Any]:
    """Best-effort resolution of entity-like parameters and TL object construction using Telethon.

    Handles entity resolution for: peer, from_peer, to_peer, user, user_id,
    channel, chat, chat_id, users, chats, peers.

    .. note::
       TL object construction (dict → Telethon type) is done by
       :func:`_construct_tl_params` which is called before this function
       in :func:`invoke_mtproto_impl`.  Direct callers should also run
       ``_construct_tl_params`` first.
    """
    if not params:
        return {}

    client = await get_connected_client()

    async def _resolve_one(value: Any) -> Any:
        # Pass-through for already-resolved TL objects
        with contextlib.suppress(Exception):
            # Telethon TL objects usually have to_dict
            if hasattr(value, "to_dict") or getattr(value, "_", None):
                return value
        # Parse Telegram URLs (https://t.me/…, tg://…) to peer identifiers
        # before falling through to get_input_entity, which cannot resolve URLs.
        if isinstance(value, str):
            parsed = parse_telegram_url(value)
            if parsed is not None:
                value = parsed
        if is_ambiguous_peer_scalar(value):
            entity = await get_entity_by_id(value, client=client)
            if entity is not None:
                return await client.get_input_entity(entity)
        return await client.get_input_entity(value)

    keys_to_resolve = {
        "peer",
        "from_peer",
        "to_peer",
        "user",
        "user_id",
        "channel",
        "chat",
        "chat_id",
        "users",
        "chats",
        "peers",
    }

    resolved: dict[str, Any] = dict(params)

    # TL object construction from nested dicts is done by _construct_tl_params()
    # before this function is called.  We run it again as a safety net for
    # callers that skip that step — it's a no-op on already-converted values.
    resolved = _construct_tl_params(resolved)

    # Resolve entity-like parameters
    for key in list(resolved.keys()):
        if key in keys_to_resolve:
            value = resolved[key]
            if isinstance(value, list | tuple):
                resolved[key] = [await _resolve_one(v) for v in value]
            else:
                resolved[key] = await _resolve_one(value)

    return resolved


async def _convert_peer_types(
    client,
    params: dict[str, Any],
    method_cls,
) -> dict[str, Any]:
    """Fix resolved peer types to match the method's expected parameter types.

    Two cases:

    1. **Method expects ``int``** but the value is a peer/input object
       (``InputPeerChat``, ``InputChat``, etc.) → extract the raw ID
       (``.chat_id``, ``.user_id``, ``.channel_id``).

       This happens when ``_resolve_params()`` converts an int (e.g.
       ``chat_id=5417489797``) to ``InputPeerChat``, but the method's
       signature (e.g. ``AddChatUserRequest.__init__(chat_id: int, ...)``)
       expects the raw integer, not an ``InputPeer*``.

    2. **Method expects ``Input*``** (string annotation like ``'InputChat'``
       or ``'TypeInputUser'``) but the value is ``InputPeer*`` → fetch the
       full entity from cache to construct ``Input*`` with the ``access_hash``.
    """
    # Import Telethon TL types — InputChat / InputChannel may not exist
    # in older Telethon builds, so we handle them conditionally.
    from telethon.tl.types import (
        InputPeerChannel,
        InputPeerChat,
        InputPeerUser,
    )

    input_chat_cls = None
    input_user_cls = None
    input_channel_cls = None
    try:
        from telethon.tl.types import InputChat

        input_chat_cls = InputChat
    except ImportError:
        pass  # not available in this Telethon version
    try:
        from telethon.tl.types import InputUser

        input_user_cls = InputUser
    except ImportError:
        pass
    try:
        from telethon.tl.types import InputChannel

        input_channel_cls = InputChannel
    except ImportError:
        pass

    # Types from which we can extract a raw peer/user/chat ID.
    # Key = class, value = attribute name holding the int ID.
    peer_types_with_id: dict[type, str] = {
        InputPeerChat: "chat_id",
        InputPeerUser: "user_id",
        InputPeerChannel: "channel_id",
    }
    # Add Input* types if they exist in this Telethon build
    if input_chat_cls is not None:
        peer_types_with_id[input_chat_cls] = "chat_id"
    if input_user_cls is not None:
        peer_types_with_id[input_user_cls] = "user_id"
    if input_channel_cls is not None:
        peer_types_with_id[input_channel_cls] = "channel_id"

    sig = inspect.signature(method_cls.__init__)
    result = dict(params)

    for name, param in sig.parameters.items():
        if name == "self" or name not in result:
            continue
        value = result[name]
        expected = param.annotation

        # --- Case 1: method expects int → extract raw ID from peer object ---
        if expected is int:
            value_cls = type(value)
            if value_cls in peer_types_with_id:
                id_field = peer_types_with_id[value_cls]
                result[name] = getattr(value, id_field)
                logger.debug(
                    "Extracted %s.%s = %s for parameter '%s' (method expects int)",
                    value_cls.__name__,
                    id_field,
                    result[name],
                    name,
                )
            continue

        # --- Case 2: method expects Input* (string annotation) but we have InputPeer* ---
        if not isinstance(expected, str):
            continue

        expected_name = expected
        # Strip 'Type' prefix from union annotations: TypeInputUser → InputUser
        if expected_name.startswith("Type"):
            expected_stripped = expected_name[4:]
        else:
            expected_stripped = expected_name

        # Map expected stripped name → (peer_cls, constructor for full entity).
        # Only include types that exist in this Telethon build.
        input_builders: dict[str, tuple] = {}
        if input_chat_cls is not None:
            input_builders["InputChat"] = (
                InputPeerChat,
                lambda e: input_chat_cls(chat_id=e.id, access_hash=e.access_hash),
            )
        if input_user_cls is not None:
            input_builders["InputUser"] = (
                InputPeerUser,
                lambda e: input_user_cls(user_id=e.id, access_hash=e.access_hash),
            )
        if input_channel_cls is not None:
            input_builders["InputChannel"] = (
                InputPeerChannel,
                lambda e: input_channel_cls(channel_id=e.id, access_hash=e.access_hash),
            )

        if expected_stripped not in input_builders:
            continue

        peer_cls, builder = input_builders[expected_stripped]
        if not isinstance(value, peer_cls):
            continue

        # Fetch the full entity to get the access_hash from cache
        try:
            entity = await client.get_entity(value)
            result[name] = builder(entity)
            logger.debug(
                "Converted %s → %s for parameter '%s'",
                peer_cls.__name__,
                expected_stripped,
                name,
            )
        except Exception as e:
            logger.warning(
                "Could not convert %s → %s for '%s': %s",
                peer_cls.__name__,
                expected_stripped,
                name,
                e,
            )

    return result


def _resolve_method_class(method_full_name: str):
    """Resolve MTProto method name to Telethon class.

    Args:
        method_full_name: Full class name of the MTProto method, e.g., 'messages.GetHistory'

    Returns:
        Tuple of (method_cls, normalized_name)

    Raises:
        ValueError: If method name format is invalid
        ImportError: If method class cannot be found
    """
    if "." not in method_full_name:
        raise ValueError(
            "method_full_name must be in the form 'module.ClassName', e.g., 'messages.GetHistory'"
        )

    module_name, class_name = method_full_name.rsplit(".", 1)

    # Telethon uses e.g. GetHistoryRequest, not GetHistory
    if not class_name.endswith("Request"):
        class_name += "Request"

    tl_module = import_module(f"telethon.tl.functions.{module_name}")
    method_cls = getattr(tl_module, class_name)

    return method_cls, method_full_name


# ============================================================================
# PARAMETER SANITIZATION
# ============================================================================


def _fill_missing_int_defaults(cls, params: dict[str, Any]) -> None:
    """Fill missing required int/nullable params with sensible defaults in-place.

    After the int64 stringification fix, callers may omit params like
    offset_id / add_offset / hash that Telegram expects.  Rather than a
    cryptic "missing N required" TypeError, fill int-typed params with 0
    and nullable-typed params with None.
    """
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return
    for name, param in sig.parameters.items():
        if name == "self" or name in params:
            continue
        if param.default is not inspect.Parameter.empty:
            continue  # has a default already
        if param.annotation is int:
            params[name] = 0
        else:
            # Check for Union types containing None (e.g. datetime | None)
            try:
                if type(None) in param.annotation.__args__:
                    params[name] = None
            except AttributeError:
                pass


def _sanitize_mtproto_params(params: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize and validate MTProto method parameters for security.

    Args:
        params: Raw parameters dictionary
    Returns:
        Sanitized parameters dictionary
    """
    sanitized = params.copy()

    # Security: Handle hash parameter correctly
    # 'hash' can be: (a) string invite hash for messages.ImportChatInvite, or
    # (b) integer for state/difference methods like messages.GetState
    if "hash" in sanitized:
        hash_value = sanitized["hash"]
        if isinstance(hash_value, str):
            if trimmed := hash_value.strip():
                sanitized["hash"] = trimmed
            else:
                del sanitized["hash"]
        elif isinstance(hash_value, int):
            if not 0 <= hash_value <= 0xFFFFFFFF:
                logger.warning(f"Hash out of bounds: {hash_value}, removing")
                del sanitized["hash"]
        else:
            logger.warning(f"Invalid hash type: {type(hash_value)}, removing")
            del sanitized["hash"]

    # Security: Validate other critical parameters
    for key, value in list(sanitized.items()):
        # Prevent injection of potentially dangerous parameters
        if key.startswith("_") or key in ["__class__", "__dict__", "__module__"]:
            logger.warning(f"Removing potentially dangerous parameter: {key}")
            del sanitized[key]
            continue

        # Validate string parameters for reasonable length
        if isinstance(value, str) and len(value) > 10000:
            logger.warning(
                f"String parameter {key} too long ({len(value)} chars), truncating"
            )
            sanitized[key] = value[:10000]

    return sanitized


# A request declaring one of these is bound to a chat: a message id inside it
# resolves against that named peer.
_PEER_BINDING_PARAMS = frozenset(
    {
        "peer",
        "channel",
        "channel_id",
        "chat",
        "chat_id",
        "user",
        "user_id",
        "from_peer",
        "to_peer",
        "peers",
        "users",
        "chats",
    }
)


def _declares_peer_binding(method_cls: Any) -> bool:
    """True when the request itself carries a chat binding."""
    annotations = getattr(method_cls.__init__, "__annotations__", None) or {}
    return bool(_PEER_BINDING_PARAMS & set(annotations))


def _unbound_message_id_params(method_cls: Any, params: dict[str, Any]) -> list[str]:
    """Names of params carrying a bare message id on a request with no chat binding.

    A message id is not a coordinate. ``messages.GetMessagesRequest`` has no
    peer field at all -- its only param is ``id`` -- so the server resolves a
    bare ``InputMessageID`` against whatever dialog the account can see. A read
    of id 78605 returned an unrelated 2017 megagroup's message body.

    Telethon's own resolve step (``utils.get_input_message``) converts a plain
    int into ``InputMessageID``, so an int is the same hazard in a different
    spelling. It is caught here, before the request reaches the wire: a guard
    matching only the explicit dict form would be bypassed by writing
    ``{"id": [78605]}`` instead.
    """
    if _declares_peer_binding(method_cls):
        return []

    from telethon.tl.types import InputMessageID

    annotations = getattr(method_cls.__init__, "__annotations__", None) or {}

    def _is_bare_message_id(value: Any) -> bool:
        if isinstance(value, InputMessageID):
            return True
        if isinstance(value, bool):
            return False  # bool subclasses int, but is never a message id
        if isinstance(value, int):
            return True
        if isinstance(value, dict):
            return str(value.get("_", "")).lower() == "inputmessageid"
        return False

    offenders: list[str] = []
    for name, annotation in annotations.items():
        if "InputMessage" not in str(annotation):
            continue
        value = params.get(name)
        if value is None:
            continue
        candidates = value if isinstance(value, list | tuple) else [value]
        if any(_is_bare_message_id(v) for v in candidates):
            offenders.append(name)
    return offenders
