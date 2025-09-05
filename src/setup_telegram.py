import argparse
import asyncio
import getpass
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from src.client.connection import generate_bearer_token
from src.config.settings import (
    API_HASH,
    API_ID,
    PHONE_NUMBER,
    SESSION_DIR,
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Telegram MCP Server Setup")
    parser.add_argument(
        "--api-id",
        type=str,
        help="Telegram API ID (can also be set via API_ID environment variable)",
    )
    parser.add_argument(
        "--api-hash",
        type=str,
        help="Telegram API Hash (can also be set via API_HASH environment variable)",
    )
    parser.add_argument(
        "--phone",
        type=str,
        help="Phone number with country code (can also be set via PHONE_NUMBER environment variable)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Automatically overwrite existing session without prompting",
    )
    parser.add_argument(
        "--session-name",
        type=str,
        help="Override with custom session name instead of random token (for advanced users)",
    )

    return parser.parse_args()


async def main():
    global SESSION_PATH  # Declare global for session path modification

    def mask_phone_number(phone):
        """Redact all but the last 4 digits of a phone number."""
        if not phone or len(phone) < 4:
            return "****"
        return "*" * (len(phone) - 4) + phone[-4:]

    # Load environment variables from .env file
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✓ Loaded environment variables from: {env_file}")
    else:
        print(
            "⚠️  No .env file found. Using environment variables or command line arguments."
        )

    # Parse command line arguments
    args = parse_args()

    # Use CLI arguments if provided, otherwise fall back to environment variables
    api_id = args.api_id or API_ID
    api_hash = args.api_hash or API_HASH
    phone_number = args.phone or PHONE_NUMBER

    # Validate required credentials
    if not api_id:
        print(
            "❌ Error: API ID is required. Provide via --api-id argument or API_ID environment variable."
        )
        return
    if not api_hash:
        print(
            "❌ Error: API Hash is required. Provide via --api-hash argument or API_HASH environment variable."
        )
        return
    if not phone_number:
        print(
            "❌ Error: Phone number is required. Provide via --phone argument or PHONE_NUMBER environment variable."
        )
        return

    # Generate session name - use custom name if provided, otherwise random token
    if args.session_name:
        session_name = args.session_name
        if not session_name.endswith(".session"):
            session_name += ".session"
        bearer_token = args.session_name  # Use custom name as token for simplicity
        print(f"Using custom session name: {session_name}")
    else:
        # Generate a random bearer token for the session
        bearer_token = generate_bearer_token()
        session_name = f"{bearer_token}.session"
        print("Generated random bearer token for session")

    SESSION_PATH = SESSION_DIR / session_name

    print("Starting Telegram session setup...")
    print(f"API ID: {api_id}")
    print(f"Phone: {mask_phone_number(phone_number)}")
    print(f"Session will be saved to: {SESSION_PATH}")
    print(f"Session directory: {SESSION_PATH.parent}")

    # Handle session file conflicts (rare with random tokens, but handle gracefully)
    if SESSION_PATH.exists():
        print(f"\n⚠️  Session file already exists: {SESSION_PATH}")
        print("This might indicate a collision with an existing random token.")

        if args.overwrite:
            print("✓ Overwriting existing session (as requested)")
            SESSION_PATH.unlink(missing_ok=True)
        elif args.session_name:
            # Allow overriding with custom session name if provided
            new_name = args.session_name
            if not new_name.endswith(".session"):
                new_name += ".session"
            new_session_path = SESSION_DIR / new_name
            print(f"Using custom session name: {new_session_path}")
            SESSION_PATH = new_session_path
        else:
            # For random tokens, always overwrite since collision is unlikely
            print("✓ Overwriting existing session (random token collision)")
            SESSION_PATH.unlink(missing_ok=True)

    print(f"\n🔐 Authenticating with session: {SESSION_PATH}")

    # Create the client and connect
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"Sending code to {mask_phone_number(phone_number)}...")
        await client.send_code_request(phone_number)

        # Get verification code (interactive only)
        code = input("Enter the code you received: ")

        try:
            await client.sign_in(phone_number, code)
        except SessionPasswordNeededError:
            # In case you have two-step verification enabled
            password = getpass.getpass("Please enter your 2FA password: ")
            await client.sign_in(password=password)

    print("Successfully authenticated!")

    # Test the connection by getting some dialogs
    async for dialog in client.iter_dialogs(limit=1):
        print(f"Successfully connected! Found chat: {dialog.name}")
        break

    await client.disconnect()

    print("\n✅ Setup complete!")
    print(f"📁 Session saved to: {SESSION_PATH}")
    if args.session_name:
        print(f"🔑 Bearer Token (custom): {bearer_token}")
    else:
        print(f"🔑 Bearer Token: {bearer_token}")
    print("\n💡 Use this Bearer token for authentication when using the MCP server:")
    print(f"   Authorization: Bearer {bearer_token}")
    print("\n🚀 You can now use the Telegram search functionality!")


def sync_main():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
