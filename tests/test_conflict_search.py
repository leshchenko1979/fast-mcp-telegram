from telethon import TelegramClient
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta, timezone

# Load environment variables
load_dotenv()

# Get credentials from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'mcp_telegram_search')

# Keywords that might indicate conflict or disagreement
CONFLICT_INDICATORS = [
    'не согласен', 'неправ', 'ошибаешься', 'спор', 'конфликт',
    'претензи', 'возражаю', 'неверно', 'нет, это не так',
    'категорически не', 'абсолютно не', 'неправда'
]

async def find_today_conflicts():
    print("\n=== Searching for Today's Conflicts ===")

    # Create and connect client
    print("\nConnecting to Telegram...")
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("Not authorized. Please run setup_telegram.py first")
        return

    print("Successfully connected!")

    try:
        # Get today's date in UTC
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        print(f"\nSearching for conflicts since {today_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        # Store potential conflicts
        conflicts = []

        # Get all dialogs
        async for dialog in client.iter_dialogs():
            try:
                print(f"\nChecking chat: {dialog.name}")

                # Get today's messages
                messages = []
                async for message in client.iter_messages(dialog, offset_date=today_start, reverse=True):
                    if message.text:
                        messages.append(message)

                if not messages:
                    continue

                print(f"Found {len(messages)} messages today")

                # Analyze messages for conflicts
                for i, message in enumerate(messages):
                    # Check if message contains conflict indicators
                    has_conflict = any(indicator.lower() in message.text.lower() for indicator in CONFLICT_INDICATORS)

                    # Check if message is a reply (might indicate discussion/argument)
                    is_reply = message.reply_to_msg_id is not None

                    if has_conflict or is_reply:
                        # Get context (previous and next messages)
                        context = []

                        # Add previous message if it's a reply
                        if is_reply:
                            try:
                                replied_msg = await client.get_messages(dialog, ids=message.reply_to_msg_id)
                                if replied_msg and replied_msg.date >= today_start:
                                    context.append({
                                        'text': replied_msg.text,
                                        'date': replied_msg.date.isoformat(),
                                        'from_id': str(replied_msg.from_id),
                                        'is_reply': False
                                    })
                            except Exception as e:
                                print(f"Couldn't get replied message: {e}")

                        # Add the current message
                        context.append({
                            'text': message.text,
                            'date': message.date.isoformat(),
                            'from_id': str(message.from_id),
                            'is_reply': is_reply
                        })

                        # Add next message if available
                        if i < len(messages) - 1:
                            next_msg = messages[i + 1]
                            if next_msg.reply_to_msg_id == message.id:
                                context.append({
                                    'text': next_msg.text,
                                    'date': next_msg.date.isoformat(),
                                    'from_id': str(next_msg.from_id),
                                    'is_reply': True
                                })

                        conflicts.append({
                            'chat_name': dialog.name,
                            'chat_id': dialog.id,
                            'messages': context,
                            'has_conflict_keywords': has_conflict
                        })

            except Exception as e:
                print(f"Error processing chat {dialog.name}: {e}")
                continue

        # Print results
        print("\n=== Potential Conflicts Found ===")
        print(f"Total potential conflicts: {len(conflicts)}")

        for i, conflict in enumerate(conflicts, 1):
            print(f"\n{i}. Chat: {conflict['chat_name']}")
            print("Messages:")
            for msg in conflict['messages']:
                print(f"  [{msg['date']}] {'(REPLY) ' if msg['is_reply'] else ''}{msg['text'][:100]}...")
            print(f"Has conflict keywords: {'Yes' if conflict['has_conflict_keywords'] else 'No (Reply thread)'}")
            print("-" * 50)

    except Exception as e:
        print(f"Error during search: {e}")
    finally:
        await client.disconnect()
        print("\nSearch completed. Client disconnected.")

if __name__ == "__main__":
    asyncio.run(find_today_conflicts())
