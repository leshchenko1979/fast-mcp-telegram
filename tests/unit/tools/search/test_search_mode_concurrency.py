"""Tests for concurrency control in search_mode.py."""

import asyncio

import pytest

from src.tools.search.search_mode import _run_with_limits


class TestDefaultConcurrency:
    """Test _DEFAULT_MAX_CONCURRENT constant."""

    def test_default_value(self):
        from src.tools.search.search_mode import _DEFAULT_MAX_CONCURRENT

        assert _DEFAULT_MAX_CONCURRENT == 2


class TestRunWithLimits:
    """Test the _run_with_limits wrapper function."""

    @pytest.mark.asyncio
    async def test_runs_without_semaphore(self):
        """Coroutine executes directly when semaphore is None."""
        executed = False

        async def coro():
            nonlocal executed
            executed = True
            return "result"

        result = await _run_with_limits(coro(), semaphore=None)
        assert result == "result"
        assert executed

    @pytest.mark.asyncio
    async def test_runs_with_semaphore(self):
        """Coroutine executes under semaphore when one is provided."""
        executed = False

        async def coro():
            nonlocal executed
            executed = True
            return "result"

        semaphore = asyncio.Semaphore(2)
        result = await _run_with_limits(coro(), semaphore=semaphore)
        assert result == "result"
        assert executed

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Semaphore with value 2 allows at most 2 concurrent executions."""
        semaphore = asyncio.Semaphore(2)
        counter = 0
        max_concurrent = 0

        async def track_concurrent():
            nonlocal counter, max_concurrent
            counter += 1
            max_concurrent = max(max_concurrent, counter)
            await asyncio.sleep(0.05)
            counter -= 1
            return "done"

        coros = [
            _run_with_limits(track_concurrent(), semaphore=semaphore) for _ in range(20)
        ]
        await asyncio.gather(*coros)
        assert max_concurrent <= 2, f"Expected max 2 concurrent, got {max_concurrent}"
