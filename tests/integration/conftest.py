"""
Integration test fixtures for benchmark scenarios.

Provides a module-scoped ``telethon_client`` fixture shared across
all parametrized benchmark test cases.
"""

import sys
from pathlib import Path

import pytest_asyncio

# ── Ensure src is importable ──────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Protect sys.argv from fastmcp's import-time arg parsing ──────────────
_saved_argv = sys.argv[:]
sys.argv = [sys.argv[0] if sys.argv else "conftest"]
try:
    from src.client.connection import get_connected_client
finally:
    sys.argv = _saved_argv


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def telethon_client():
    """Module-scoped Telethon client for integration benchmarks.

    Created once per test module and disconnected after all tests finish.

    ``loop_scope="module"`` must match the tests' own loop scope: the cached
    client carries asyncio locks and a sqlite session, all bound to the loop
    that created them, so running the tests on a fresh per-function loop
    raises "bound to a different event loop" and then "database is locked".
    """
    client = await get_connected_client()
    me = await client.get_me()
    print(f"Connected as: {me.first_name or ''} (@{me.username or '?'})")
    yield client
    await client.disconnect()
