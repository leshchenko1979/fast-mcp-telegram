import base64
import random
from importlib import import_module
from typing import Any

from loguru import logger

from src.client.connection import get_connected_client
from src.utils.error_handling import log_and_build_error


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


async def invoke_mtproto_method(
    method_full_name: str, params: dict[str, Any], params_json: str = ""
) -> dict[str, Any]:
    """
    Dynamically invoke any MTProto method by name and parameters.

    Args:
        method_full_name: Full class name of the MTProto method, e.g., 'messages.GetHistory'
        params: Dictionary of parameters for the method
    Returns:
        Result of the method call as a dict, or error info
    """
    logger.debug(f"Invoking MTProto method: {method_full_name} with params: {params}")

    try:
        # Security: Validate and sanitize parameters
        sanitized_params = _sanitize_mtproto_params(params)

        # Parse method_full_name
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

        # Simplify SendMessage: auto-generate random_id if not provided
        if (
            method_full_name == "messages.SendMessage"
            and "random_id" not in sanitized_params
        ):
            sanitized_params["random_id"] = random.getrandbits(64)

        method_obj = method_cls(**sanitized_params)
        client = await get_connected_client()
        result = await client(method_obj)
        # Try to convert result to dict (if possible)
        result_dict = result.to_dict() if hasattr(result, "to_dict") else str(result)
        safe_result = _json_safe(result_dict)
        logger.info(f"MTProto method {method_full_name} invoked successfully")
        return safe_result
    except Exception as e:
        return log_and_build_error(
            operation="invoke_mtproto",
            error_message=f"Failed to invoke MTProto method '{method_full_name}': {e!s}",
            params={
                "method_full_name": method_full_name,
                "params_json": params_json,
            },
            exception=e,
        )


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
