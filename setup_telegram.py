from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Get credentials from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'mcp_telegram_search')

# Use project directory for session file
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_PATH = os.path.join(PROJECT_DIR, SESSION_NAME)

async def main():
    print("Starting Telegram session setup...")
    print(f"Using session file: {SESSION_PATH}")

    # Create the client and connect
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"Sending code to {PHONE_NUMBER}...")
        await client.send_code_request(PHONE_NUMBER)

        code = input("Enter the code you received: ")
        try:
            await client.sign_in(PHONE_NUMBER, code)
        except SessionPasswordNeededError:
            # In case you have two-step verification enabled
            password = input("Please enter your 2FA password: ")
            await client.sign_in(password=password)

    print("Successfully authenticated!")

    # Test the connection by getting some dialogs
    async for dialog in client.iter_dialogs(limit=1):
        print(f"Successfully connected! Found chat: {dialog.name}")
        break

    await client.disconnect()
    print("Setup complete! You can now use the Telegram search functionality.")

if __name__ == '__main__':
    asyncio.run(main())
