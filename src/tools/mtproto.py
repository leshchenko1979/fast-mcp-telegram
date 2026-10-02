import json
import logging
import re
from typing import Any

from telethon.errors import RPCError
from telethon.errors.rpcerrorlist import rpc_errors_dict, rpc_errors_re

from src.client.connection import get_connected_client
from src.tools.mtproto_tl import (
    _construct_tl_params,
    _convert_peer_types,
    _fill_missing_int_defaults,
    _json_safe,
    _resolve_method_class,
    _resolve_params,
    _sanitize_mtproto_params,
    _unbound_message_id_params,
)
from src.utils.error_handling import log_and_build_error, log_connection_error_response
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


# Fields dropped from a raw invoke_mtproto result unless the caller opts in with
# include_sensitive=true. A raw passthrough carries no output schema of its own to
# protect the caller, which is exactly why it needs an explicit boundary:
#   phone        -- PII, with no legitimate passthrough use case
#   access_hash  -- credential-shaped handle; its holder can act as the entity
_SENSITIVE_RESULT_FIELDS = frozenset({"phone", "access_hash"})


def _strip_sensitive_fields(value: Any) -> Any:
    """Recursively drop _SENSITIVE_RESULT_FIELDS from a JSON-safe result.

    Applied AFTER _json_safe: by then every nested TL object has been expanded
    into plain dicts, so a User nested inside a messages.Messages envelope is
    reached. Filtering before _json_safe would miss exactly those.
    """
    if isinstance(value, dict):
        return {
            k: _strip_sensitive_fields(v)
            for k, v in value.items()
            if k not in _SENSITIVE_RESULT_FIELDS
        }
    if isinstance(value, list):
        return [_strip_sensitive_fields(v) for v in value]
    return value


# Reverse mapping: Telethon exception class -> Telegram RPC error code (from Telethon guts)
_RPC_CLASS_TO_CODE: dict[type, str] = {
    cls: code for code, cls in rpc_errors_dict.items()
}
for pattern, cls in rpc_errors_re:
    base = re.sub(r"\([^)]+\)", "", pattern).strip("_").replace("__", "_")
    _RPC_CLASS_TO_CODE[cls] = base

# Regex for Telegram raw error codes (UPPER_SNAKE_CASE)
_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _normalize_rpc_error_code(exception: Exception) -> str | None:
    """
    Map a Telethon RPCError to a stable, machine-readable Telegram error code.

    Uses Telethon's rpc_errors_dict and rpc_errors_re for mapping.
    Fallback: use exception.message if it matches UPPER_SNAKE_CASE.

    Returns:
        Error code string (e.g., "INVITE_HASH_EXPIRED") or None
    """
    if code := _RPC_CLASS_TO_CODE.get(type(exception)):
        return code
    if isinstance(exception, RPCError):
        msg = getattr(exception, "message", str(exception))
        if isinstance(msg, str) and _UPPER_SNAKE_RE.match(msg.strip()):
            return msg.strip()
    return None


# ============================================================================
# HIGH-LEVEL API FUNCTIONS
# ============================================================================


