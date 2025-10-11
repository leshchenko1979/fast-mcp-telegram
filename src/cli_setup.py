"""
Simplified Telegram MCP server setup using unified ServerConfig.
"""

import asyncio
import base64
import getpass
import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import CliImplicitFlag, SettingsConfigDict
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from .config.server_config import ServerConfig, ServerMode
from .utils.mcp_config import generate_mcp_config_json


class SetupConfig(ServerConfig):
    """
    Setup configuration extending ServerConfig with setup-specific options.

    Inherits all server configuration (API credentials, session settings, etc.)
    and adds setup-specific options like overwrite flag.
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

    # Setup-specific options
    overwrite: CliImplicitFlag[bool] = Field(
        default=False,
        description="Automatically overwrite existing session without prompting",
    )

    bot_token: str = Field(
        default="",
        description="Bot token from BotFather (for bot account setup)",
    )

    def validate_required_fields(self) -> None:
        """Validate that required fields are provided."""
        if not self.api_id:
            raise ValueError(
                "API ID is required. Provide via --api-id argument or API_ID environment variable."
            )
        if not self.api_hash:
            raise ValueError(
                "API Hash is required. Provide via --api-hash argument or API_HASH environment variable."
            )

        # Either phone number (for user account) or bot token (for bot account) is required
        if not self.bot_token and not self.phone_number:
            raise ValueError(
                "Either phone number (for user account) or bot token (for bot account) is required. "
                "Provide via --phone-number or --bot-token argument, or corresponding environment variables."
            )


def generate_bearer_token() -> str:
    """Generate a cryptographically secure bearer token for session management."""
    # Generate 32 bytes (256-bit) of random data
    token_bytes = secrets.token_bytes(32)
    # Encode as URL-safe base64 and strip padding
    return base64.urlsafe_b64encode(token_bytes).decode().rstrip("=")


def mask_phone_number(phone: str) -> str:
    """Redact all but the last 4 digits of a phone number."""
    if not phone or len(phone) < 4:
        return "****"
    return "*" * (len(phone) - 4) + phone[-4:]


async def setup_telegram_session(setup_config: SetupConfig) -> tuple[Path, str | None]:
    """Set up Telegram session and return session path and bearer token (None for STDIO/HTTP_NO_AUTH)."""

    session_dir = setup_config.session_directory

    # Ensure directory exists
    session_dir.mkdir(parents=True, exist_ok=True)

    # Determine session behavior based on server mode
    if setup_config.server_mode == ServerMode.HTTP_AUTH:
        # HTTP_AUTH mode: Generate random bearer token and use it as session name
        # This is the security model for production multi-user deployments
        bearer_token = generate_bearer_token()
        session_path = session_dir / bearer_token
        print(
            f"Setting up HTTP_AUTH session: {bearer_token[:12]}...{bearer_token[-4:]}.session"
        )
        print("(Random token ensures security for multi-user production)")
    else:
        # STDIO or HTTP_NO_AUTH mode: Use configured session name
        # This allows user-controlled session names like "personal", "work", etc.
        session_path = setup_config.session_path
        bearer_token = None  # No bearer token for STDIO/HTTP_NO_AUTH modes
        print(f"Setting up session: {setup_config.session_name}.session")
        print(f"(Mode: {setup_config.server_mode.value})")

    print("\nStarting Telegram session setup...")
    print(f"API ID: {setup_config.api_id}")

    if setup_config.bot_token:
        print("Bot token: [REDACTED]")
        print("Account type: Bot")
    else:
        print(f"Phone: {mask_phone_number(setup_config.phone_number)}")
        print("Account type: User")

    # Note: Telethon adds .session extension automatically to session_path
    # So we pass session_path without .session, and Telethon creates session_path.session
    actual_session_file = Path(str(session_path) + ".session")
    print(f"Session will be saved to: {actual_session_file}")
    print(f"Session directory: {session_dir}")

    # Handle session file conflicts
    if actual_session_file.exists():
        print(f"\n⚠️  Session file already exists: {actual_session_file}")

        if setup_config.overwrite:
            print("✓ Overwriting existing session (as requested)")
            actual_session_file.unlink(missing_ok=True)
        else:
            # Ask user for confirmation
            response = input("Overwrite existing session? [y/N]: ").lower().strip()
            if response in ("y", "yes"):
                actual_session_file.unlink(missing_ok=True)
            else:
                print("❌ Setup cancelled")
                return session_path, bearer_token

    print(f"\n🔐 Authenticating with session: {setup_config.session_name}")

    # Create the client and connect
    client = TelegramClient(
        session_path,
        setup_config.api_id,
        setup_config.api_hash,
        entity_cache_limit=setup_config.entity_cache_limit,
    )

    try:
        await client.connect()

        if setup_config.bot_token:
            # Bot authentication
            print("Authenticating as bot...")
            await client.start(bot_token=setup_config.bot_token)
            print("Successfully authenticated as bot!")

            # Test the connection by getting bot info
            me = await client.get_me()
            print(f"Bot username: @{me.username}")
            print(f"Bot name: {me.first_name}")
        else:
            # User authentication
            if not await client.is_user_authorized():
                print(
                    f"Sending code to {mask_phone_number(setup_config.phone_number)}..."
                )
                await client.send_code_request(setup_config.phone_number)

                # Get verification code (interactive only)
                code = input("Enter the code you received: ")

                try:
                    await client.sign_in(setup_config.phone_number, code)
                except SessionPasswordNeededError:
                    # In case you have two-step verification enabled
                    password = getpass.getpass("Please enter your 2FA password: ")
                    await client.sign_in(password=password)

            print("Successfully authenticated!")

            # Test the connection by getting some dialogs
            async for dialog in client.iter_dialogs(limit=1):
                print(f"Successfully connected! Found chat: {dialog.name}")
                break

    finally:
        await client.disconnect()

    return session_path, bearer_token


def _print_mode_instructions(
    mode: ServerMode,
    session_path: Path,
    session_name: str,
    bearer_token: str | None,
    domain: str | None = None,
    api_id: str = "",
    api_hash: str = "",
) -> None:
    """Print mode-specific setup instructions with MCP config."""
    # Generate MCP config using shared utility
    config_json = generate_mcp_config_json(
        mode, session_name, bearer_token, domain, api_id, api_hash
    )

    # Print session info
    print(f"📁 Session saved to: {session_path}.session")

    if mode == ServerMode.HTTP_AUTH:
        print(f"🔑 Bearer Token: {bearer_token}")
        print("\n⚠️  SECURITY: Keep this Bearer token secret!")
        print("   Anyone with this token can access your Telegram account")
    else:
        print(f"🔑 Session name: {session_name}")

    # Print MCP configuration
    print("\n📋 MCP Configuration (add to your MCP client):")
    print(config_json)

    # Print mode-specific notes
    if mode == ServerMode.HTTP_AUTH:
        print("\n💡 For HTTP_AUTH mode (production):")
        print(
            f"   Configure your server domain via DOMAIN env var (currently: {domain or 'your-server.com'})"
        )
        print("   The Bearer token above is required for authentication")
    elif mode == ServerMode.HTTP_NO_AUTH:
        print("\n💡 For HTTP_NO_AUTH mode (development):")
        print("   Start server with: fast-mcp-telegram --mode http-no-auth")
        print("   No authentication needed - use for local development only")
    else:  # STDIO
        print("\n💡 For STDIO mode (Cursor IDE):")
        print("   Save the config above to your Cursor MCP settings")
        if session_name != "telegram":
            print(f"   Note: Using custom session name '{session_name}'")


async def main():
    """Main setup function."""

    try:
        # Create setup configuration with automatic CLI parsing
        setup_config = SetupConfig()

        # Validate required fields
        setup_config.validate_required_fields()

        # Set up Telegram session
        session_path, bearer_token = await setup_telegram_session(setup_config)

        # Display results
        print("\n✅ Setup complete!")
        _print_mode_instructions(
            setup_config.server_mode,
            session_path,
            setup_config.session_name,
            bearer_token,
            setup_config.domain,
            setup_config.api_id,
            setup_config.api_hash,
        )

        # Display account type specific information
        if setup_config.bot_token:
            print("\n🤖 Bot setup complete! You can now use the MTProto bridge:")
            print("   - Use /mtproto-api/... endpoints for bot operations")
            print(
                "   - High-level tools (search, send_message, etc.) are disabled for bots"
            )
        else:
            print("\n🚀 You can now use the Telegram search functionality!")

    except ValueError as e:
        print(f"❌ Error: {e}")
        return
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return


def sync_main():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
