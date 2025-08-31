from typing import Any


def _append_dedup_until_limit(
    collected: list[dict[str, Any]],
    seen_keys: set,
    new_messages: list[dict[str, Any]],
    target_total: int,
) -> None:
    """Append messages into collected with deduplication until target_total is reached.

    Deduplicates by (chat.id, message.id) pair.
    """
    for msg in new_messages:
        key = (msg.get("chat", {}).get("id"), msg.get("id"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        collected.append(msg)
        if len(collected) >= target_total:
            break
