"""
Server configuration using pydantic_settings for clean environment and argument handling.
"""

import logging
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Repo root (`src/config` -> three parents) so .env loads when cwd is wrong (e.g. MCP stdio).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# DOMAIN values treated as unset: no public origin for MCP URLs or attachment links.
_DOMAIN_PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {"your-domain.com", "your-server.com", "localhost"}
)


def _is_loopback_http_host(host_with_optional_port: str) -> bool:
    """True only for localhost / 127.0.0.1 with optional :port (not localhosting.com, etc.)."""
    h = host_with_optional_port.lower()
    if h in {"localhost", "127.0.0.1"}:
        return True
    host, sep, _ = h.partition(":")
    return bool(sep) and host in ("localhost", "127.0.0.1")


def _is_test_environment() -> bool:
    """Detect if we're running in a test environment where CLI parsing should be disabled."""
    # Check for pytest-related environment variables
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True

    # Check if pytest is in the call stack
    for frame_info in sys._current_frames().values():
        frame = frame_info
        while frame:
            if "pytest" in frame.f_code.co_filename:
                return True
            frame = frame.f_back

    # Check if pytest modules are imported
    pytest_modules = ["pytest", "_pytest", "pluggy"]
    return any(module_name in sys.modules for module_name in pytest_modules)


class ServerMode(str, Enum):
    """Server operation modes with clear authentication and transport behavior."""

    STDIO = "stdio"  # stdio transport, no auth (default session only)
    HTTP_NO_AUTH = "http-no-auth"  # http transport, auth disabled (development)
    HTTP_AUTH = "http-auth"  # http transport, auth required (production)


