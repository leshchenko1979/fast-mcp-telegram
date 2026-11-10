"""
Shared benchmarking infrastructure for fast-mcp-telegram.

Provides scenario definition (BenchScenario), execution (ScenarioRunner),
and reporting (BenchReport, report_table, report_json).

Usage (standalone CLI via ``run_bench.py``)::

    uv run python3 -m tests.integration.run_bench --list-scenarios
    uv run python3 -m tests.integration.run_bench --only folder_flags
    uv run python3 -m tests.integration.run_bench --smoke --json results.json

Usage (pytest via ``test_bench_scenarios.py``)::

    pytest -m integration -k bench
    pytest -m integration -k bench_scenario_folder
"""

import asyncio
import json
import math
import statistics
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

# ══════════════════════════════════════════════════════════════════════════
# Data types
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class BenchScenario:
    """Configuration for a single benchmark scenario.

    The ``params`` dict is passed as ``**kwargs`` to the implementation
    function (``find_chats_impl`` or ``search_messages_impl``) together
    with a Telethon ``client`` as the first positional argument.

    ``smoke=True`` marks scenarios meant for quick validation (1 iteration).
    The CLI flag ``--smoke`` selects only these scenarios.
    """

    name: str
    tool: str  # "find_chats" or "search_messages"
    params: dict[str, Any] = field(default_factory=dict)
    iterations: int = 5
    timeout: float = (
        30.0  # reserved; not enforced by runner (asyncio.wait_for corrupts MTProto)
    )
    cooldown: float = 0.0
    smoke: bool = False
    description: str = ""


@dataclass
class BenchReport:
    """Aggregated report for one scenario across N iterations."""

    scenario: str
    ok: bool
    mean: float
    min: float
    max: float
    median: float
    p90: float
    n_iterations: int
    n_clean: int
    durations: list[float]
    results_counts: list[int]
    errors: list[str | None]
    config: dict[str, Any] = field(default_factory=dict)
    n_floodwait_exceeded: int = 0
    unreliable: bool = False


# ══════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════


class ScenarioRunner:
    """Runs benchmarks with warmup, iteration loops, and flood-wait retry."""

    def __init__(
        self,
        client: Any,
        impl_map: dict[str, Callable],
        *,
        floodwait_max_retry: int = 3,
        floodwait_cap: int = 60,
    ):
        self.client = client
        self.impl_map = impl_map
        self.floodwait_max_retry = floodwait_max_retry
        self.floodwait_cap = floodwait_cap

    async def warmup(self, practice_query: str = "test") -> None:
        """Warm up connection and API cache."""
        me = await self.client.get_me()
        print(f"Connected as: {me.first_name or ''} (@{me.username or '?'})")
        for tool in self.impl_map:
            try:
                result = await self.impl_map[tool](query=practice_query, limit=1)
                status = (
                    "OK"
                    if isinstance(result, dict) and "error" not in result
                    else str(result.get("error"))
                )
                print(f"  Warmup {tool}: {status}")
            except Exception as e:
                print(f"  Warmup {tool}: {e}")

    async def run_one(self, scenario: BenchScenario) -> BenchReport:
        """Execute a single scenario with warmup + timed iterations.

        On FloodWaitError ≤ cap: sleeps required time, retries the scenario.
        If a retry was needed, the iteration is SKIPPED from measurement.
        On FloodWaitError > cap or max retries exhausted: iteration is exceeded.
        """
        impl = self.impl_map.get(scenario.tool)
        if impl is None:
            return BenchReport(
                scenario=scenario.name,
                ok=False,
                mean=0,
                min=0,
                max=0,
                median=0,
                p90=0,
                n_iterations=0,
                n_clean=0,
                durations=[],
                results_counts=[],
                errors=[],
                config=asdict(scenario),
                unreliable=True,
            )

        n_iterations = 1 if scenario.smoke else max(1, scenario.iterations)
        durations: list[float] = []
        results_counts: list[int] = []
        errors: list[str | None] = []
        n_clean = 0
        n_floodwait_exceeded = 0

        print(
            f"  {scenario.name} ({n_iterations} iter{'s' if n_iterations > 1 else ''})"
        )

        for i in range(n_iterations):
            start = time.monotonic()
            error: str | None = None
            results_count = 0
            floodwait_retries = 0

            while True:
                try:
                    result = await impl(**scenario.params)
                    if isinstance(result, dict):
                        if "error" in result:
                            error = result["error"]
                        else:
                            results_count = len(
                                result.get("chats", result.get("messages", []))
                            )
                            if result.get("warning"):
                                print(
                                    f"    ⚠️  iter {i + 1} WARNING: {result['warning']}"
                                )
                    break
                except Exception as e:
                    cls_name = type(e).__name__
                    if "FloodWait" in cls_name:
                        floodwait_retries += 1
                        wait = getattr(e, "seconds", 30) + 1
                        if (
                            wait > self.floodwait_cap
                            or floodwait_retries > self.floodwait_max_retry
                        ):
                            error = (
                                f"FloodWaitExceeded:{wait - 1}s>cap:"
                                f"{self.floodwait_cap}s"
                            )
                            n_floodwait_exceeded += 1
                            print(f"    ⏳ iter {i + 1}: {error}")
                            break
                        print(
                            f"    ⏳ iter {i + 1}: FloodWait {wait - 1}s "
                            f"(retry {floodwait_retries})"
                        )
                        await asyncio.sleep(wait)
                        continue
                    error = f"{cls_name}: {e}"
                    break

            elapsed = time.monotonic() - start

            if floodwait_retries == 0:
                n_clean += 1
                durations.append(elapsed)
                results_counts.append(results_count)
                errors.append(error)
                status = error if error else f"{elapsed:.1f}s"
                print(f"    iter {i + 1}: {status} ({results_count} results)")
            else:
                print(
                    f"    iter {i + 1}: SKIPPED (FloodWait retries={floodwait_retries}, "
                    f"{elapsed:.1f}s wasted)"
                )

        if not durations:
            return BenchReport(
                scenario=scenario.name,
                ok=False,
                mean=0,
                min=0,
                max=0,
                median=0,
                p90=0,
                n_iterations=n_iterations,
                n_clean=n_clean,
                durations=[],
                results_counts=[],
                errors=errors,
                config=asdict(scenario),
                n_floodwait_exceeded=n_floodwait_exceeded,
                unreliable=(n_clean < n_iterations / 2),
            )

        ok = all(e is None for e in errors)
        return BenchReport(
            scenario=scenario.name,
            ok=ok,
            mean=statistics.mean(durations),
            min=min(durations),
            max=max(durations),
            median=statistics.median(durations),
            p90=_p90(durations),
            n_iterations=n_iterations,
            n_clean=n_clean,
            durations=durations,
            results_counts=results_counts,
            errors=errors,
            config=asdict(scenario),
            n_floodwait_exceeded=n_floodwait_exceeded,
            unreliable=(n_clean < n_iterations / 2),
        )

    async def run_many(self, scenarios: list[BenchScenario]) -> list[BenchReport]:
        """Run multiple scenarios sequentially."""
        reports = []
        for s in scenarios:
            r = await self.run_one(s)
            reports.append(r)
            if s.cooldown > 0:
                await asyncio.sleep(s.cooldown)
        return reports


