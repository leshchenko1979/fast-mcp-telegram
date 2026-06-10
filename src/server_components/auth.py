import contextlib
import logging
import warnings
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastmcp.exceptions import ToolError

from src.client.connection import set_request_token
from src.config.server_config import cfg
from src.server_components.session_token_validation import (
    InvalidSessionTokenError,
    session_file_path,
    validate_session_token,
)

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""


def _auth_guidance_response(message: str | None = None) -> dict[str, Any]:
    """Return a structured MCP tool error with authentication guidance.

    This is returned by the ``require_auth`` decorator when the user
    is not authenticated, instead of raising an exception. The agent
    sees this as a tool call result (not a crash).
    """
    guidance = message or (
        "🔐 **Authentication Required**\n\n"
        "This Telegram MCP server requires authentication to use its tools.\n\n"
        "### How to authenticate:\n"
        "1. **Open the setup page** in your browser:\n"
        "   [Setup Page](/setup)\n\n"
        "2. **Scan the QR code** from Telegram mobile (recommended)\n"
        "   or enter your phone number on the same page.\n\n"
        "3. **Copy the bearer token** shown after successful login.\n\n"
        "4. **Configure your MCP client** by setting the Authorization header:\n"
        "   ```\n"
        "   Authorization: Bearer <your-token>\n"
        "   ```\n\n"
        "For clients that can't set headers, use URL-path authentication:\n"
        "   `/v1/url_auth/<your-token>/mcp`\n\n"
        "Once configured, the token identifies your session and all tools "
        "will work normally."
    )
    return {
        "isError": True,
        "content": [{"type": "text", "text": guidance}],
    }


def _get_bearer_token_from_http() -> str | None:
    """Extract Bearer token from the current HTTP request headers.

    Returns None if running on a non-HTTP transport or no token is present.
    The token is validated by ``_extract_bearer_token_from_headers``.
    """
    try:
        config = cfg()
        if config.transport != "http":
            return None

        # FastMCP exposes HTTP headers via this dependency
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers()
        return _extract_bearer_token_from_headers(headers)
    except Exception:  # pragma: no cover — defensive for stdio / test contexts
        return None


