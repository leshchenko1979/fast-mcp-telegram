"""
Unified scenario definitions for the bench harness.

All scenarios are ``BenchScenario`` instances consumed by both
``run_bench.py`` (standalone CLI) and ``test_bench_scenarios.py`` (pytest).

Design rules
------------
* Every scenario is just data — a ``tool`` name and a ``params`` dict.
  No embedded logic, no closures.
* The runner (``ScenarioRunner``) calls ``impl_map[tool](**params)``.  The
  tool impls resolve their own client via ``get_connected_client()``; the
  runner keeps a client only for its own warmup and identity check.
* Assertion scenarios (dedup, fairness, partial) are **not** here — they
  are correctness tests better suited to ``pytest`` assertions, not
  performance benchmarks.
* Folder-related scenarios hard-code ``folder="Без каналов"`` (the
  operator's known folder name).  Override via CLI flag or edit this file.
* Date scenarios use static dates for reproducibility.  Run via CLI
  with ``--param min_date=...`` to adjust.
"""

from bench_core import BenchScenario

# ── Helper ──────────────────────────────────────────────────────────────────


def _fc(**params) -> dict:
    """Shorthand for a find_chats scenario params dict."""
    return {"tool": "find_chats", "params": params}


def _sm(**params) -> dict:
    """Shorthand for a search_messages scenario params dict."""
    return {"tool": "search_messages", "params": params}


# ── find_chats scenarios ────────────────────────────────────────────────────
# Code paths: global (single/multi), date (browse/search), folder (include/flags)

FIND_CHATS_SCENARIOS: list[BenchScenario] = [
    BenchScenario(
        name="global_single",
        description="Single-term global Telegram search (query='alexey').",
        smoke=True,
        **_fc(query="alexey", limit=10),
    ),
    BenchScenario(
        name="global_multi",
        description=(
            "Multi-term global search — the P0 optimisation target "
            "(query='alexey,test,bot')."
        ),
        iterations=5,
        **_fc(query="alexey,test,bot", limit=10),
    ),
    BenchScenario(
        name="date_browse",
        description=(
            "Browse chats with min_date — triggers the iter_dialogs + "
            "GetPeerDialogs fallback path (query=None, min_date=2024-01-01)."
        ),
        iterations=5,
        smoke=True,
        **_fc(query=None, limit=20, min_date="2024-01-01"),
    ),
    BenchScenario(
        name="date_search",
        description=(
            "Search with date filter and query — triggers iter_dialogs "
            "with a query fallback (query='alex', max_date=2024-06-01)."
        ),
        iterations=5,
        **_fc(query="alex", limit=10, max_date="2024-06-01"),
    ),
    BenchScenario(
        name="folder_include",
        description=(
            "Folder with include_peers — the GetPeerDialogs path "
            "(folder='Без каналов')."
        ),
        iterations=5,
        **_fc(query=None, limit=20, folder="Без каналов"),
    ),
    BenchScenario(
        name="folder_flags",
        description=(
            "Folder with flag-based filtering — the iter_dialogs + flags path "
            "(folder='Без каналов')."
        ),
        iterations=5,
        smoke=True,
        **_fc(query=None, limit=10, folder="Без каналов"),
    ),
    BenchScenario(
        name="folder_flags_date",
        description=(
            "Folder with flags + date — the v0.28.2 fix target "
            "(folder='Без каналов', min_date=2024-01-01).  Before the fix "
            "this took ~39s, after the fix ~6.9s."
        ),
        iterations=5,
        smoke=True,
        **_fc(query=None, limit=20, folder="Без каналов", min_date="2024-01-01"),
    ),
]

# ── search_messages scenarios ───────────────────────────────────────────────

SEARCH_SCENARIOS: list[BenchScenario] = [
    BenchScenario(
        name="baseline",
        description="Unlikely term (query='__z__') to measure baseline overhead.",
        iterations=3,
        **_sm(query="__z__", limit=1),
    ),
    BenchScenario(
        name="single_term",
        description="Single-term search (query='недвижимость').",
        iterations=5,
        smoke=True,
        **_sm(query="недвижимость", limit=10),
    ),
    BenchScenario(
        name="two_terms",
        description="Two-term search (query='недвижимость, инвестиции').",
        iterations=5,
        **_sm(query="недвижимость, инвестиции", limit=10),
    ),
    BenchScenario(
        name="three_terms",
        description="Three-term search (query='недвижимость, инвестиции, сделка').",
        iterations=5,
        **_sm(query="недвижимость, инвестиции, сделка", limit=10),
    ),
    BenchScenario(
        name="five_terms",
        description="Five-term search — the P1 optimisation target.",
        iterations=5,
        **_sm(
            query="недвижимость, инвестиции, объект, проект, сделка",
            limit=10,
        ),
    ),
    BenchScenario(
        name="three_terms_large",
        description="Three-term search with large result set (limit=50).",
        iterations=5,
        **_sm(query="недвижимость, инвестиции, сделка", limit=50),
    ),
]

# ── Combined index ──────────────────────────────────────────────────────────

BY_TOOL: dict[str, list[BenchScenario]] = {
    "find_chats": FIND_CHATS_SCENARIOS,
    "search_messages": SEARCH_SCENARIOS,
}


def get_scenarios(
    tool: str | None = None,
    pattern: str | None = None,
    smoke_only: bool = False,
) -> list[BenchScenario]:
    """Resolve which scenarios to run based on CLI flags.

    Parameters
    ----------
    tool:
        ``"find_chats"``, ``"search_messages"``, or ``None`` for all.
    pattern:
        Optional substring or simple pattern to filter scenario names.
    smoke_only:
        If true, return only scenarios with ``smoke=True``.

    Returns
    -------
    List of matching scenarios (sorted by tool, then by definition order).
    """
    result: list[BenchScenario] = []
    for t, scenarios in BY_TOOL.items():
        if tool is not None and t != tool:
            continue
        for s in scenarios:
            if smoke_only and not s.smoke:
                continue
            if pattern and pattern not in s.name:
                continue
            result.append(s)
    return result


def list_scenarios() -> str:
    """Formatted table for ``--list-scenarios``."""
    lines = [
        f"{'Name':30s} {'Tool':20s} {'Smoke':>6s} {'Iter':>5s} {'Description':s}",
        "-" * 120,
    ]
    for s in get_scenarios():
        lines.append(
            f"{s.name:30s} {s.tool:20s} {'✓' if s.smoke else '':>6s} "
            f"{s.iterations if not s.smoke else 1:>5d} {s.description}"
        )
    lines.append("")
    return "\n".join(lines)
