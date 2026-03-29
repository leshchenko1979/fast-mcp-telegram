"""
ASGI middleware for URL-based bearer token authentication.

This middleware allows clients that cannot set custom HTTP headers to authenticate
by including the bearer token in the URL path instead. For example:

    POST /v1/url_auth/{token}/mcp/tools/call

The middleware:
1. Extracts the token from the URL path
2. Validates the token against reserved names
3. Rewrites the path to /v1/mcp/... (removing the token prefix)
4. Injects Authorization header
5. Forwards to FastMCP

This is an alternative to header-based auth:
    Authorization: Bearer <token>

URL-based auth is less secure (token appears in logs) but is necessary for
clients that don't support custom headers.
"""

import logging
import re
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.server_components.auth import RESERVED_SESSION_NAMES

if TYPE_CHECKING:
    from src.config.server_config import ServerConfig

logger = logging.getLogger(__name__)

# Path pattern to match: /v1/url_auth/{token}/mcp/{method}
# The token is extracted from the URL and validated against reserved names.
# The matched portion is replaced with /v1/mcp/{method}
#
# Examples:
#   /v1/url_auth/TOKEN/mcp/tools/call -> /v1/mcp/tools/call (with token)
#   /v1/url_auth/TOKEN/mcp/resources/read -> /v1/mcp/resources/read (with token)
#   /v1/url_auth/TOKEN/mcp/initialize -> /v1/mcp/initialize (with token)
#
# Non-matching:
#   /v1/mcp/... -> Not matched (header-based auth)
#   /health -> Not matched
#   /setup -> Not matched
PATH_PATTERN = re.compile(r"^/v1/url_auth/([^/]+)/mcp/")


class UrlTokenMiddleware(BaseHTTPMiddleware):
    """Injects Authorization header from URL path for clients that cannot set headers.

    This middleware:
    1. Matches requests to /v1/url_auth/{token}/mcp/... paths
    2. Extracts the token from the URL path
    3. Validates the token (rejects reserved session names)
    4. Rewrites path to /v1/mcp/... (FastMCP mount point)
    5. Injects Authorization: Bearer <token> header
    6. Passes the request to FastMCP
    """

    def __init__(self, app, config: "ServerConfig"):
        """Initialize middleware with config for domain/URL info.

        Args:
            app: The ASGI application (FastMCP app mounted at /v1/mcp)
            config: ServerConfig for domain and other settings
        """
        super().__init__(app)
        self._config = config

    @property
    def _domain(self) -> str:
        """Get the configured domain."""
        return self._config.domain or "your-server.com"

    async def dispatch(self, request: Request, call_next):
        """Process the request and inject auth header if URL contains token."""
        path = request.url.path

        # Only process URL-auth paths
        match = PATH_PATTERN.match(path)
        if not match:
            return await call_next(request)

        token = match.group(1)

        # Security: reject reserved session names from URL
        if token.lower() in RESERVED_SESSION_NAMES:
            logger.warning(f"Rejected reserved session name '{token}' from URL path")
            return JSONResponse(
                {
                    "error": "Invalid token in URL. Use header-based authentication instead."
                },
                status_code=401,
            )

        # Rewrite path: /v1/url_auth/{token}/mcp/{method} -> /v1/mcp/{method}
        # This makes FastMCP receive the request at its normal mount point
        new_path = f"/v1/mcp/{path[len(match.group(0)) :]}"
        # Modify scope directly since request.url is read-only
        request.scope["path"] = new_path

        # Inject Authorization header
        # We do this by modifying the request headers directly
        # Starlette's Headers class stores headers as a list of "key:value" bytes
        auth_value = f"Bearer {token}"
        request.headers.__dict__["_list"].append(f"authorization:{auth_value}".encode())

        logger.debug(f"URL token middleware injected auth for token: {token[:8]}...")

        return await call_next(request)


def _rewrite_url(url, new_path: str):
    """Create a new URL with a different path."""
    from urllib.parse import urlunsplit

    scheme = url.scheme if hasattr(url, "scheme") else "https"
    netloc = url.netloc if hasattr(url, "netloc") else ""
    query = url.query if hasattr(url, "query") else ""

    new_url = urlunsplit((scheme, netloc, new_path, query, ""))

    class RewrittenUrl:
        def __init__(self, url_str, path):
            self._url = url_str
            self._path = path

        @property
        def path(self):
            return self._path

        @property
        def path_params(self):
            return getattr(url, "path_params", {})

        def __repr__(self):
            return f"RewrittenUrl(path={self._path})"

    return RewrittenUrl(new_url, new_path)


def generate_url_based_config(domain: str, token: str) -> dict:
    """Generate MCP config for URL-based authentication.

    Args:
        domain: The server domain
        token: The bearer token

    Returns:
        MCP config dictionary for URL-based auth
    """
    return {
        "mcpServers": {
            "telegram": {
                "url": f"https://{domain}/v1/url_auth/{token}/mcp",
            }
        }
    }
