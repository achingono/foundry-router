"""Per-credit-group reserve policy configuration and integration."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from foundry_router.api.common import api_error, finalize_non_streaming_credit
from foundry_router.api.google_sealing import backend_fingerprint
from foundry_router.api.routes.admin import build_router as admin_router
from foundry_router.auth import verify_admin_auth
from foundry_router.config import Settings
from foundry_router.config.group_reserves import GroupReservePolicy, parse_group_reserves
from foundry_router.credit import CreditAssessment, CreditState, InMemoryCreditStore
from foundry_router.forwarding import BackendRequestResult
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.routing import execute_with_single_failover, select_candidate_backend

ZEN_GROUP = "zen-g"
AZURE_GROUP = "azure-g"
OVERRIDE = {"min_credit_reserve_usd": 0.05, "min_credit_reserve_percent": 5.0}


def base_kwargs(**extra: Any) -> dict[str, Any]:
    backends = {
        "zen": {
            "provider": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1",
            "credential": "test-only",
            "deployment": "m-zen",
            "credit_group": ZEN_GROUP,
        },
        "azure": {
            "endpoint": "https://example.openai.azure.com",
            "credential": "test-only",
            "deployment": "m-azure",
            "credit_group": AZURE_GROUP,
        },
    }
    kwargs: dict[str, Any] = {
        "_env_file": None,
        "backends_json": json.dumps(backends),
        "models_json": json.dumps({"z": {"backends": {"zen": 1}}, "a": {"backends": {"azure": 1}}}),
        "client_api_keys_json": '["client-test"]',
        "admin_api_keys_json": '["admin-test"]',
        "pricing_json": json.dumps(
            {
                "z": {"input_per_million": 1, "output_per_million": 1},
                "a": {"input_per_million": 1, "output_per_million": 1},
            }
        ),
        "backend_cycle_start_day_json": json.dumps({ZEN_GROUP: 1, AZURE_GROUP: 1}),
        "backend_cycle_allowance_usd_json": json.dumps({ZEN_GROUP: 10, AZURE_GROUP: 210}),
        "backend_initial_estimated_remaining_usd_json": json.dumps(
            {ZEN_GROUP: 10, AZURE_GROUP: 210}
        ),
    }
    kwargs.update(extra)
    return kwargs


def mixed_settings(**extra: Any) -> Settings:
    return Settings(**base_kwargs(**extra))


def test_empty_map_inherits_app_wide() -> None:
    settings = mixed_settings()
    assert settings.credit_group_reserves == {}
    assert settings.resolve_reserve_policy(ZEN_GROUP) == GroupReservePolicy(10.0, 5.0)
    assert settings.resolve_reserve_policy(AZURE_GROUP) == GroupReservePolicy(10.0, 5.0)


def test_explicit_override_and_zero_pair() -> None:
    settings = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    assert settings.resolve_reserve_policy(ZEN_GROUP) == GroupReservePolicy(0.05, 5.0)
    assert settings.resolve_reserve_policy(AZURE_GROUP) == GroupReservePolicy(10.0, 5.0)
    zeroed = mixed_settings(
        credit_group_reserves_json=json.dumps(
            {ZEN_GROUP: {"min_credit_reserve_usd": 0, "min_credit_reserve_percent": 0}}
        ),
    )
    assert zeroed.resolve_reserve_policy(ZEN_GROUP) == GroupReservePolicy(0.0, 0.0)


def test_percent_boundary_accepts_hundred() -> None:
    settings = mixed_settings(
        credit_group_reserves_json=json.dumps(
            {ZEN_GROUP: {"min_credit_reserve_usd": 1, "min_credit_reserve_percent": 100}}
        ),
    )
    assert settings.resolve_reserve_policy(ZEN_GROUP) == GroupReservePolicy(1.0, 100.0)


@pytest.mark.parametrize(
    "entry",
    [
        {"min_credit_reserve_usd": -0.01, "min_credit_reserve_percent": 5.0},
        {"min_credit_reserve_usd": 0.05, "min_credit_reserve_percent": -1},
        {"min_credit_reserve_usd": 0.05, "min_credit_reserve_percent": 100.01},
        {"min_credit_reserve_usd": True, "min_credit_reserve_percent": 5.0},
        {"min_credit_reserve_usd": "0.05", "min_credit_reserve_percent": 5.0},
        {"min_credit_reserve_usd": None, "min_credit_reserve_percent": 5.0},
        {"min_credit_reserve_usd": 0.05},
        {"min_credit_reserve_usd": 0.05, "min_credit_reserve_percent": 5.0, "other": 1},
        "not-an-object",
        [0.05, 5.0],
    ],
)
def test_malformed_entries_refused(entry: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(credit_group_reserves_json=json.dumps({ZEN_GROUP: entry}))


@pytest.mark.parametrize("raw", ["[1,2]", "42", '"x"', "{bad json"])
def test_malformed_top_level_refused(raw: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(credit_group_reserves_json=raw)


def test_non_finite_numbers_refused() -> None:
    for token in ("NaN", "Infinity"):
        raw = f'{{"{ZEN_GROUP}": {{"min_credit_reserve_usd": {token}, "min_credit_reserve_percent": 5.0}}}}'
        with pytest.raises((TypeError, ValueError)):
            mixed_settings(credit_group_reserves_json=raw)


def test_duplicate_keys_refused() -> None:
    pair = '{"min_credit_reserve_usd": 0.05, "min_credit_reserve_percent": 5.0}'
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(
            credit_group_reserves_json=f'{{"{ZEN_GROUP}": {pair}, "{ZEN_GROUP}": {pair}}}'
        )
    dup_fields = (
        '{"min_credit_reserve_usd": 0.05, "min_credit_reserve_usd": 0.06, '
        '"min_credit_reserve_percent": 5.0}'
    )
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(credit_group_reserves_json=f'{{"{ZEN_GROUP}": {dup_fields}}}')


def test_oversize_input_refused() -> None:
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(credit_group_reserves_json=" " * (64 * 1024 + 1))


def test_unknown_group_refused() -> None:
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(credit_group_reserves_json=json.dumps({"ghost": OVERRIDE}))


def test_non_metered_group_refused() -> None:
    kwargs = base_kwargs()
    backends = json.loads(kwargs["backends_json"])
    backends["plain"] = {
        "endpoint": "https://example.openai.azure.com",
        "credential": "test-only",
        "deployment": "m-plain",
        "credit_group": "plain-g",
        "credit_metered": False,
    }
    kwargs["backends_json"] = json.dumps(backends)
    kwargs["credit_group_reserves_json"] = json.dumps({"plain-g": OVERRIDE})
    with pytest.raises((TypeError, ValueError)):
        Settings(**kwargs)


def test_backend_id_mapped_elsewhere_refused() -> None:
    with pytest.raises((TypeError, ValueError)):
        mixed_settings(credit_group_reserves_json=json.dumps({"zen": OVERRIDE}))


def test_non_string_raw_refused() -> None:
    with pytest.raises(TypeError):
        parse_group_reserves(None, set(), set())  # type: ignore[arg-type]


def test_entry_count_bound_refused() -> None:
    raw = "{" + ",".join(f'"g{i}": 0' for i in range(1025)) + "}"
    assert len(raw.encode("utf-8")) < 64 * 1024
    with pytest.raises(ValueError):
        parse_group_reserves(raw, {f"g{i}" for i in range(1025)}, set())


def test_resolver_rejects_unknown_id() -> None:
    settings = mixed_settings()
    with pytest.raises(ValueError):
        settings.resolve_reserve_policy("ghost")


def test_validation_errors_carry_no_values() -> None:
    marker = "987654321.5"
    raw = json.dumps(
        {"ghost": {"min_credit_reserve_usd": 987654321.5, "min_credit_reserve_percent": 5.0}}
    )
    try:
        mixed_settings(credit_group_reserves_json=raw)
    except (TypeError, ValueError) as exc:
        assert marker not in str(exc)
    else:  # pragma: no cover - must refuse
        raise AssertionError("unknown group accepted")
    with pytest.raises((TypeError, ValueError)) as info:
        parse_group_reserves("not an object", set(), set())
    assert "not an object" not in str(info.value)


async def run_model(settings: Settings, store: Any, model: str) -> int:
    async def finalize(**kwargs: Any) -> Any:
        return await finalize_non_streaming_credit(**kwargs, credit_store=store)

    async def execute(_backend: str, *_args: Any, **_kwargs: Any) -> BackendRequestResult:
        return BackendRequestResult(
            JSONResponse({"usage": {"input_tokens": 1, "output_tokens": 0}}, status_code=200),
            True,
        )

    response = await execute_with_single_failover(
        settings,
        model,
        operation="responses",
        body={"input": "abc", "max_output_tokens": 5},
        request_id="r",
        execute_backend=execute,
        health_store=InMemoryHealthStore(),
        credit_store=store,
        metrics_store=InMemoryMetricsStore(),
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
        api_error=api_error,
        finalize_non_streaming_credit=finalize,
    )
    return response.status_code


@pytest.mark.asyncio
async def test_override_admits_where_app_wide_refuses() -> None:
    blocked = mixed_settings()
    assert await run_model(blocked, InMemoryCreditStore(), "z") != 200
    admitted = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    assert await run_model(admitted, InMemoryCreditStore(), "z") == 200


@pytest.mark.asyncio
async def test_inherited_group_matches_app_wide_behavior() -> None:
    assert await run_model(mixed_settings(), InMemoryCreditStore(), "a") == 200
    unrelated = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    assert await run_model(unrelated, InMemoryCreditStore(), "a") == 200


class ScalarOnlyStore:
    """Test double without context APIs; records scalar reserve arguments."""

    def __init__(self, inner: InMemoryCreditStore) -> None:
        self.inner = inner
        self.assess_calls: list[dict[str, Any]] = []
        self.reserve_calls: list[dict[str, Any]] = []

    async def sync_from_settings(self, settings: Settings) -> None:
        await self.inner.sync_from_settings(settings)

    async def assess(self, backend_id: str, cost: float, **kwargs: Any) -> CreditAssessment:
        self.assess_calls.append({"backend_id": backend_id, **kwargs})
        return CreditAssessment(
            state=CreditState.USABLE,
            available_credit_usd=9.5,
            projected_unused_credit_usd=9.5,
            estimated_request_cost_usd=cost,
            cycle_allowance_usd=10.0,
        )

    async def try_assign_reservation(
        self, request_id: str, backend_id: str, cost: float, **kwargs: Any
    ) -> bool:
        self.reserve_calls.append({"backend_id": backend_id, **kwargs})
        return True

    async def finalize_request(self, request_id: str, **kwargs: Any) -> None:
        await self.inner.finalize_request(request_id, **kwargs)

    async def live_snapshot(self, *args: Any, **kwargs: Any) -> Any:
        return await self.inner.live_snapshot(*args, **kwargs)


@pytest.mark.asyncio
async def test_scalar_assess_path_carries_resolved_policy() -> None:
    settings = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    store = ScalarOnlyStore(InMemoryCreditStore())
    result = await select_candidate_backend(
        settings,
        "z",
        operation="responses",
        body={"input": "abc", "max_output_tokens": 5},
        request_id="r",
        health_store=InMemoryHealthStore(),
        credit_store=store,
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
    )
    assert result.backend_id == "zen"
    assert store.assess_calls[0]["min_credit_reserve_usd"] == 0.05
    assert store.assess_calls[0]["min_credit_reserve_percent"] == 5.0


@pytest.mark.asyncio
async def test_scalar_reserve_path_carries_resolved_policy() -> None:
    settings = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    store = ScalarOnlyStore(InMemoryCreditStore())
    assert await run_model(settings, store, "z") == 200
    assert store.reserve_calls[0]["min_credit_reserve_usd"] == 0.05
    assert store.reserve_calls[0]["min_credit_reserve_percent"] == 5.0


@pytest.mark.asyncio
async def test_non_metered_bypass_unchanged() -> None:
    kwargs = base_kwargs()
    backends = json.loads(kwargs["backends_json"])
    backends["plain"] = {
        "endpoint": "https://example.openai.azure.com",
        "credential": "test-only",
        "deployment": "m-plain",
        "credit_metered": False,
    }
    models = json.loads(kwargs["models_json"])
    models["p"] = {"backends": {"plain": 1}}
    pricing = json.loads(kwargs["pricing_json"])
    pricing["p"] = {"input_per_million": 1, "output_per_million": 1}
    kwargs.update(
        backends_json=json.dumps(backends),
        models_json=json.dumps(models),
        pricing_json=json.dumps(pricing),
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    assert await run_model(Settings(**kwargs), InMemoryCreditStore(), "p") == 200


class CountingStore(InMemoryCreditStore):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict[str, Any]] = []

    async def live_snapshot(self, groups: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        self.calls.append({"groups": list(groups), **kwargs})
        return await super().live_snapshot(groups, **kwargs)


def admin_app(settings: Settings, store: Any) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[verify_admin_auth] = lambda: None
    app.include_router(
        admin_router(
            load_settings_fn=lambda: settings,
            health_store=InMemoryHealthStore(),
            credit_store=store,
            metrics_store=InMemoryMetricsStore(),
            reconciliation_status_snapshot=dict,
        )
    )
    return app


@pytest.mark.asyncio
async def test_admin_shows_effective_policy_per_group() -> None:
    settings = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    app = admin_app(settings, InMemoryCreditStore())
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        status = (await client.get("/admin/status")).json()
        zen = status["credit_groups"][ZEN_GROUP]["reserve_policy"]
        assert zen == {
            "min_credit_reserve_usd": 0.05,
            "min_credit_reserve_percent": 5.0,
            "source": "override",
        }
        azure = status["credit_groups"][AZURE_GROUP]["reserve_policy"]
        assert azure["source"] == "inherited"
        assert azure["min_credit_reserve_usd"] == 10.0
        assert (await client.get("/metrics")).status_code == 200


@pytest.mark.asyncio
async def test_admin_reads_once_per_distinct_policy() -> None:
    settings = mixed_settings(
        credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE}),
    )
    store = CountingStore()
    app = admin_app(settings, store)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get("/admin/status")).status_code == 200
    assert len(store.calls) == 2
    seen = {
        (call["min_credit_reserve_usd"], call["min_credit_reserve_percent"]): call["groups"]
        for call in store.calls
    }
    assert seen[(0.05, 5.0)] == [ZEN_GROUP]
    assert seen[(10.0, 5.0)] == [AZURE_GROUP]
    stamps = {call["now_utc"] for call in store.calls}
    assert len(stamps) == 1


@pytest.mark.asyncio
async def test_admin_snapshot_failure_fails_request() -> None:
    from foundry_router.api.routes.admin import _credit_snapshots_by_policy

    class Broken:
        async def live_snapshot(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("store unavailable")

    settings = mixed_settings()
    with pytest.raises(RuntimeError):
        await _credit_snapshots_by_policy(settings, Broken(), [ZEN_GROUP])


def sealing_settings(**extra: Any) -> Settings:
    kwargs = base_kwargs(
        google_state_keys_json=json.dumps(
            {
                "scope_key": base64.urlsafe_b64encode(b"s" * 32).decode(),
                "keys": {"current": base64.urlsafe_b64encode(b"k" * 32).decode()},
                "active": "current",
                "generation": "fixture",
            }
        ),
        **extra,
    )
    return Settings(**kwargs)


def test_empty_map_fingerprint_matches_app_wide_pair() -> None:
    assert backend_fingerprint(sealing_settings(), "zen", "z") == backend_fingerprint(
        sealing_settings(
            credit_group_reserves_json=json.dumps(
                {ZEN_GROUP: {"min_credit_reserve_usd": 10.0, "min_credit_reserve_percent": 5.0}}
            ),
        ),
        "zen",
        "z",
    )


def test_unrelated_override_keeps_binding() -> None:
    before = backend_fingerprint(sealing_settings(), "zen", "z")
    assert (
        backend_fingerprint(
            sealing_settings(credit_group_reserves_json=json.dumps({AZURE_GROUP: OVERRIDE})),
            "zen",
            "z",
        )
        == before
    )


def test_own_group_override_breaks_binding() -> None:
    before = backend_fingerprint(sealing_settings(), "zen", "z")
    assert (
        backend_fingerprint(
            sealing_settings(credit_group_reserves_json=json.dumps({ZEN_GROUP: OVERRIDE})),
            "zen",
            "z",
        )
        != before
    )
