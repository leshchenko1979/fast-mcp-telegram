#!/usr/bin/env python3
"""Integration tests for find_chats filter functionality.

Run with: uv run python3 tests/integration/test_filter_resolution.py
"""
import asyncio
import sys
from src.client.connection import get_connected_client
from src.tools.contacts import _get_filter_by_name, _filter_matches_flags
from src.utils.entity import build_entity_dict


async def get_filter_info(client, filter_name: str) -> dict:
    """Get filter definition and stats."""
    filter_dict = await _get_filter_by_name(client, filter_name)
    if not filter_dict:
        return {"error": f"Filter '{filter_name}' not found"}

    include_peers = filter_dict.get("include_peers", []) or []
    exclude_peers = filter_dict.get("exclude_peers", []) or []

    return {
        "name": filter_name,
        "include_peers_count": len(include_peers),
        "exclude_peers_count": len(exclude_peers),
        "flags": {
            "contacts": filter_dict.get("contacts", False),
            "non_contacts": filter_dict.get("non_contacts", False),
            "groups": filter_dict.get("groups", False),
            "broadcasts": filter_dict.get("broadcasts", False),
            "bots": filter_dict.get("bots", False),
            "exclude_muted": filter_dict.get("exclude_muted", False),
            "exclude_read": filter_dict.get("exclude_read", False),
            "exclude_archived": filter_dict.get("exclude_archived", False),
        }
    }


async def resolve_include_peers(client, filter_dict: dict) -> list[dict]:
    """Resolve include_peers to entity dicts."""
    results = []
    for inp in filter_dict.get("include_peers", []) or []:
        try:
            entity = await client.get_entity(inp)
            ed = build_entity_dict(entity)
            if ed:
                results.append(ed)
        except Exception as e:
            results.append({"error": str(e), "peer": str(inp)})
    return results


async def count_matching_dialogs(client, filter_dict: dict, limit: int = 500) -> tuple[int, list[tuple[dict, object]]]:
    """Count dialogs matching filter flags and return first N results with dialogs for verification."""
    matched = []
    async for dialog in client.iter_dialogs(limit=limit):
        entity = getattr(dialog, "entity", None)
        if not entity:
            continue
        if _filter_matches_flags(entity, dialog, filter_dict):
            entity_dict = build_entity_dict(entity)
            if entity_dict:
                matched.append((entity_dict, dialog))

    return len(matched), matched[:10]


async def main():
    client = await get_connected_client()

    filters_to_test = ["Без каналов", "Ответить", "Каналы"]

    for name in filters_to_test:
        print(f"\n{'='*60}")
        print(f"Testing filter: {name}")
        print('='*60)

        filter_info = await get_filter_info(client, name)
        if "error" in filter_info:
            print(f"ERROR: {filter_info['error']}")
            continue

        print(f"\nFilter definition:")
        print(f"  Include peers: {filter_info['include_peers_count']}")
        print(f"  Exclude peers: {filter_info['exclude_peers_count']}")
        print(f"  Flags: {filter_info['flags']}")

        # Get filter for further testing
        filter_dict = await _get_filter_by_name(client, name)

        # Test include_peers resolution
        if filter_info["include_peers_count"] > 0:
            print(f"\nResolving {filter_info['include_peers_count']} include_peers...")
            peers = await resolve_include_peers(client, filter_dict)
            type_counts = {}
            for p in peers:
                t = p.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
            print(f"  Resolved types: {type_counts}")
            for i, p in enumerate(peers[:5]):
                print(f"    {i+1}. {p.get('type')}: {p.get('title') or p.get('first_name', 'N/A')} (id={p.get('id')})")

        # Test flag matching
        print(f"\nFlag matching (checking first 500 dialogs)...")
        count, sample = await count_matching_dialogs(client, filter_dict)
        print(f"  Total matching: {count}")
        if sample:
            print(f"  Sample (first 5):")
            for i, (e, dialog) in enumerate(sample[:5]):
                print(f"    {i+1}. {e.get('type')}: {e.get('title') or e.get('first_name', 'N/A')} (id={e.get('id')})")

        # Verify each sample complies with filter flags (but not include_peers/exclude_peers)
        print(f"\n  Verifying {len(sample)} sample chats comply with filter flags...")
        flag_failures = []
        for entity_dict, dialog in sample:
            entity = dialog.entity
            if not _filter_matches_flags(entity, dialog, filter_dict):
                flag_failures.append(entity_dict)

        if flag_failures:
            print(f"  FLAGS VERIFICATION FAILED: {len(flag_failures)} chats do not comply with filter flags:")
            for e in flag_failures:
                print(f"    - {e.get('type')}: {e.get('title') or e.get('first_name', 'N/A')} (id={e.get('id')})")
        else:
            print(f"  Flags verification passed: all {len(sample)} sample chats comply with filter flags.")

        # Verify exclude_peers compliance
        exclude_peers = filter_dict.get("exclude_peers", []) or []
        if exclude_peers:
            exclude_ids = set()
            for ep in exclude_peers:
                try:
                    ent = await client.get_entity(ep)
                    exclude_ids.add(getattr(ent, "id", None))
                except Exception:
                    pass

            peer_failures = [e for e, _ in sample if e.get("id") in exclude_ids]
            if peer_failures:
                print(f"  EXCLUDE_PEERS VERIFICATION FAILED: {len(peer_failures)} chats are in exclude_peers:")
                for e in peer_failures:
                    print(f"    - {e.get('type')}: {e.get('title') or e.get('first_name', 'N/A')} (id={e.get('id')})")
            else:
                print(f"  Exclude peers verification passed: no sample chats are in exclude_peers.")

    print(f"\n{'='*60}")
    print("All filter tests completed")
    print('='*60)


if __name__ == "__main__":
    asyncio.run(main())
