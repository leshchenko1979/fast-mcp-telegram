"""
Server configuration using pydantic_settings for clean environment and argument handling.
"""

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Native CLI parsing configuration
        cli_parse_args=True,
        cli_kebab_case=True,
        cli_exit_on_error=True,
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

    # Web setup configuration
    domain: str = Field(
        default="your-domain.com",
        description="Domain for web setup and config generation",
    )

    # Session management
    max_active_sessions: int = Field(
        default=10, ge=1, description="Maximum number of active sessions in LRU cache"
    )

    setup_session_ttl_seconds: int = Field(
        default=900, ge=60, description="TTL for temporary setup sessions (seconds)"
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
        if self.server_mode == ServerMode.STDIO:
            return "stdio"
        return "http"

    @property
    def disable_auth(self) -> bool:
        """Whether authentication is disabled."""
        return self.server_mode in (ServerMode.STDIO, ServerMode.HTTP_NO_AUTH)

    @property
    def require_auth(self) -> bool:
        """Whether authentication is required (no fallback)."""
        return self.server_mode == ServerMode.HTTP_AUTH

    @property
    def session_directory(self) -> Path:
        """Get session directory with smart defaults."""
        if self.session_dir:
            return Path(self.session_dir)

        # Use standard user config directory
        config_dir = Path.home() / ".config" / "fast-mcp-telegram"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def validate_config(self) -> None:
        """Validate configuration and log important information."""
        from loguru import logger

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

        # Validation warnings
        if self.transport == "stdio" and self.host != "127.0.0.1":
            logger.warning("⚠️ stdio transport ignores host setting")

        if self.server_mode == ServerMode.HTTP_AUTH and not self.api_id:
            logger.warning(
                "⚠️ Production mode without API credentials - ensure they're available for setup"
            )

    @classmethod
    def from_args_and_env(cls) -> "ServerConfig":
        """Create configuration from command line arguments and environment variables.

        With native CLI parsing, this simply creates the config instance.
        pydantic-settings automatically handles CLI args, env vars, and .env files.
        """
        config = cls()
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
