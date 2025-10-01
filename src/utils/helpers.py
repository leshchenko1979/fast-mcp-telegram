from importlib import import_module
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


def normalize_method_name(method: str) -> str:
    """Normalize method to telethon.tl.functions path (case-insensitive).

    Returns "module.Class" where Class excludes the trailing "Request".
    """
    if not method or "." not in method:
        raise ValueError(
            "Method must include module and class, e.g., 'messages.GetHistory'"
        )

    module, cls = method.split(".", 1)
    module = module.strip().lower()
    cls = cls.strip()

    if cls.endswith("Request"):
        cls = cls[: -len("Request")]

    # Try to resolve real Telethon Request class by case-insensitive match
    # Build and cache a lowercase->BaseName map per module for efficiency
    base_name = _resolve_request_base_name_case_insensitive(module, cls)
    if base_name:
        return f"{module}.{base_name}"

    # Preserve caller's casing if it includes uppercase; otherwise capitalize first letter
    if not any(ch.isupper() for ch in cls):
        cls = cls.capitalize()
    return f"{module}.{cls}"


# -------------------------
# Internal helpers (cached)
# -------------------------

_TELETHON_FUNCS_CACHE: dict[str, dict[str, str]] = {}


def _get_functions_map_for_module(module: str) -> dict[str, str]:
    """Return a cached map: lower(BaseName) -> BaseName for Telethon functions in module."""
    cached = _TELETHON_FUNCS_CACHE.get(module)
    if cached is not None:
        return cached

    mapping: dict[str, str] = {}
    try:
        tl_module = import_module(f"telethon.tl.functions.{module}")
        for attr in dir(tl_module):
            if not attr.endswith("Request"):
                continue
            base = attr[: -len("Request")]
            mapping[base.lower()] = base
    except Exception:
        # If Telethon is unavailable or module not found, leave mapping empty
        mapping = {}

    _TELETHON_FUNCS_CACHE[module] = mapping
    return mapping


def _resolve_request_base_name_case_insensitive(module: str, cls: str) -> str | None:
    """Resolve class base name (without Request) in a case-insensitive manner using cache.

    Returns the canonical BaseName if found, otherwise None.
    """
    mapping = _get_functions_map_for_module(module)
    return mapping.get(cls.lower())
