"""
Session file-based token verifier for FastMCP Bearer authentication.

Validates opaque bearer tokens by checking that a corresponding session file
exists in the configured session directory. Used when running in http-auth mode.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastmcp.server.auth import AccessToken, TokenVerifier

from src.server_components.auth import RESERVED_SESSION_NAMES

if TYPE_CHECKING:
    from src.config.server_config import ServerConfig

logger = logging.getLogger(__name__)


class SessionFileTokenVerifier(TokenVerifier):
    """Token verifier that validates bearer tokens against existing session files.

    A token is valid if and only if:
    - It is not a reserved session name (telegram, default, etc.)
    - A file {session_directory}/{token}.session exists

    The token string is preserved in AccessToken.token for use by tools
    (get_client_by_token, etc.).
    """

    def __init__(self, config: "ServerConfig", **kwargs):
        """Initialize the verifier with server config.

        Args:
            config: ServerConfig instance providing session_directory
            **kwargs: Additional arguments passed to TokenVerifier (base_url, required_scopes)
        """
        super().__init__(**kwargs)
        self._config = config

    @property
    def _session_directory(self) -> Path:
        """Session directory from config."""
        return self._config.session_directory

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify token by checking that the session file exists.

        Args:
            token: Bearer token (session file name without .session)

        Returns:
            AccessToken with token set if valid, None otherwise
        """
        if not token or not token.strip():
            return None

        token = token.strip()

        if token.lower() in RESERVED_SESSION_NAMES:
            logger.warning(
                "Rejected reserved session name '%s' as bearer token",
                token,
            )
            return None

        session_path = self._session_directory / f"{token}.session"
        if not session_path.is_file():
            return None

        return AccessToken(
            token=token,
            client_id="telegram-session",
            scopes=[],
            expires_at=None,
            resource=None,
        )
