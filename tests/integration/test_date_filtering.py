#!/usr/bin/env python3
"""Integration tests for get_messages date filtering.

Run with: uv run python3 tests/integration/test_date_filtering.py
"""
import asyncio
from datetime import datetime, timezone
from src.client.connection import get_connected_client
from src.tools.search import search_messages_impl


async def run_date_filtering_test():
    """Test min_date/max_date filtering for per-chat search."""
    print("\n" + "=" * 60)
    print("Testing get_messages date filtering")
    print("=" * 60)

    # Find a chat with some history
    client = await get_connected_client()
    me = await client.get_me()
    print(f"Connected as: {me.first_name} {me.last_name or ''} (@{me.username})")

    # Get recent dialogs to find a chat with messages
    print("\nFinding a chat with message history...")
    test_chat_id = None
    test_chat_title = None

    async for dialog in client.iter_dialogs(limit=50):
        entity = getattr(dialog, "entity", None)
        if not entity:
            continue
        # Find a chat that has messages (not just a contact)
        if hasattr(entity, "username") and entity.username:
            test_chat_id = str(entity.id)
            test_chat_title = getattr(entity, "title", None) or getattr(entity, "first_name", "Unknown")
            print(f"Selected chat: {test_chat_title} (id={test_chat_id})")
            break

    if not test_chat_id:
        print("ERROR: No suitable chat found for testing")
        return

    # Test 1: Browse without date filter
    print("\n--- Test 1: Browse chat (no date filter) ---")
    result = await search_messages_impl(chat_id=test_chat_id, limit=10)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        msgs = result.get("messages", [])
        print(f"Found {len(msgs)} messages")
        for m in msgs[:3]:
            print(f"  [{m.get('id')}] {m.get('date')} - {m.get('text', '')[:50]}")
        if msgs:
            latest_date = msgs[0].get("date") if msgs else None
            oldest_date = msgs[-1].get("date") if msgs else None
            print(f"  Date range in results: {oldest_date} to {latest_date}")

    # Test 2: Browse with min_date (recent messages only)
    print("\n--- Test 2: Browse with min_date=2024-01-01 ---")
    result = await search_messages_impl(
        chat_id=test_chat_id,
        min_date="2024-01-01",
        limit=10
    )
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        msgs = result.get("messages", [])
        print(f"Found {len(msgs)} messages")
        for m in msgs[:3]:
            print(f"  [{m.get('id')}] {m.get('date')} - {m.get('text', '')[:50]}")
        if msgs:
            latest_date = msgs[0].get("date") if msgs else None
            oldest_date = msgs[-1].get("date") if msgs else None
            print(f"  Date range in results: {oldest_date} to {latest_date}")

    # Test 3: Browse with max_date (old messages only)
    print("\n--- Test 3: Browse with max_date=2023-01-01 ---")
    result = await search_messages_impl(
        chat_id=test_chat_id,
        max_date="2023-01-01",
        limit=10
    )
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        msgs = result.get("messages", [])
        print(f"Found {len(msgs)} messages")
        for m in msgs[:3]:
            print(f"  [{m.get('id')}] {m.get('date')} - {m.get('text', '')[:50]}")
        if msgs:
            latest_date = msgs[0].get("date") if msgs else None
            oldest_date = msgs[-1].get("date") if msgs else None
            print(f"  Date range in results: {oldest_date} to {latest_date}")

    # Test 4: Search with date filter
    print("\n--- Test 4: Search with min_date ---")
    # Try to search for something common that might exist
    result = await search_messages_impl(
        chat_id=test_chat_id,
        query="the",
        min_date="2024-01-01",
        limit=10
    )
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        msgs = result.get("messages", [])
        print(f"Found {len(msgs)} messages")
        for m in msgs[:3]:
            print(f"  [{m.get('id')}] {m.get('date')} - {m.get('text', '')[:50]}")

    # Test 5: Date filter with message_ids mode (should error)
    print("\n--- Test 5: message_ids mode with date filter (should error) ---")
    # Get a message ID first
    if msgs:
        msg_id = msgs[0].get("id")
        result = await search_messages_impl(
            chat_id=test_chat_id,
            message_ids=[msg_id],
            min_date="2024-01-01"
        )
        if "error" in result:
            print(f"CORRECTLY ERRORED: {result['error']}")
        else:
            print(f"BUG: Should have errored but got: {result}")

    print("\n" + "=" * 60)
    print("Date filtering tests completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_date_filtering_test())