async def invoke_mtproto_impl(
    method_full_name: str,
    params_json: str,
    allow_dangerous: bool = False,
    resolve: bool = True,
    include_sensitive: bool = False,
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

        # Phase 1 — construct TL objects from nested dicts.
        # Runs unconditionally, regardless of the resolve flag: fixes
        # "Cannot cast dict to Peer" when resolve=false.
        final_params = params
        if isinstance(params, dict):
            try:
                final_params = _construct_tl_params(params)
            except Exception as e:
                return log_and_build_error(
                    operation="invoke_mtproto",
                    error_message=f"Failed to construct TL parameters: {e}",
                    params={
                        "method_full_name": method_full_name,
                        "normalized_method": normalized_method,
                        "params_json": params_json,
                    },
                    exception=e,
                )

            # Phase 2 — resolve entity-like parameters (opt-in).
            # Kept separate from construction so a client/session-store failure
            # (get_connected_client inside _resolve_params) is not reported as
            # a parameter-construction fault.
            if resolve:
                try:
                    final_params = await _resolve_params(final_params)
                except Exception as e:
                    return log_and_build_error(
                        operation="invoke_mtproto",
                        error_message=f"Failed to resolve entity parameters: {e}",
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

            # A bare message id on a request with no chat binding reads an
            # arbitrary dialog: ids are per-chat, so the server resolves one
            # against whatever the account can see. Refuse rather than let the
            # server guess -- a successful wrong read is worse than an error.
            unbound = _unbound_message_id_params(method_cls, sanitized_params)
            if unbound:
                return log_and_build_error(
                    operation="invoke_mtproto",
                    error_message=(
                        f"{normalized_method} declares no peer/channel field, so the "
                        f"message id(s) in {', '.join(unbound)} have nothing to bind "
                        "to and Telegram would resolve them against an arbitrary "
                        "dialog. Message ids are per-chat, so a bare id is not a "
                        "coordinate. Name the chat instead: "
                        'channels.GetMessages {"channel": -100..., "id": [N]} or '
                        'messages.GetHistory {"peer": ..., "limit": N}.'
                    ),
                    params={
                        "method_full_name": method_full_name,
                        "normalized_method": normalized_method,
                        "params_json": params_json,
                    },
                )

            # Fill missing required int params with 0 so callers that omit
            # offset_id / offset_date / add_offset / hash etc. get defaults
            # instead of a cryptic "missing N required" TypeError.
            _fill_missing_int_defaults(method_cls, sanitized_params)

            # Fix resolved peer types to match method's expected parameter types.
            # Case 1: method expects int → extract raw ID from InputPeer* / Input*
            #   (e.g. AddChatUserRequest.__init__(chat_id: int) gets 5417489797
            #    from InputPeerChat(chat_id=5417489797)).
            # Case 2: method expects Input* (string annotation) → fetch entity
            #   and construct Input* with access_hash (e.g. InputPeerChat → InputChat).
            _client = await get_connected_client()
            sanitized_params = await _convert_peer_types(
                _client, sanitized_params, method_cls
            )

            # Create method object and invoke via Telethon
            method_obj = method_cls(**sanitized_params)
            client = await get_connected_client()
            result = await client(method_obj)

            # Process result to JSON-safe format.
            # A non-object RPC result — a bare Bool (e.g. messages.EditChatAbout),
            # int or str — carries no to_dict(), and rendering it with str() yielded
            # the Python literal "True", which FastMCP rejects with
            # "structured_content must be a dict or None". The call had SUCCEEDED, so
            # the caller saw a hard error for a write that landed. Wrap it instead.
            if isinstance(result, dict):
                result_dict = result
            elif callable(getattr(result, "to_dict", None)):
                result_dict = result.to_dict()
            else:
                result_dict = {"result": result}
            safe_result = _json_safe(result_dict)
            if not include_sensitive:
                safe_result = _strip_sensitive_fields(safe_result)

            logger.info(f"MTProto method {normalized_method} invoked successfully")
            return safe_result

        except RPCError as e:
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Failed to invoke MTProto method '{normalized_method}': {e!s}",
                params={
                    "method_full_name": method_full_name,
                    "normalized_method": normalized_method,
                    "params": _json_safe(final_params),
                },
                exception=e,
                error_code=_normalize_rpc_error_code(e),
            )
        except Exception as e:
            invoke_err_params = {
                "method_full_name": method_full_name,
                "normalized_method": normalized_method,
                "params": _json_safe(final_params),
            }
            if (
                r := log_connection_error_response(
                    "invoke_mtproto", invoke_err_params, e
                )
            ) is not None:
                return r
            return log_and_build_error(
                operation="invoke_mtproto",
                error_message=f"Failed to invoke MTProto method '{normalized_method}': {e!s}",
                params=invoke_err_params,
                exception=e,
            )

    except Exception as e:
        outer_params = {
            "method_full_name": method_full_name,
            "params_json": params_json,
        }
        if (
            r := log_connection_error_response("invoke_mtproto", outer_params, e)
        ) is not None:
            return r
        return log_and_build_error(
            operation="invoke_mtproto",
            error_message=f"Error in invoke_mtproto: {e!s}",
            params=outer_params,
            exception=e,
        )