def require_auth(func: Callable) -> Callable:
    """Decorator that validates authentication before running the tool.

    Behavior:
    - **Auth disabled** (stdio, http-no-auth): runs the tool as-is, no auth check.
    - **Auth required** (http-auth): Extracts Bearer token from HTTP headers.
    - **No token / invalid token**: Returns a structured MCP error with
      clear guidance on how to authenticate (QR code, setup page, URL path auth).
    - **Valid token + session file exists**: Sets the request token in context
      and runs the tool.

    This replaces the old ``with_auth_context`` decorator. The key difference:
    instead of raising ``AuthenticationError`` (which crashes the tool call),
    it returns a structured response that agents can interpret.

    Backward compatible: existing bearer tokens, URL path auth, and the
    ``SessionFileTokenVerifier`` all work through this decorator.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        config = cfg()

        # Auth disabled: passthrough (stdio, http-no-auth)
        if config.disable_auth:
            set_request_token(None)
            return await func(*args, **kwargs)

        # Auth required: extract token from HTTP headers
        token = _get_bearer_token_from_http()

        # Fall back to FastMCP's get_access_token (backward compat for tests / old HTTP)
        if token is None:
            try:
                from fastmcp.server.dependencies import get_access_token

                access_token = get_access_token()
                if access_token is not None:
                    validated = access_token.token
                    set_request_token(validated)
                    return await func(*args, **kwargs)
            except ToolError:
                raise
            except Exception:
                pass

        if token is None:
            logger.info("Unauthenticated tool call — returning auth guidance")
            return _auth_guidance_response()

        # Validate token format
        try:
            validated = validate_session_token(token)
        except InvalidSessionTokenError:
            logger.warning("Invalid token format in tool call")
            return _auth_guidance_response(
                "Invalid bearer token format. "
                "Get a valid token from the [setup page](/setup)."
            )

        # Check session file exists
        session_path = session_file_path(config.session_directory, validated)
        if not session_path.exists():
            logger.info(
                "Token %s... has no session file — returning auth guidance",
                validated[:8],
            )
            return _auth_guidance_response(
                "This bearer token is not registered. "
                "Authenticate at the [setup page](/setup) to get a valid token."
            )

        # Token is valid and session exists — run the tool
        set_request_token(validated)
        return await func(*args, **kwargs)

    return wrapper


def _extract_bearer_token_from_headers(headers: dict[str, str]) -> str | None:
    """
    Extract Bearer token from HTTP headers with validation.

    Args:
        headers: Dictionary of HTTP headers

    Returns:
        Bearer token string if valid, None otherwise
    """
    auth_header = headers.get("authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None

    try:
        return validate_session_token(token)
    except InvalidSessionTokenError:
        return None


def extract_bearer_token() -> str | None:
    """
    Extract Bearer token from HTTP Authorization header if running over HTTP.
    Returns None for non-HTTP transports or when header is missing/invalid.
    Validates that token is not a reserved session name to prevent session conflicts.
    """
    try:
        config = cfg()
        if config.transport != "http":
            return None

        # Imported lazily to avoid dependency during stdio runs
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers()
        return _extract_bearer_token_from_headers(headers)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error extracting bearer token: {e}")
        return None


def with_auth_context(func: Callable) -> Callable:
    """(Deprecated) Legacy decorator — use ``require_auth`` instead.

    Kept for backward compatibility during migration. Calls ``require_auth``
    internally, but raises ``AuthenticationError`` when auth fails to
    preserve the old interface for code that catches it explicitly.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        warnings.warn(
            "with_auth_context is deprecated, use require_auth instead",
            DeprecationWarning,
            stacklevel=2,
        )
        config = cfg()

        if config.disable_auth:
            set_request_token(None)
            return await func(*args, **kwargs)

        # Try HTTP header extraction first (new HTTP mode without transport auth)
        token = _get_bearer_token_from_http()

        # Fall back to FastMCP's get_access_token (old HTTP mode with transport auth)
        if token is None:
            with contextlib.suppress(Exception):
                from fastmcp.server.dependencies import get_access_token

                access_token = get_access_token()
                if access_token is not None:
                    validated = access_token.token
                    set_request_token(validated)
                    logger.info(
                        f"Bearer token from auth provider: {validated[:8]}..."
                    )
                    return await func(*args, **kwargs)
            error_msg = (
                "Missing Bearer token in Authorization header. HTTP requests require "
                "authentication. Use: 'Authorization: Bearer <your-token>' header."
            )
            logger.warning(f"Authentication failed: {error_msg}")
            raise AuthenticationError(error_msg)

        try:
            validated = validate_session_token(token)
        except InvalidSessionTokenError:
            error_msg = "Invalid bearer token format."
            logger.warning(error_msg)
            raise AuthenticationError(error_msg) from None

        session_path = session_file_path(config.session_directory, validated)
        if not session_path.exists():
            error_msg = f"Token {validated[:8]}... has no session file."
            logger.warning(error_msg)
            raise AuthenticationError(error_msg)

        set_request_token(validated)
        logger.info(f"Bearer token for request: {validated[:8]}...")

        return await func(*args, **kwargs)

    return wrapper


def extract_bearer_token_from_request(request) -> str | None:
    """
    Extract Bearer token from an incoming Starlette request when running over HTTP.

    Behavior:
    - Reads Authorization header directly from the request (custom route safe)
    - Falls back to FastMCP's get_http_headers helper when available
    - Returns None in non-HTTP transports or when header is missing/invalid
    - Validates that token is not a reserved session name to prevent session conflicts
    """
    try:
        config = cfg()
        if config.transport != "http":
            return None

        # Prefer direct read from the incoming request (custom routes)
        with contextlib.suppress(Exception):
            headers = dict(request.headers)
            if token := _extract_bearer_token_from_headers(headers):
                return token
        # Fallback: FastMCP dependency (works in tool-execution context)
        try:  # pragma: no cover - optional path
            from fastmcp.server.dependencies import get_http_headers

            headers = get_http_headers()
            return _extract_bearer_token_from_headers(headers)
        except Exception:
            return None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error extracting bearer token from request: {e}")
        return None
