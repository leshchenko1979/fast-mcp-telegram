from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import asyncio
from src.config.settings import (
    API_ID, API_HASH, PHONE_NUMBER,
    SESSION_PATH
)

async def main():
    print("Starting Telegram session setup...")
    print(f"Session will be saved to: {SESSION_PATH}")
    print(f"Session directory: {SESSION_PATH.parent}")

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
