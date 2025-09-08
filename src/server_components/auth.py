from collections.abc import Callable
from functools import wraps

from loguru import logger

from src.client.connection import set_request_token
from src.config.server_config import get_config


def extract_bearer_token() -> str | None:
    """
    Extract Bearer token from HTTP Authorization header if running over HTTP.
    Returns None for non-HTTP transports or when header is missing/invalid.
    """
    try:
        config = get_config()
        if config.transport != "http":
            return None

        # Imported lazily to avoid dependency during stdio runs
        from fastmcp.server.dependencies import get_http_headers  # type: ignore

        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:].strip()
        return token or None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error extracting bearer token: {e}")
        return None


def with_auth_context(func: Callable) -> Callable:
    """Decorator to extract Bearer token and set it in request context.

    Behavior based on server mode:
    - stdio: No auth (default session only)
    - http-no-auth: Auth bypassed entirely
    - http-auth: Auth required (Bearer token mandatory)
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        config = get_config()

        if config.disable_auth:
            set_request_token(None)
            return await func(*args, **kwargs)

        # At this point, we're in http-auth mode - authentication is required
        token = extract_bearer_token()

        if not token:
            try:
                from fastmcp.server.dependencies import (
                    get_http_headers,  # type: ignore
                )

                headers = get_http_headers()
                auth_header = headers.get("authorization", "")
            except Exception:
                auth_header = ""

            if auth_header:
                error_msg = (
                    "Invalid authorization header format. Expected 'Bearer <token>' "
                    f"but got: {auth_header[:20]}..."
                )
            else:
                error_msg = (
                    "Missing Bearer token in Authorization header. HTTP requests require "
                    "authentication. Use: 'Authorization: Bearer <your-token>' header."
                )
            logger.warning(f"Authentication failed: {error_msg}")
            raise Exception(error_msg)

        set_request_token(token)
        logger.info(f"Bearer token extracted for request: {token[:8]}...")

        return await func(*args, **kwargs)

    return wrapper
