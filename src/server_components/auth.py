import os
from collections.abc import Callable
from functools import wraps

from loguru import logger

from src.client.connection import set_request_token
from src.config.settings import DISABLE_AUTH


def _get_transport() -> str:
    """Determine current transport from environment; defaults to stdio.

    This avoids tight coupling to server module globals.
    """
    return os.environ.get("MCP_TRANSPORT", "stdio").lower()


def extract_bearer_token() -> str | None:
    """
    Extract Bearer token from HTTP Authorization header if running over HTTP.
    Returns None for non-HTTP transports or when header is missing/invalid.
    """
    try:
        if _get_transport() != "http":
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

    - Bypasses auth entirely when DISABLE_AUTH=true
    - For HTTP transport with auth enabled, requires a valid Bearer token
    - For stdio transport, falls back to singleton behavior
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        if DISABLE_AUTH:
            set_request_token(None)
            return await func(*args, **kwargs)

        transport = _get_transport()
        token = extract_bearer_token()

        if not token:
            if transport == "http":
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

            # stdio fallback
            set_request_token(None)
            logger.info("No Bearer token provided, using default session")
        else:
            set_request_token(token)
            logger.info(f"Bearer token extracted for request: {token[:8]}...")

        return await func(*args, **kwargs)

    return wrapper
