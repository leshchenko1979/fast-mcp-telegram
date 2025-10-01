from typing import Any

from loguru import logger
from starlette.responses import JSONResponse

from src.client.connection import get_connected_client, set_request_token
from src.config.server_config import get_config
from src.server_components.auth import extract_bearer_token_from_request
from src.tools.mtproto import invoke_mtproto_method
from src.utils.error_handling import log_and_build_error
from src.utils.helpers import normalize_method_name

DANGEROUS_METHODS = {
    "account.DeleteAccount",
    "messages.DeleteHistory",
    "messages.DeleteUserHistory",
    "messages.DeleteChatUser",
    "messages.DeleteMessages",
    "channels.DeleteHistory",
    "channels.DeleteMessages",
}


def register_mtproto_api_routes(mcp_app) -> None:
    async def _resolve_params(params: dict[str, Any]) -> dict[str, Any]:
        """Best-effort resolution of entity-like parameters using Telethon.

        Keys handled (singular and list): peer, from_peer, to_peer, user, user_id,
        channel, chat, chat_id, users, chats, peers.
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
        for key in list(resolved.keys()):
            if key in keys_to_resolve:
                value = resolved[key]
                if _is_list_like(value):
                    resolved[key] = [await _resolve_one(v) for v in value]
                else:
                    resolved[key] = await _resolve_one(value)
        return resolved

    def _build_unauthorized_error() -> JSONResponse:
        error = log_and_build_error(
            operation="mtproto_api",
            error_message=(
                "Missing Bearer token in Authorization header. HTTP requests require "
                "authentication. Use: 'Authorization: Bearer <your-token>' header."
            ),
            params=None,
        )
        return JSONResponse(error, status_code=401)

    @mcp_app.custom_route("/mtproto-api/{method}", methods=["POST"])
    @mcp_app.custom_route("/mtproto-api/v1/{method}", methods=["POST"])
    async def mtproto_api(request):
        config = get_config()

        # Auth handling per server mode
        if config.require_auth:
            token = extract_bearer_token_from_request(request)
            if not token:
                return _build_unauthorized_error()
            set_request_token(token)
        else:
            # In stdio or http-no-auth we do not require token
            set_request_token(None)

        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            error = log_and_build_error(
                operation="mtproto_api",
                error_message=f"Invalid JSON body: {e}",
                params=None,
            )
            return JSONResponse(error, status_code=400)

        method_raw = request.path_params.get("method", "")
        try:
            normalized_method = normalize_method_name(str(method_raw))
        except Exception as e:
            error = log_and_build_error(
                operation="mtproto_api",
                error_message=str(e),
                params={"method": method_raw},
            )
            return JSONResponse(error, status_code=400)

        params = body.get("params") or {}
        params_json = body.get("params_json") or ""
        resolve = bool(body.get("resolve", False))
        allow_dangerous = bool(body.get("allow_dangerous", False))

        # Deny dangerous methods unless explicitly allowed
        if (normalized_method in DANGEROUS_METHODS) and not allow_dangerous:
            error = log_and_build_error(
                operation="mtproto_api",
                error_message=(
                    f"Method '{normalized_method}' is blocked by default. "
                    "Pass 'allow_dangerous=true' to override."
                ),
                params={"method": normalized_method},
            )
            return JSONResponse(error, status_code=400)

        # Optional entity resolution
        try:
            final_params: dict[str, Any] = params
            if resolve and isinstance(params, dict):
                final_params = await _resolve_params(params)
        except Exception as e:
            error = log_and_build_error(
                operation="mtproto_api",
                error_message=f"Failed to resolve parameters: {e}",
                params={"method": normalized_method},
            )
            return JSONResponse(error, status_code=400)

        # Log method with sanitized info (no raw values)
        try:
            token_preview = "none"
            if config.require_auth:
                token_value = extract_bearer_token_from_request(request) or ""
                token_preview = (token_value[:8] + "...") if token_value else "missing"
            logger.info(
                "Invoking MTProto API",
                extra={
                    "method": normalized_method,
                    "token": token_preview,
                    "param_keys": list(final_params.keys())
                    if isinstance(final_params, dict)
                    else [],
                },
            )
        except Exception:
            pass

        # Invoke underlying tool
        result = await invoke_mtproto_method(
            method_full_name=normalized_method,
            params=final_params if isinstance(final_params, dict) else {},
            params_json=params_json if isinstance(params_json, str) else "",
        )

        # If result is an error dict, choose HTTP code by message
        if isinstance(result, dict) and result.get("ok") is False:
            message = (result.get("error") or "").lower()
            status = 400
            if "auth" in message and config.require_auth:
                status = 401
            elif any(k in message for k in ("failed", "exception", "traceback")):
                status = 500
            return JSONResponse(result, status_code=status)

        return JSONResponse(result, status_code=200)
