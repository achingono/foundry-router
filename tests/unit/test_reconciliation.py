"""Unit tests for reconciliation loop behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from foundry_router.credit import InMemoryCreditStore
from foundry_router.reconciliation import ReconciliationLoop, StaticSettingsReconciliationProvider


def _settings_stub() -> object:
    settings = type("SettingsStub", (), {})()
    settings.backends = {"backend_a": {}}
    settings.backend_cycle_start_day = {"backend_a": 1}
    settings.backend_cycle_allowance_usd = {"backend_a": 100.0}
    settings.backend_initial_estimated_remaining_usd = {"backend_a": 100.0}
    settings.reconciliation_interval_minutes = 1
    settings.reconciliation_overrides_usd = {"backend_a": 25.0}
    return settings


class BrokenProvider:
    async def fetch_remaining_credit(self, _settings: object) -> dict[str, float]:
        raise RuntimeError("backend unavailable")


class StaticProvider:
    async def fetch_remaining_credit(self, settings: object) -> dict[str, float]:
        return dict(settings.reconciliation_overrides_usd)


class StubLogger:
    def info(self, *_args: object, **_kwargs: object) -> None:
        return None

    def warning(self, *_args: object, **_kwargs: object) -> None:
        return None


class BlockingProvider:
    async def fetch_remaining_credit(self, _settings: object) -> dict[str, float]:
        await asyncio.sleep(60)
        return {}


def test_reconciliation_run_once_applies_updates() -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    asyncio.run(store.sync_from_settings(settings))
    loop = ReconciliationLoop(
        provider=StaticProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )

    asyncio.run(loop.run_once())

    status = loop.status_snapshot()
    assert status["last_success_utc"] is not None
    assert status["last_error"] is None
    assert status["last_updated_backends"] == 1


def test_reconciliation_run_once_handles_provider_failure() -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    asyncio.run(store.sync_from_settings(settings))
    loop = ReconciliationLoop(
        provider=BrokenProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )

    asyncio.run(loop.run_once())

    status = loop.status_snapshot()
    assert status["last_success_utc"] is None
    assert status["last_error"] == "RuntimeError"
    assert status["consecutive_failures"] == 1
    assert status["stale"] is True


def test_static_settings_provider_reads_overrides() -> None:
    provider = StaticSettingsReconciliationProvider()
    settings = _settings_stub()
    balances = asyncio.run(provider.fetch_remaining_credit(settings))
    assert balances == {"backend_a": 25.0}


def test_status_not_stale_before_any_attempt() -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    loop = ReconciliationLoop(
        provider=StaticProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )

    status = loop.status_snapshot()
    assert status["last_attempt_utc"] is None
    assert status["stale"] is False


def test_status_stale_for_invalid_last_success_timestamp() -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    loop = ReconciliationLoop(
        provider=StaticProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )
    loop._status.last_success_utc = "not-an-iso-date"

    status = loop.status_snapshot()
    assert status["stale"] is True


def test_status_stale_for_old_success_and_not_stale_for_fresh_success() -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    loop = ReconciliationLoop(
        provider=StaticProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )

    old_success = (datetime.now(UTC) - timedelta(minutes=3)).isoformat()
    fresh_success = datetime.now(UTC).isoformat()

    loop._status.last_success_utc = old_success
    assert loop.status_snapshot()["stale"] is True

    loop._status.last_success_utc = fresh_success
    assert loop.status_snapshot()["stale"] is False


@pytest.mark.asyncio
async def test_start_is_non_blocking_and_stop_cleans_up() -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    await store.sync_from_settings(settings)
    loop = ReconciliationLoop(
        provider=BlockingProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )

    await asyncio.wait_for(loop.start(), timeout=0.1)
    assert loop._task is not None
    assert not loop._task.done()

    await loop.stop()
    assert loop._task is None


@pytest.mark.asyncio
async def test_run_loop_handles_timeout_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_stub()
    store = InMemoryCreditStore()
    await store.sync_from_settings(settings)
    loop = ReconciliationLoop(
        provider=StaticProvider(),
        credit_store=store,
        settings=settings,
        logger=StubLogger(),
    )

    calls: list[int] = []

    async def fake_run_once() -> None:
        calls.append(1)
        if len(calls) >= 2:
            loop._stop_event.set()

    async def fake_wait_for(_awaitable: object, **_kwargs: object) -> object:
        if hasattr(_awaitable, "close"):
            _awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(loop, "run_once", fake_run_once)
    monkeypatch.setattr("foundry_router.reconciliation.asyncio.wait_for", fake_wait_for)

    await loop._run()
    assert len(calls) == 2
