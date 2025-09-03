import argparse
import asyncio
import getpass
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from src.config.settings import (
    API_HASH,
    API_ID,
    PHONE_NUMBER,
    SESSION_DIR,
    SESSION_PATH,
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
        help="Custom session name (without .session extension)",
    )

    return parser.parse_args()


async def main():
    global SESSION_PATH  # Declare global for session path modification

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

    print("Starting Telegram session setup...")
    print(f"API ID: {api_id}")
    print(f"Phone: {phone_number}")
    print(f"Session will be saved to: {SESSION_PATH}")
    print(f"Session directory: {SESSION_PATH.parent}")

    # Handle session file conflicts
    if SESSION_PATH.exists():
        print(f"\n⚠️  Session file already exists: {SESSION_PATH}")
        print("This session may be invalidated or from a different IP address.")

        if args.overwrite:
            print("✓ Overwriting existing session (as requested)")
            if SESSION_PATH.is_dir():
                import shutil

                shutil.rmtree(SESSION_PATH)
                print("Removed session directory")
            else:
                SESSION_PATH.unlink(missing_ok=True)
        elif args.session_name:
            new_name = args.session_name
            if not new_name.endswith(".session"):
                new_name += ".session"
            new_session_path = SESSION_DIR / new_name
            print(f"Using custom session name: {new_session_path}")
            SESSION_PATH = new_session_path
        else:
            # Interactive mode only
            while True:
                choice = input(
                    "\nChoose an option:\n"
                    "1. Overwrite existing session (recommended)\n"
                    "2. Use different session name\n"
                    "3. Cancel setup\n"
                    "Enter choice (1-3): "
                ).strip()

                if choice == "1":
                    print(f"Removing existing session: {SESSION_PATH}")
                    if SESSION_PATH.is_dir():
                        import shutil

                        shutil.rmtree(SESSION_PATH)
                        print("✓ Existing session directory removed")
                    else:
                        SESSION_PATH.unlink(missing_ok=True)
                        print("✓ Existing session file removed")
                    break
                if choice == "2":
                    new_name = input(
                        "Enter new session name (without .session extension): "
                    ).strip()
                    if not new_name:
                        print("❌ Session name cannot be empty")
                        continue
                    if not new_name.endswith(".session"):
                        new_name += ".session"

                    new_session_path = SESSION_DIR / new_name
                    print(f"Using new session path: {new_session_path}")
                    SESSION_PATH = new_session_path
                    break
                if choice == "3":
                    print("Setup cancelled.")
                    return
                print("❌ Invalid choice. Please enter 1, 2, or 3.")

    print(f"\n🔐 Authenticating with session: {SESSION_PATH}")

    # Create the client and connect
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"Sending code to {phone_number}...")
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
    print(f"✅ Setup complete! Session saved to: {SESSION_PATH}")
    print("You can now use the Telegram search functionality.")


def sync_main():
    """Synchronous entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
