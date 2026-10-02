"""Phase 11: store factory, readiness checks, and D6 effective-limit contract."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import foundry_router.main as main_module
from foundry_router.main import _extra_readiness_checks, build_stores
from foundry_router.ratelimit import InMemoryRateLimitStore, effective_quota_limits
from foundry_router.state.table import AzureTableCreditStore, AzureTableHealthStore


def _memory_settings(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "state_backend": "memory",
        "quota_group_rate_limits": {},
        "rate_limit_replica_share": 1,
        "backends": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_stores_memory_returns_singletons() -> None:
    settings = _memory_settings()
    health, credit, rate_limit, clients = build_stores(settings)
    assert health is main_module._health_store
    assert credit is main_module._credit_store
    assert rate_limit is main_module._rate_limit_store
    assert clients == ()


def test_build_stores_table_returns_shared_table_stores() -> None:
    settings = SimpleNamespace(
        state_backend="table",
        table_endpoint="https://placeholder.table.core.windows.net",
        table_health_name="routerhealth",
        table_credit_name="routercredit",
        table_request_timeout_seconds=5.0,
    )
    health, credit, rate_limit, clients = build_stores(settings)
    assert isinstance(health, AzureTableHealthStore)
    assert isinstance(credit, AzureTableCreditStore)
    assert isinstance(rate_limit, InMemoryRateLimitStore)
    assert len(clients) == 2


def test_effective_quota_limits_floors_each_dimension() -> None:
    raw = {"g1": {"rpm": 10, "tpm": 101, "rpd": 3}}
    assert effective_quota_limits(raw, 2) == {"g1": {"rpm": 5, "tpm": 50, "rpd": 1}}
    assert effective_quota_limits(raw, 1) == raw


@pytest.mark.asyncio
async def test_rate_limit_sync_applies_replica_share() -> None:
    store = InMemoryRateLimitStore()
    settings = SimpleNamespace(
        quota_group_rate_limits={"g1": {"rpm": 10}},
        reservation_max_age_seconds=900.0,
        rate_limit_replica_share=2,
    )
    await store.sync_from_settings(settings)
    assert store.quota_limits == {"g1": {"rpm": 5}}


@pytest.mark.asyncio
async def test_routing_resync_keeps_per_replica_share(monkeypatch) -> None:
    """Repeated routing calls must not revert the scaled store limits."""
    from foundry_router.health import BackendHealthSnapshot, BackendHealthState
    from foundry_router.routing import select_candidate_backend

    settings = SimpleNamespace(
        models={"m": SimpleNamespace(backends={"b1": 1.0})},
        backends={"b1": SimpleNamespace(credit_metered=False, quota_group="g1")},
        pricing={"m": SimpleNamespace(input_per_million=1.0, output_per_million=1.0)},
        quota_group_rate_limits={"g1": {"rpm": 10}},
        rate_limit_replica_share=2,
        min_credit_reserve_usd=0.0,
        min_credit_reserve_percent=0.0,
        reservation_max_age_seconds=900.0,
        protected_emergency_fallback=False,
    )
    store = InMemoryRateLimitStore()
    await store.sync_from_settings(settings)
    assert store.quota_limits == {"g1": {"rpm": 5}}

    class Health:
        async def snapshot_backend_health(self, ids):
            return {i: BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0) for i in ids}

    class Credit:
        async def sync_from_settings(self, s):
            return None

        async def finalize_request(self, *a, **k):
            return None

    class Logger:
        def info(self, *a, **k):
            return None

        def debug(self, *a, **k):
            return None

        def warning(self, *a, **k):
            return None

    for i in range(3):
        await select_candidate_backend(
            settings,
            "m",
            operation="responses",
            body={"input": "hi"},
            request_id=f"req-{i}",
            health_store=Health(),
            credit_store=Credit(),
            logger=Logger(),
            rate_limit_store=store,
        )
    assert store.quota_limits == {"g1": {"rpm": 5}}


@pytest.mark.asyncio
async def test_readiness_zero_share_fails(monkeypatch) -> None:
    settings = _memory_settings(
        quota_group_rate_limits={"g1": {"rpm": 1}},
        rate_limit_replica_share=2,
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    main_module._state_probe_cache.update(at=0.0, ok=True)
    checks = await _extra_readiness_checks()
    assert checks["rate_limit_share_valid"] is False
    assert "state_store_reachable" not in checks


@pytest.mark.asyncio
async def test_readiness_memory_backend_share_valid(monkeypatch) -> None:
    settings = _memory_settings(
        quota_group_rate_limits={"g1": {"rpm": 10}},
        rate_limit_replica_share=2,
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    checks = await _extra_readiness_checks()
    assert checks == {"rate_limit_share_valid": True}


class _FakeProbeClient:
    def __init__(self, table_name: str, reachable: bool) -> None:
        self._table_name = table_name
        self._reachable = reachable
        self.calls = 0

    async def probe_reachable(self, *args, **kwargs) -> bool:
        self.calls += 1
        return self._reachable

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_readiness_table_unreachable_is_503(monkeypatch) -> None:
    settings = SimpleNamespace(
        state_backend="table",
        table_endpoint="https://placeholder.table.core.windows.net",
        table_health_name="routerhealth",
        table_credit_name="routercredit",
        table_request_timeout_seconds=5.0,
        quota_group_rate_limits={},
        rate_limit_replica_share=1,
        backends={"b1": SimpleNamespace()},
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    monkeypatch.setattr(
        main_module,
        "_table_clients",
        (
            _FakeProbeClient("routercredit", False),
            _FakeProbeClient("routerhealth", True),
        ),
    )
    main_module._state_probe_cache.update(at=0.0, ok=True)
    checks = await _extra_readiness_checks()
    assert checks["state_store_reachable"] is False


@pytest.mark.asyncio
async def test_readiness_probe_cached_within_five_seconds(monkeypatch) -> None:
    settings = SimpleNamespace(
        state_backend="table",
        table_endpoint="https://placeholder.table.core.windows.net",
        table_health_name="routerhealth",
        table_credit_name="routercredit",
        table_request_timeout_seconds=5.0,
        quota_group_rate_limits={},
        rate_limit_replica_share=1,
        backends={"b1": SimpleNamespace()},
    )
    monkeypatch.setattr(main_module, "load_settings", lambda: settings)
    credit = _FakeProbeClient("routercredit", True)
    health = _FakeProbeClient("routerhealth", True)
    monkeypatch.setattr(main_module, "_table_clients", (credit, health))
    main_module._state_probe_cache.update(at=0.0, ok=True)
    first = await _extra_readiness_checks()
    assert first["state_store_reachable"] is True
    total_calls = credit.calls + health.calls
    assert total_calls == 2
    # Second call within the cache bound performs no further reads.
    second = await _extra_readiness_checks()
    assert second["state_store_reachable"] is True
    assert credit.calls + health.calls == total_calls
