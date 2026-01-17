import logging

from starlette.responses import JSONResponse

from src.client.connection import set_request_token
from src.config.server_config import get_config
from src.server_components.auth import extract_bearer_token_from_request
from src.tools.mtproto import DANGEROUS_METHODS, invoke_mtproto_impl
from src.utils.error_handling import log_and_build_error
from src.utils.helpers import normalize_method_name

logger = logging.getLogger(__name__)


def register_mtproto_api_routes(mcp_app) -> None:
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
        resolve = bool(body.get("resolve", True))  # Default to True
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
                    "param_keys": list(params.keys())
                    if isinstance(params, dict)
                    else [],
                },
            )
        except Exception:
            pass

        # Convert params dict to JSON string for the implementation
        import json

        # Prioritize params_json if it's provided, otherwise use params
        if params_json:
            final_params_json = params_json
        elif isinstance(params, dict) and params:
            final_params_json = json.dumps(params)
        else:
            final_params_json = "{}"

        # Invoke underlying tool using the shared implementation
        result = await invoke_mtproto_impl(
            method_full_name=normalized_method,
            params_json=final_params_json,
            allow_dangerous=allow_dangerous,
            resolve=resolve,  # Use the resolve parameter from request
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
