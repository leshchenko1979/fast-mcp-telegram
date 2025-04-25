from telethon import TelegramClient
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime

# Load environment variables
load_dotenv()

# Get credentials from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'mcp_telegram_search')

async def test_search(query: str = "склады", limit: int = 20):
    print(f"\n=== Testing Telegram Search ===")
    print(f"Query: {query}")
    print(f"Limit: {limit}")
    print("=" * 30)

    # Create and connect client
    print("\nConnecting to Telegram...")
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("Not authorized. Please run setup_telegram.py first")
        return

    print("Successfully connected!")

    try:
        # First test: List some dialogs
        print("\nTesting dialog listing...")
        dialog_count = 0
        async for dialog in client.iter_dialogs(limit=5):
            print(f"Dialog: {dialog.name} (ID: {dialog.id})")
            dialog_count += 1
        print(f"Found {dialog_count} dialogs")

        # Second test: Search in all dialogs
        print(f"\nSearching for '{query}' in all dialogs...")
        results = []
        async for dialog in client.iter_dialogs():
            try:
                print(f"\nSearching in {dialog.name}...")
                message_count = 0
                async for message in client.iter_messages(dialog, limit=limit * 2):
                    if not message.text:
                        continue
                    if query.lower() in message.text.lower():
                        message_count += 1
                        results.append({
                            "id": message.id,
                            "date": message.date.isoformat(),
                            "chat_id": message.chat_id,
                            "chat_name": dialog.name,
                            "text": message.text[:100] + "..." if len(message.text) > 100 else message.text
                        })
                        print(f"Found message: {message.text[:50]}...")
                        if len(results) >= limit:
                            break
                print(f"Found {message_count} matching messages in this chat")
                if len(results) >= limit:
                    break
            except Exception as e:
                print(f"Error searching in chat {dialog.name}: {e}")
                continue

        # Print results summary
        print("\n=== Search Results Summary ===")
        print(f"Total messages found: {len(results)}")
        for idx, result in enumerate(results, 1):
            print(f"\n{idx}. Message from {result['chat_name']}")
            print(f"Date: {result['date']}")
            print(f"Text: {result['text']}")
        print("=" * 30)

    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        await client.disconnect()
        print("\nTest completed. Client disconnected.")

if __name__ == "__main__":
    # Get query from command line if provided
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "склады"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    # Run the test
    asyncio.run(test_search(query, limit))
