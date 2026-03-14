"""
Utilities for bridging synchronous and asynchronous code.

The shopping agent codebase is entirely synchronous, but browser-use requires async/await.
These utilities allow calling async browser-use from sync code without refactoring the entire application.
"""

import asyncio
from typing import Any, List


def run_async(coro) -> Any:
    """
    Run an async coroutine from synchronous code.

    Args:
        coro: An async coroutine to run

    Returns:
        The result of the coroutine

    Raises:
        RuntimeError: If called from an async context
    """
    try:
        loop = asyncio.get_running_loop()
        raise RuntimeError(
            "run_async called from async context - use await directly instead"
        )
    except RuntimeError:
        # No running loop - safe to create a new one
        return asyncio.run(coro)


def run_async_parallel(coros: List) -> List:
    """
    Run multiple async coroutines in parallel, handling exceptions gracefully.

    Args:
        coros: List of async coroutines to run concurrently

    Returns:
        List of results (successful results or Exception objects for failures)
    """

    async def gather_all():
        return await asyncio.gather(*coros, return_exceptions=True)

    return run_async(gather_all())
