"""Shared test isolation for process-global routing state.

The combination-exclusion store is intentionally persistent in production
(memory-backed, single replica). Its 30-minute windows never expire inside a
test session, so any test exercising the main-module execution paths would
otherwise observe other tests' exclusions — including across files that share
``main.app`` globals. Resetting here keeps each test's routing view independent
without changing production semantics.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _reset_combination_exclusion_state():
    from foundry_router.main import _exclusion_store, _metrics_store

    asyncio.run(_exclusion_store.reset())
    asyncio.run(_metrics_store.reset())
    yield
    asyncio.run(_exclusion_store.reset())
    asyncio.run(_metrics_store.reset())
