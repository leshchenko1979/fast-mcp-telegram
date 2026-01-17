import logging
from collections.abc import Callable
from functools import wraps

from src.client.connection import set_request_token
from src.config.server_config import get_config

logger = logging.getLogger(__name__)

# Reserved session names that cannot be used as bearer tokens
# These are common default names that could conflict with STDIO/HTTP_NO_AUTH sessions
RESERVED_SESSION_NAMES = frozenset(
    {
        "telegram",  # Default session name
        "default",  # Common default name
        "session",  # Generic session name
        "bot",  # Bot session name
        "user",  # User session name
        "main",  # Main session name
        "primary",  # Primary session name
        "test",  # Test session name
        "dev",  # Development session name
        "prod",  # Production session name
    }
)


def extract_bearer_token() -> str | None:
    """
    Extract Bearer token from HTTP Authorization header if running over HTTP.
    Returns None for non-HTTP transports or when header is missing/invalid.
    Validates that token is not a reserved session name to prevent session conflicts.
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
        if not token:
            return None

        # Security validation: prevent reserved session names as bearer tokens
        if token.lower() in RESERVED_SESSION_NAMES:
            logger.warning(
                f"Rejected reserved session name '{token}' as bearer token to prevent session conflicts. "
                f"Reserved names: {sorted(RESERVED_SESSION_NAMES)}"
            )
            return None

        return token
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
        config = get_config()
        if config.transport != "http":
            return None

        # Prefer direct read from the incoming request (custom routes)
        try:
            auth_header = request.headers.get("authorization", "")
        except Exception:
            auth_header = ""

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if not token:
                return None

            # Security validation: prevent reserved session names as bearer tokens
            if token.lower() in RESERVED_SESSION_NAMES:
                logger.warning(
                    f"Rejected reserved session name '{token}' as bearer token to prevent session conflicts. "
                    f"Reserved names: {sorted(RESERVED_SESSION_NAMES)}"
                )
                return None

            return token

        # Fallback: FastMCP dependency (works in tool-execution context)
        try:  # pragma: no cover - optional path
            from fastmcp.server.dependencies import get_http_headers  # type: ignore

            headers = get_http_headers()
            auth_header = headers.get("authorization", "")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            token = auth_header[7:].strip()
            if not token:
                return None

            # Security validation: prevent reserved session names as bearer tokens
            if token.lower() in RESERVED_SESSION_NAMES:
                logger.warning(
                    f"Rejected reserved session name '{token}' as bearer token to prevent session conflicts. "
                    f"Reserved names: {sorted(RESERVED_SESSION_NAMES)}"
                )
                return None

            return token
        except Exception:
            return None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error extracting bearer token from request: {e}")
        return None