class ServerConfig(BaseSettings):
    """
    Server configuration with automatic environment variable and argument parsing.

    Supports three clear server modes:
    - stdio: Development with Cursor IDE (no auth, default session only)
    - http-no-auth: Development HTTP server (auth disabled)
    - http-auth: Production HTTP server (auth required)
    """

    model_config = SettingsConfigDict(
        # Load order: .env first, then .env.local overrides (same keys win from .env.local).
        # Repo-root files first (MCP stdio often has cwd=$HOME), then cwd `.env` / `.env.local` so
        # local overrides still win (e.g. tests that chdir into tmp_path).
        env_file=(
            str(PROJECT_ROOT / ".env"),
            str(PROJECT_ROOT / ".env.local"),
            ".env",
            ".env.local",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Empty export API_ID= in the parent shell must not beat non-empty values from .env
        env_ignore_empty=True,
        # Disable CLI parsing in test environments to avoid conflicts with pytest
        cli_parse_args=not _is_test_environment(),
        cli_kebab_case=True,
        cli_exit_on_error=not _is_test_environment(),  # Don't exit on error in tests
        cli_enforce_required=False,
    )

    # Server mode - determines transport and auth behavior
    server_mode: ServerMode = Field(
        default=ServerMode.STDIO,
        validation_alias=AliasChoices("mode", "server_mode"),
        description="Server operation mode: stdio (local dev), http-no-auth (dev server), http-auth (production)",
    )

    # Network configuration
    host: str = Field(
        default="127.0.0.1", description="Host to bind to (use 0.0.0.0 for production)"
    )

    port: int = Field(default=8000, ge=1, le=65535, description="Port to bind to")

    # Session configuration
    session_dir: str = Field(
        default="",
        description="Custom session directory (defaults to ~/.config/fast-mcp-telegram/)",
    )

    session_name: str = Field(
        default="telegram",
        description="Session file name (without .session extension) for stdio mode or custom sessions",
    )

    # Telegram API configuration
    api_id: str = Field(
        default="",
        description="Telegram API ID (get from https://my.telegram.org/apps)",
    )

    api_hash: str = Field(
        default="",
        description="Telegram API Hash (get from https://my.telegram.org/apps)",
    )

    phone_number: str = Field(
        default="",
        description="Phone number for Telegram authentication (include country code)",
    )

    bot_api_token: str = Field(
        default="",
        description=(
            "Bot token from @BotFather. Alternative to phone+OTP setup. "
            "When set, the server authenticates automatically on startup "
            "without interactive setup — ideal for Glama Try in Browser, "
            "CI/CD, and ephemeral deployments."
        ),
    )

    # Web setup, MCP URL generation, and attachment_download_url base (HTTP transport).
    domain: str = Field(
        default="your-domain.com",
        validation_alias=AliasChoices("domain", "DOMAIN"),
        description=(
            "Public host or full URL: web setup, generated MCP config, and attachment links. "
            "Host only → https:// added (http:// for localhost/127.0.0.1). "
            "Placeholder values disable public attachment URLs."
        ),
    )

    # Session management
    max_active_sessions: int = Field(
        default=10, ge=1, description="Maximum number of active sessions in LRU cache"
    )

    setup_session_ttl_seconds: int = Field(
        default=900, ge=60, description="TTL for temporary setup sessions (seconds)"
    )

    entity_cache_limit: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of entities to cache per Telegram client",
    )

    # MTProto proxy configuration
    mtproto_proxy: str | None = Field(
        default=None,
        description=(
            "MTProto proxy URL in format: tg://proxy?server=host&port=443&secret=xxx "
            "or just: host:port:secret"
        ),
    )

    # File download security
    allow_http_urls: bool = Field(
        default=False, description="Allow HTTP URLs (insecure, only for development)"
    )
    max_file_size_mb: int = Field(
        default=50, description="Maximum file size for downloads (MB)"
    )
    block_private_ips: bool = Field(
        default=True, description="Block access to private IP ranges"
    )

    prefix_mcp_tools_with_account: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "prefix_mcp_tools_with_account",
            "PREFIX_MCP_TOOLS_WITH_ACCOUNT",
        ),
        description=(
            "Prefix MCP tool names per Bearer session with Telegram username "
            "or numeric user ID (multi-account agents)"
        ),
    )

    attachment_ticket_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400 * 7,
        validation_alias=AliasChoices(
            "attachment_ticket_ttl_seconds", "ATTACHMENT_TICKET_TTL_SECONDS"
        ),
        description="TTL for in-memory attachment download tickets (seconds)",
    )

    acl_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("acl_enabled", "ACL_ENABLED"),
        description=(
            "Enable opt-in per-token session ACL from acl config file (http-auth only)"
        ),
    )

    acl_config_path: str = Field(
        default="",
        validation_alias=AliasChoices("acl_config_path", "ACL_CONFIG_PATH"),
        description=(
            "Path to session ACL YAML/JSON file (default: {session_directory}/acl.yaml)"
        ),
    )

    acl_deny_unlisted_principals: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "acl_deny_unlisted_principals", "ACL_DENY_UNLISTED_PRINCIPALS"
        ),
        description=(
            "When ACL is enabled, deny all tool access for principals omitted "
            "from the ACL principals map (synthetic empty lane). Default false "
            "preserves full access for unlisted principals."
        ),
    )

    # Logging configuration
    log_level: str = Field(
        default="DEBUG", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    # Session inactivity cleanup (delete unused .session files)
    inactive_session_days: int = Field(
        default=30,
        ge=0,
        validation_alias=AliasChoices(
            "inactive_session_days",
            "TELEGRAM_INACTIVE_SESSION_DAYS",
        ),
        description=(
            "Auto-delete .session files unused for >N days. "
            "Set to 0 to disable. Uses file mtime to determine inactivity."
        ),
    )

    # Backward compatibility: DISABLE_AUTH environment variable
    disable_auth_env: str | None = Field(
        default=None,
        validation_alias="DISABLE_AUTH",
        description="DISABLE_AUTH environment variable value",
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str, info) -> str:
        """Set smart defaults for host based on server mode."""
        if not v or v == "127.0.0.1":
            # Get server_mode from values if available
            mode = info.data.get("server_mode", ServerMode.STDIO)
            if mode in (ServerMode.HTTP_AUTH, ServerMode.HTTP_NO_AUTH):
                return "0.0.0.0"  # Production HTTP should bind to all interfaces
        return v

    @property
    def transport(self) -> Literal["stdio", "http"]:
        """Transport type based on server mode."""
        return "stdio" if self.server_mode == ServerMode.STDIO else "http"

    @property
    def disable_auth(self) -> bool:
        """Whether authentication is disabled."""
        # Check for DISABLE_AUTH environment variable first (backward compatibility)
        if self.disable_auth_env is not None and self.disable_auth_env.strip():
            # Parse string values to boolean
            env_value = self.disable_auth_env.lower().strip()
            if env_value in ("true", "1", "yes", "on"):
                return True
            if env_value in ("false", "0", "no", "off"):
                return False
            # Invalid values are ignored, fall through to server mode logic

        # Otherwise use server mode logic
        return self.server_mode in (ServerMode.STDIO, ServerMode.HTTP_NO_AUTH)

    @property
    def require_auth(self) -> bool:
        """Whether authentication is required (no fallback)."""
        return self.server_mode == ServerMode.HTTP_AUTH

    @property
    def acl_config_file(self) -> Path:
        """Resolved ACL config path."""
        if self.acl_config_path.strip():
            return Path(self.acl_config_path).expanduser()
        return self.session_directory / "acl.yaml"

    @property
    def session_directory(self) -> Path:
        """Get session directory with smart defaults."""
        if self.session_dir:
            return Path(self.session_dir)

        # Use standard user config directory
        config_dir = Path.home() / ".config" / "fast-mcp-telegram"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @property
    def session_path(self) -> Path:
        """Get full session file path (without .session extension - Telethon adds it)."""
        return self.session_directory / self.session_name

    @property
    def public_base_url_normalized(self) -> str:
        """Public origin for attachment links, derived from DOMAIN (no trailing slash)."""
        raw = (self.domain or "").strip()
        if not raw or raw.lower() in _DOMAIN_PLACEHOLDER_VALUES:
            return ""
        if "://" in raw:
            return raw.rstrip("/")
        host_part = raw.split("/", 1)[0].lower()
        if _is_loopback_http_host(host_part):
            return f"http://{raw}".rstrip("/")
        return f"https://{raw}".rstrip("/")

    def validate_config(self) -> None:
        """Validate configuration and log important information."""
        # Prevent repeated logging by checking if already logged
        if hasattr(self, "_config_logged"):
            return

        logger.info(f"🚀 Server mode: {self.server_mode.value}")
        logger.info(f"🌐 Transport: {self.transport}")

        if self.transport == "http":
            logger.info(f"🔗 Binding to {self.host}:{self.port}")

        if self.server_mode == ServerMode.STDIO:
            logger.info("🔓 Authentication DISABLED - Default session only")
        elif self.server_mode == ServerMode.HTTP_NO_AUTH:
            logger.info("🔓 Authentication DISABLED for development mode")
        elif self.require_auth:
            logger.info("🔐 Authentication REQUIRED - Bearer token mandatory")

        logger.info(f"📁 Session directory: {self.session_directory}")

        if self.mtproto_proxy:
            logger.info("🔌 MTProto proxy: enabled")

        if self.prefix_mcp_tools_with_account:
            logger.info("🏷️ Account-prefixed MCP tool names enabled")

        # Mark as logged to prevent repeated messages
        self._config_logged = True

        # Validation warnings
        if self.transport == "stdio" and self.host != "127.0.0.1":
            logger.warning("⚠️ stdio transport ignores host setting")

        if self.server_mode == ServerMode.HTTP_AUTH and not self.api_id:
            logger.warning(
                "⚠️ Production mode without API credentials - ensure they're available for setup"
            )

        if self.acl_enabled and not self.disable_auth:
            from src.server_components.session_acl import validate_acl_config

            validate_acl_config()
            logger.info(f"🔒 Session ACL enabled: {self.acl_config_file}")

        if self.transport == "http" and not self.public_base_url_normalized:
            logger.warning(
                "⚠️ DOMAIN is '%s' — attachment_download_url DISABLED for all messages. "
                "Set DOMAIN=<your-public-host> in .env to enable download links.",
                self.domain,
            )

    @classmethod
    def from_args_and_env(cls) -> "ServerConfig":
        """Create configuration from command line arguments and environment variables.

        With native CLI parsing, this simply creates the config instance.
        pydantic-settings automatically handles CLI args, env vars, and .env files.
        """
        global _config
        config = cls()
        # Register before validate_config so ACL and other validators can call get_config()
        # without re-entering from_args_and_env (RecursionError during startup).
        _config = config
        config.validate_config()
        return config


# Global configuration instance
_config: ServerConfig | None = None


def get_config() -> ServerConfig:
    """Get the global server configuration instance."""
    global _config
    if _config is None:
        _config = ServerConfig.from_args_and_env()
    return _config


def set_config(config: ServerConfig) -> None:
    """Set the global server configuration instance (for testing)."""
    global _config
    _config = config
