"""
Simplified Telegram MCP server setup using pydantic-settings.
"""

import asyncio
import getpass
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, CliImplicitFlag, SettingsConfigDict
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

import base64
import secrets


class SetupConfig(BaseSettings):
    """
    Setup configuration with automatic CLI parsing.

    This handles only setup-specific options, not server configuration.
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
        description="Phone number with country code (e.g., +1234567890)",
    )

    # Setup options
    overwrite: CliImplicitFlag[bool] = Field(
        default=False,
        description="Automatically overwrite existing session without prompting",
    )

    session_name: str = Field(
        default="",
        description="Custom session name instead of random token (for advanced users)",
    )

    # Session directory (for setup only)
    session_dir: str = Field(
        default="",
        description="Custom session directory (defaults to ~/.config/fast-mcp-telegram/)",
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
        if not self.phone_number:
            raise ValueError(
                "Phone number is required. Provide via --phone-number argument or PHONE_NUMBER environment variable."
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


async def setup_telegram_session(setup_config: SetupConfig) -> tuple[Path, str]:
    """Set up Telegram session and return session path and bearer token."""

    # Get session directory
    if setup_config.session_dir:
        session_dir = Path(setup_config.session_dir)
    else:
        # Use standard user config directory
        session_dir = Path.home() / ".config" / "fast-mcp-telegram"

    session_dir.mkdir(parents=True, exist_ok=True)

    # Generate session name and bearer token
    if setup_config.session_name:
        session_name = setup_config.session_name
        if not session_name.endswith(".session"):
            session_name += ".session"
        bearer_token = (
            setup_config.session_name
        )  # Use custom name as token for simplicity
        print(f"Using custom session name: {session_name}")
    else:
        # Generate a random bearer token for the session
        bearer_token = generate_bearer_token()
        session_name = f"{bearer_token}.session"
        print("Generated random bearer token for session")

    session_path = session_dir / session_name

    print("Starting Telegram session setup...")
    print(f"API ID: {setup_config.api_id}")
    print(f"Phone: {mask_phone_number(setup_config.phone_number)}")
    print(f"Session will be saved to: {session_path}")
    print(f"Session directory: {session_path.parent}")

    # Handle session file conflicts
    if session_path.exists():
        print(f"\n⚠️  Session file already exists: {session_path}")

        if setup_config.overwrite:
            print("✓ Overwriting existing session (as requested)")
            session_path.unlink(missing_ok=True)
        elif setup_config.session_name:
            # Custom session name - user choice
            response = input("Overwrite existing session? [y/N]: ").lower().strip()
            if response in ("y", "yes"):
                session_path.unlink(missing_ok=True)
            else:
                print("❌ Setup cancelled")
                return session_path, bearer_token
        else:
            # Random token collision (very unlikely)
            print("✓ Overwriting existing session (random token collision)")
            session_path.unlink(missing_ok=True)

    print(f"\n🔐 Authenticating with session: {session_path}")

    # Create the client and connect
    client = TelegramClient(session_path, setup_config.api_id, setup_config.api_hash)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f"Sending code to {mask_phone_number(setup_config.phone_number)}...")
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


async def main():
    """Main setup function."""

    try:
        # Create setup configuration with automatic CLI parsing
        setup_config = SetupConfig()

        # Validate required fields
        setup_config.validate_required_fields()

        # Set up Telegram session
        session_path, bearer_token = await setup_telegram_session(setup_config)

        print("\n✅ Setup complete!")
        print(f"📁 Session saved to: {session_path}")
        if setup_config.session_name:
            print(f"🔑 Bearer Token (custom): {bearer_token}")
        else:
            print(f"🔑 Bearer Token: {bearer_token}")
        print(
            "\n💡 Use this Bearer token for authentication when using the MCP server:"
        )
        print(f"   Authorization: Bearer {bearer_token}")
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
