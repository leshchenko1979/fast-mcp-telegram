import base64
import inspect
import json
import logging
from importlib import import_module
from typing import Any

from src.client.connection import SessionNotAuthorizedError, get_connected_client
from src.utils.error_handling import log_and_build_error
from src.utils.helpers import normalize_method_name

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Dangerous methods that require explicit permission
DANGEROUS_METHODS = {
    "account.DeleteAccount",
    "messages.DeleteHistory",
    "messages.DeleteUserHistory",
    "messages.DeleteChatUser",
    "messages.DeleteMessages",
    "channels.DeleteHistory",
    "channels.DeleteMessages",
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


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

    # Case-insensitive lookup: build mapping if not already built
    if not hasattr(_construct_tl_object_from_dict, "_name_mapping"):
        _construct_tl_object_from_dict._name_mapping = {}
        for name in dir(types):
            cls = getattr(types, name)
            # Only include TL object classes (they have CONSTRUCTOR_ID)
            if hasattr(cls, "CONSTRUCTOR_ID"):
                _construct_tl_object_from_dict._name_mapping[name.lower()] = name

    # Try case-insensitive lookup first
    name_mapping = _construct_tl_object_from_dict._name_mapping
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
                    params[param_name] = value

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
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
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


async def _resolve_params(params: dict[str, Any]) -> dict[str, Any]:
    """Best-effort resolution of entity-like parameters and TL object construction using Telethon.

    Handles entity resolution for: peer, from_peer, to_peer, user, user_id,
    channel, chat, chat_id, users, chats, peers.

    Also handles automatic TL object construction from dictionaries with '_' key.
    """
    if not params:
        return {}

    client = await get_connected_client()

    def _is_list_like(value: Any) -> bool:
        return isinstance(value, list | tuple)

    async def _resolve_one(value: Any) -> Any:
        # Pass-through for already-resolved TL objects
        try:
            # Telethon TL objects usually have to_dict
            if hasattr(value, "to_dict") or getattr(value, "_", None):
                return value
        except Exception:
            pass
        # Resolve using input entity for strings/ints
        return await client.get_input_entity(value)

    def _process_value(value: Any) -> Any:
        """Recursively process values for TL object construction and entity resolution."""
        if isinstance(value, dict):
            # First try to construct TL objects from dict
            constructed = _construct_tl_object_from_dict(value)
            if constructed is not value:  # Construction succeeded
                return constructed
            # If construction failed, process nested dict values
            return {k: _process_value(v) for k, v in value.items()}
        if _is_list_like(value):
            return [_process_value(item) for item in value]
        return value

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

    # First pass: construct TL objects from dictionaries
    for key in list(resolved.keys()):
        resolved[key] = _process_value(resolved[key])

    # Second pass: resolve entity-like parameters
    for key in list(resolved.keys()):
        if key in keys_to_resolve:
            value = resolved[key]
            if _is_list_like(value):
                resolved[key] = [await _resolve_one(v) for v in value]
            else:
                resolved[key] = await _resolve_one(value)

    return resolved


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
    # According to Telethon docs, 'hash' is a Telegram-specific identifier for data differences
    # It's not a cryptographic hash and can often be safely set to 0
    if "hash" in sanitized:
        hash_value = sanitized["hash"]

        # Validate hash is a valid integer
        if not isinstance(hash_value, int | str):
            logger.warning(f"Invalid hash type: {type(hash_value)}, setting to 0")
            sanitized["hash"] = 0
        else:
            try:
                # Convert to int if it's a string
                if isinstance(hash_value, str):
                    sanitized["hash"] = int(hash_value)
                # Ensure it's within reasonable bounds (32-bit unsigned int)
                elif not (0 <= hash_value <= 0xFFFFFFFF):
                    logger.warning(
                        f"Hash value out of bounds: {hash_value}, setting to 0"
                    )
                    sanitized["hash"] = 0
            except (ValueError, OverflowError):
                logger.warning(f"Invalid hash value: {hash_value}, setting to 0")
                sanitized["hash"] = 0

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


# ============================================================================
# HIGH-LEVEL API FUNCTIONS
# ============================================================================


async def invoke_mtproto_impl(
    method_full_name: str,
    params_json: str,
    allow_dangerous: bool = False,
    resolve: bool = True,
) -> dict[str, Any]:
    """
    Invoke MTProto methods with enhanced features.

    This function provides comprehensive MTProto method invocation with:
    - Method name normalization
    - Dangerous method protection
    - Entity resolution
    - Parameter sanitization
    - Telethon client interaction
    - Result processing

    Args:
        method_full_name: Telegram API method name (e.g., "messages.GetHistory")
        params_json: Method parameters as JSON string
        allow_dangerous: Allow dangerous methods like delete operations (default: False)
        resolve: Automatically resolve entity-like parameters (default: True)

    Returns:
        API response as dict, or error details if failed
    """
    try:
        # Normalize method name for consistency
        try:
            normalized_method = normalize_method_name(method_full_name)
        except Exception as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Invalid method name format: {e}",
                params={
                    "method_full_name": method_full_name,
                    "params_json": params_json,
                },
                exception=e,
            )

        # Check for dangerous methods unless explicitly allowed
        if normalized_method in DANGEROUS_METHODS and not allow_dangerous:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=(
                    f"Method '{normalized_method}' is blocked by default. "
                    "Pass allow_dangerous=true to override."
                ),
                params={
                    "method_full_name": method_full_name,
                    "normalized_method": normalized_method,
                    "params_json": params_json,
                },
            )

        # Parse parameters
        try:
            params = json.loads(params_json)
        except Exception as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Invalid JSON in params_json: {e}",
                params={
                    "method_full_name": method_full_name,
                    "normalized_method": normalized_method,
                    "params_json": params_json,
                },
                exception=e,
            )

        # Optional entity resolution
        try:
            final_params = params
            if resolve and isinstance(params, dict):
                final_params = await _resolve_params(params)
        except Exception as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Failed to resolve parameters: {e}",
                params={
                    "method_full_name": method_full_name,
                    "normalized_method": normalized_method,
                    "params_json": params_json,
                },
                exception=e,
            )

        # Now invoke the actual MTProto method
        logger.debug(
            f"Invoking MTProto method: {normalized_method} with params: {_json_safe(final_params)}"
        )

        try:
            # Resolve method class
            method_cls, _ = _resolve_method_class(normalized_method)

            # Security: Validate and sanitize parameters
            sanitized_params = _sanitize_mtproto_params(final_params)

            # Create method object and invoke via Telethon
            method_obj = method_cls(**sanitized_params)
            client = await get_connected_client()
            result = await client(method_obj)

            # Process result to JSON-safe format
            result_dict = (
                result.to_dict() if hasattr(result, "to_dict") else str(result)
            )
            safe_result = _json_safe(result_dict)

            logger.info(f"MTProto method {normalized_method} invoked successfully")
            return safe_result

        except SessionNotAuthorizedError as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message="Session not authorized. Please authenticate your Telegram session first.",
                params={
                    "method_full_name": method_full_name,
                    "normalized_method": normalized_method,
                    "params": _json_safe(final_params),
                },
                exception=e,
                action="authenticate_session",
            )
        except Exception as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Failed to invoke MTProto method '{normalized_method}': {e!s}",
                params={
                    "method_full_name": method_full_name,
                    "normalized_method": normalized_method,
                    "params": _json_safe(final_params),
                },
                exception=e,
            )

    except Exception as e:
        return log_and_build_error(
            operation="invoke_mtproto",
            error_message=f"Error in invoke_mtproto: {e!s}",
            params={
                "method_full_name": method_full_name,
                "params_json": params_json,
            },
            exception=e,
        )