# ══════════════════════════════════════════════════════════════════════════
# Reporting
# ══════════════════════════════════════════════════════════════════════════


def report_table(reports: list[BenchReport]) -> str:
    """ASCII table of benchmark results."""
    lines = [
        f"{'Scenario':30s} {'Mean':>8s} {'Min':>8s} {'Max':>8s} "
        f"{'P90':>8s} {'Results':>7s} {'Clean':>6s} {'Status':>10s}",
        "-" * 88,
    ]
    for r in reports:
        ok = "✅" if r.ok else "⚠️"
        if r.unreliable:
            ok = "⚠️UNCLEAN"
        elif r.n_floodwait_exceeded > 0:
            ok = "⚠️FLOOD"
        lines.append(
            f"{r.scenario:30s} {r.mean:>7.3f}s {r.min:>7.3f}s {r.max:>7.3f}s "
            f"{r.p90:>7.3f}s "
            f"{max(r.results_counts) if r.results_counts else 0:>7d} "
            f"{r.n_clean:>3d}/{r.n_iterations:>3d} {ok:>10s}"
        )
    lines.append("")
    return "\n".join(lines)


def report_json(reports: list[BenchReport], path: str | None = None) -> str:
    """JSON-serialized benchmark results. Optionally writes to file.

    Omitted from output: raw ``durations`` and ``results_counts`` lists
    to keep the payload concise.
    """
    data = []
    for r in reports:
        d = asdict(r)
        d.pop("durations", None)
        d.pop("results_counts", None)
        data.append(d)
    payload = {"reports": data}
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if path:
        with open(path, "w") as f:
            f.write(text)
    return text


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════


def _p90(values: list[float]) -> float:
    """90th percentile — float index; for small N returns the max."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(math.ceil(0.90 * len(s)) - 1, len(s) - 1)
    return s[max(0, idx)]


async def with_flood_retry(fn: Callable, *, max_retries: int = 3, cap: int = 60) -> Any:
    """Execute ``fn()``, retrying on ``FloodWaitError`` up to ``max_retries`` times.

    Telethon import is deferred to keep module-load free of mandatory deps.
    """
    from telethon.errors import FloodWaitError

    for attempt in range(max_retries):
        try:
            return await fn()
        except FloodWaitError as e:
            wait = e.seconds + 1
            if wait > cap or attempt == max_retries - 1:
                raise
            await asyncio.sleep(wait)
    raise RuntimeError("flood retry exhausted")  # pragma: no cover
