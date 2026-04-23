#!/usr/bin/env python3
"""Integration tests for find_chats date filtering.

Run with: uv run python3 tests/integration/test_find_chats_date_filtering.py
"""
import asyncio
from src.client.connection import get_connected_client
from src.tools.contacts import find_chats_impl


async def run_find_chats_date_filtering_test():
    """Test min_date/max_date filtering for find_chats."""
    print("\n" + "=" * 60)
    print("Testing find_chats date filtering")
    print("=" * 60)

    client = await get_connected_client()
    me = await client.get_me()
    print(f"Connected as: {me.first_name} {me.last_name or ''} (@{me.username})")

    # Get dialogs to find some chats with different activity dates
    print("\nFetching dialogs to analyze date range...")
    dialogs_info = []
    async for dialog in client.iter_dialogs(limit=50):
        entity = getattr(dialog, "entity", None)
        if not entity:
            continue
        eid = getattr(entity, "id", None)
        title = getattr(entity, "title", None) or getattr(entity, "first_name", "Unknown")
        dialog_date = getattr(dialog, "date", None)
        if eid and dialog_date:
            dialogs_info.append({
                "id": eid,
                "title": title,
                "date": dialog_date,
            })

    if not dialogs_info:
        print("ERROR: No dialogs found")
        return

    # Sort by date descending to find recent and old chats
    dialogs_info.sort(key=lambda x: x["date"], reverse=True)

    print(f"\nFound {len(dialogs_info)} dialogs with dates")
    print(f"Most recent: {dialogs_info[0]['title']} ({dialogs_info[0]['date'].isoformat()})")
    print(f"Oldest: {dialogs_info[-1]['title']} ({dialogs_info[-1]['date'].isoformat()})")

    # Test 1: Browse without date filter
    print("\n--- Test 1: find_chats without date filter ---")
    result = await find_chats_impl(query=None, limit=10)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        chats = result.get("chats", [])
        print(f"Found {len(chats)} chats")
        for c in chats[:5]:
            date = c.get("last_activity_date", "N/A")
            print(f"  [{c.get('id')}] {c.get('title') or c.get('first_name', 'Unknown')} - {date}")

    # Test 2: find_chats with min_date (Moscow time today = 2026-04-23 UTC)
    print("\n--- Test 2: find_chats with min_date=2026-04-23 ---")
    # Moscow is UTC+3, so today in Moscow (2026-04-24) is 2026-04-23 00:00 UTC
    print("Using min_date=2026-04-23 UTC (which is 2026-04-24 Moscow time)")
    result = await find_chats_impl(query=None, limit=50, min_date="2026-04-23")
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        chats = result.get("chats", [])
        print(f"Found {len(chats)} chats")
        for c in chats[:10]:
            date = c.get("last_activity_date", "N/A")
            print(f"  [{c.get('id')}] {c.get('title') or c.get('first_name', 'Unknown')} - last_activity: {date}")

    # Test 3: find_chats with max_date (old only)
    print("\n--- Test 3: find_chats with max_date ---")
    # Use the oldest date to get only very old chats
    old_date = dialogs_info[-1]["date"].isoformat()[:10]
    print(f"Using max_date={old_date} (oldest dialog)")
    result = await find_chats_impl(query=None, limit=50, max_date=old_date)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        chats = result.get("chats", [])
        print(f"Found {len(chats)} chats")
        for c in chats[:5]:
            date = c.get("last_activity_date", "N/A")
            print(f"  [{c.get('id')}] {c.get('title') or c.get('first_name', 'Unknown')} - last_activity: {date}")

    # Test 4: find_chats with both min and max date
    print("\n--- Test 4: find_chats with date range ---")
    old_date = dialogs_info[-1]["date"].isoformat()[:10]
    recent_date = dialogs_info[0]["date"].isoformat()[:10]
    print(f"Using min_date={old_date}, max_date={recent_date}")
    result = await find_chats_impl(query=None, limit=50, min_date=old_date, max_date=recent_date)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        chats = result.get("chats", [])
        print(f"Found {len(chats)} chats")

    # Test 5: find_chats with filter "Без каналов" and min_date
    print("\n--- Test 5: find_chats with filter='Без каналов' and min_date ---")
    result = await find_chats_impl(query=None, limit=20, filter="Без каналов", min_date="2026-04-23")
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        chats = result.get("chats", [])
        print(f"Found {len(chats)} chats")
        for c in chats[:10]:
            date = c.get("last_activity_date", "N/A")
            ctype = c.get("type", "unknown")
            print(f"  [{c.get('id')}] {c.get('title') or c.get('first_name', 'Unknown')} ({ctype}) - last_activity: {date}")

    # Test 6: Invalid date format
    print("\n--- Test 6: Invalid min_date format (should error) ---")
    result = await find_chats_impl(query=None, limit=10, min_date="not-a-date")
    if "error" in result:
        print(f"CORRECTLY ERRORED: {result['error']}")
    else:
        print(f"BUG: Should have errored but got: {result}")

    print("\n" + "=" * 60)
    print("find_chats date filtering tests completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_find_chats_date_filtering_test())
