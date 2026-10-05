"""Regression tests for logical model aliases (one-hop alias to canonical pool)."""

from __future__ import annotations

import asyncio
import json

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from foundry_router.config import Settings
from foundry_router.config.model_aliases import (
    canonical_request_copy,
    catalog_model_names,
    parse_model_aliases,
    resolve_model_alias,
)
from foundry_router.main import (
    _metrics_store,
    _reset_backend_health_state,
    _reset_credit_state,
    _reset_metrics_state,
    _reset_rate_limit_state,
    app,
)

client = TestClient(app)


def _base_kwargs(**overrides):
    kwargs = {
        "backends_json": '{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4-dep"}, "backend_b": {"endpoint": "https://b.openai.azure.com", "credential": "key-b", "deployment": "gpt-4-dep-b"}}',
        "models_json": '{"gpt-6.1-sol": {"backends": {"backend_a": 1.0, "backend_b": 0.8}}, "text-embedding-3-large": {"backends": {"backend_a": 1.0}}}',
        "client_api_keys_json": '["client-key-123"]',
        "admin_api_keys_json": '["admin-key-789"]',
        "pricing_json": '{"gpt-6.1-sol": {"input_per_million": 10.0, "output_per_million": 30.0}, "text-embedding-3-large": {"input_per_million": 0.13, "output_per_million": 0.0}}',
        "backend_cycle_start_day_json": '{"backend_a": 1, "backend_b": 1}',
        "backend_cycle_allowance_usd_json": '{"backend_a": 200.0, "backend_b": 200.0}',
        "backend_initial_estimated_remaining_usd_json": '{"backend_a": 200.0, "backend_b": 200.0}',
    }
    kwargs.update(overrides)
    return kwargs


@pytest.fixture
def alias_settings(monkeypatch):
    settings = Settings(
        **_base_kwargs(
            model_aliases_json='{"codex-auto-review": "gpt-6.1-sol", "codex-auto-approve": "gpt-6.1-sol", "custom-alias": "text-embedding-3-large"}'
        )
    )

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("foundry_router.main.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.backends._backend_client", None)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.main.asyncio.sleep", no_sleep)
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())
    yield settings
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


@pytest.fixture
def empty_alias_settings(monkeypatch):
    settings = Settings(**_base_kwargs())
    monkeypatch.setattr("foundry_router.main.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.backends._backend_client", None)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())
    yield settings
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


class TestParseModelAliases:
    def test_empty_default(self) -> None:
        assert parse_model_aliases("{}", {"gpt-6.1-sol"}) == {}

    def test_valid_codex_names(self) -> None:
        parsed = parse_model_aliases(
            '{"codex-auto-review": "gpt-6.1-sol", "codex-auto-approve": "gpt-6.1-sol"}',
            {"gpt-6.1-sol"},
        )
        assert parsed == {
            "codex-auto-review": "gpt-6.1-sol",
            "codex-auto-approve": "gpt-6.1-sol",
        }

    def test_duplicate_keys_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate key"):
            parse_model_aliases('{"a": "gpt-6.1-sol", "a": "gpt-6.1-sol"}', {"gpt-6.1-sol", "a"})

    def test_non_string_values_rejected(self) -> None:
        for raw in (
            '{"a": null}',
            '{"a": ["gpt-6.1-sol"]}',
            '{"a": {"target": "gpt-6.1-sol"}}',
            '{"a": 42}',
            "[]",
            "null",
        ):
            with pytest.raises((ValueError, TypeError)):
                parse_model_aliases(raw, {"gpt-6.1-sol"})

    def test_blank_and_whitespace_rejected(self) -> None:
        for raw in (
            '{"": "gpt-6.1-sol"}',
            '{"   ": "gpt-6.1-sol"}',
            '{" alias": "gpt-6.1-sol"}',
            '{"alias ": "gpt-6.1-sol"}',
            '{"alias": " gpt-6.1-sol"}',
        ):
            with pytest.raises(ValueError):
                parse_model_aliases(raw, {"gpt-6.1-sol", "alias"})

    def test_control_characters_rejected(self) -> None:
        with pytest.raises(ValueError, match="control"):
            parse_model_aliases('{"bad\\u0001alias": "gpt-6.1-sol"}', {"gpt-6.1-sol"})
        with pytest.raises(ValueError, match="control"):
            parse_model_aliases('{"alias": "gpt-6.1-sol\\u007f"}', {"gpt-6.1-sol"})

    def test_name_byte_cap(self) -> None:
        long_name = "a" * 257
        with pytest.raises(ValueError, match="exceeds 256"):
            parse_model_aliases(json.dumps({long_name: "gpt-6.1-sol"}), {"gpt-6.1-sol"})

    def test_entry_cap(self) -> None:
        many = {f"alias-{i}": "gpt-6.1-sol" for i in range(1025)}
        with pytest.raises(ValueError, match="must not exceed 1024"):
            parse_model_aliases(json.dumps(many), {"gpt-6.1-sol"})

    def test_raw_json_cap(self) -> None:
        raw = '{"a": "' + "x" * (256 * 1024) + '"}'
        with pytest.raises(ValueError, match="256 KiB"):
            parse_model_aliases(raw, {"gpt-6.1-sol"})

    def test_collision_with_canonical_rejected(self) -> None:
        with pytest.raises(ValueError, match="collides"):
            parse_model_aliases('{"gpt-6.1-sol": "gpt-6.1-sol"}', {"gpt-6.1-sol"})

    def test_self_reference_rejected(self) -> None:
        with pytest.raises(ValueError, match="itself|collides"):
            parse_model_aliases('{"lonely": "lonely"}', {"gpt-6.1-sol", "lonely"})

    def test_alias_to_alias_rejected(self) -> None:
        with pytest.raises(ValueError, match="not another alias"):
            parse_model_aliases('{"a": "b", "b": "gpt-6.1-sol"}', {"gpt-6.1-sol"})

    def test_missing_target_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown model"):
            parse_model_aliases('{"a": "ghost-model"}', {"gpt-6.1-sol"})

    def test_backend_id_as_target_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown model"):
            parse_model_aliases('{"a": "backend_a"}', {"gpt-6.1-sol"})

    def test_pricing_alias_override_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not contain alias"):
            Settings(
                **_base_kwargs(
                    model_aliases_json='{"my-alias": "gpt-6.1-sol"}',
                    pricing_json='{"gpt-6.1-sol": {"input_per_million": 1.0, "output_per_million": 1.0}, "my-alias": {"input_per_million": 1.0, "output_per_million": 1.0}}',
                )
            )


class TestResolve:
    def test_direct_is_not_alias(self) -> None:
        resolution = resolve_model_alias("gpt-6.1-sol", {"a": "gpt-6.1-sol"})
        assert resolution == resolve_model_alias("gpt-6.1-sol", {"a": "gpt-6.1-sol"})
        assert resolution.is_alias is False
        assert resolution.resolved_model == "gpt-6.1-sol"

    def test_alias_resolves_one_hop(self) -> None:
        resolution = resolve_model_alias("a", {"a": "b", "b": "c"})
        assert resolution.resolved_model == "b"
        assert resolution.is_alias is True

    def test_case_sensitive(self) -> None:
        resolution = resolve_model_alias("CODEX-AUTO-REVIEW", {"codex-auto-review": "gpt-6.1-sol"})
        assert resolution.is_alias is False

    def test_canonical_copy_preserves_nested(self) -> None:
        body: dict[str, object] = {
            "model": "codex-auto-review",
            "input": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function"}],
        }
        nested_input = body["input"]
        out = canonical_request_copy(body, "gpt-6.1-sol")
        assert out["model"] == "gpt-6.1-sol"
        assert out["input"] is nested_input
        assert body["model"] == "codex-auto-review"

    def test_catalog_ordering(self) -> None:
        names = catalog_model_names(["b", "a"], {"z-alias": "a", "m-alias": "b"})
        assert names == ["b", "a", "m-alias", "z-alias"]


class TestAliasApi:
    def test_models_includes_aliases_once(self, alias_settings) -> None:
        response = client.get("/openai/v1/models", headers={"api-key": "client-key-123"})
        assert response.status_code == 200
        ids = [m["id"] for m in response.json()["data"]]
        assert ids[:2] == ["gpt-6.1-sol", "text-embedding-3-large"]
        assert ids[2:] == ["codex-auto-approve", "codex-auto-review", "custom-alias"]
        assert len(ids) == len(set(ids))
        assert all(m["owned_by"] == "foundry-router" for m in response.json()["data"])

    def test_empty_alias_config_preserves_models(self, empty_alias_settings) -> None:
        response = client.get("/openai/v1/models", headers={"api-key": "client-key-123"})
        assert {m["id"] for m in response.json()["data"]} == {
            "gpt-6.1-sol",
            "text-embedding-3-large",
        }

    def test_admin_includes_alias_map(self, alias_settings) -> None:
        response = client.get("/admin/status", headers={"x-admin-key": "admin-key-789"})
        assert response.status_code == 200
        assert response.json()["model_aliases"] == {
            "codex-auto-review": "gpt-6.1-sol",
            "codex-auto-approve": "gpt-6.1-sol",
            "custom-alias": "text-embedding-3-large",
        }

    def test_unknown_and_case_mismatch_404_without_egress(self, alias_settings) -> None:
        with respx.mock:
            route = respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
                return_value=Response(200, json={"id": "x"})
            )
            for name in ("unknown-model", "CODEX-AUTO-REVIEW", "removed-alias"):
                response = client.post(
                    "/openai/v1/responses",
                    headers={"api-key": "client-key-123"},
                    json={"model": name, "input": "hi"},
                )
                assert response.status_code == 404
                assert response.json()["error"]["type"] == "model_not_found"
            assert route.call_count == 0

    @respx.mock
    def test_responses_alias_uses_canonical_pool_and_deployment(self, alias_settings) -> None:
        route_a = respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(
                200,
                json={
                    "id": "resp-1",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )
        )
        payload = {
            "model": "codex-auto-review",
            "input": "review this",
            "instructions": "keep intact",
            "tools": [{"type": "function", "name": "approve"}],
            "max_output_tokens": 16,
        }
        response = client.post(
            "/openai/v1/responses", headers={"api-key": "client-key-123"}, json=payload
        )
        assert response.status_code == 200
        assert route_a.call_count == 1
        sent = json.loads(route_a.calls[0].request.content.decode())
        assert sent["model"] == "gpt-4-dep"
        assert sent["input"] == "review this"
        assert sent["instructions"] == "keep intact"
        assert sent["tools"] == [{"type": "function", "name": "approve"}]
        assert sent["max_output_tokens"] == 16
        assert "codex-auto-review" not in route_a.calls[0].request.content.decode()

    @respx.mock
    def test_embeddings_alias_forwards_canonical(self, alias_settings) -> None:
        route = respx.post(
            "https://a.openai.azure.com/openai/deployments/gpt-4-dep/embeddings",
            params={"api-version": "2025-04-01-preview"},
        ).mock(return_value=Response(200, json={"object": "list", "data": []}))
        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key-123"},
            json={"model": "custom-alias", "input": "hello"},
        )
        assert response.status_code == 200
        assert route.call_count == 1

    @respx.mock
    def test_metrics_canonical_and_alias_gauge(self, alias_settings) -> None:
        asyncio.run(_metrics_store.reset())
        respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(
                200, json={"id": "r", "usage": {"input_tokens": 4, "output_tokens": 2}}
            )
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "codex-auto-approve", "input": "hi"},
        )
        assert response.status_code == 200
        metrics = client.get("/metrics", headers={"x-admin-key": "admin-key-789"})
        assert metrics.status_code == 200
        assert 'model="gpt-6.1-sol"' in metrics.text
        assert 'model="codex-auto-approve"' not in metrics.text
        assert (
            'foundry_router_model_alias_info{alias="codex-auto-approve",target="gpt-6.1-sol"} 1'
            in metrics.text
        )

    @respx.mock
    def test_routing_logs_carry_alias_context(self, alias_settings, capsys) -> None:
        respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(200, json={"id": "r"})
        )
        respx.post("https://b.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(200, json={"id": "r-b"})
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "codex-auto-review", "input": "hi"},
        )
        assert response.status_code == 200
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "routing_decision" in combined
        assert (
            "requested_model=codex-auto-review" in combined
            or '"requested_model": "codex-auto-review"' in combined
        )
        assert (
            "resolved_model=gpt-6.1-sol" in combined
            or '"resolved_model": "gpt-6.1-sol"' in combined
        )
        assert "alias=True" in combined or '"alias": true' in combined

    @respx.mock
    def test_failover_keeps_canonical_body(self, alias_settings) -> None:
        respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(502, json={"error": "bad"})
        )
        route_b = respx.post("https://b.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(200, json={"id": "from-b"})
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "codex-auto-review", "input": "hi"},
        )
        assert response.status_code == 200
        assert route_b.call_count == 1
        sent = json.loads(route_b.calls[0].request.content.decode())
        assert sent["model"] == "gpt-4-dep-b"

    def test_readiness_stays_canonical(self, alias_settings) -> None:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True


class TestAliasSharedCapacity:
    """Concurrent alias + direct admission against one constrained credit budget."""

    @staticmethod
    def _tight_settings() -> Settings:
        return Settings(
            backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4-dep"}}',
            models_json='{"gpt-6.1-sol": {"backends": {"backend_a": 1.0}}}',
            client_api_keys_json='["client-key-123"]',
            admin_api_keys_json='["admin-key-789"]',
            model_aliases_json='{"codex-auto-review": "gpt-6.1-sol", "codex-auto-approve": "gpt-6.1-sol"}',
            pricing_json='{"gpt-6.1-sol": {"input_per_million": 10.0, "output_per_million": 30.0}}',
            backend_cycle_start_day_json='{"backend_a": 1}',
            backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
            backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
        )

    def test_concurrent_alias_and_direct_share_one_budget(self) -> None:
        from foundry_router.credit import InMemoryCreditStore
        from foundry_router.health import InMemoryHealthStore
        from foundry_router.routing import select_candidate_backend

        async def run() -> None:
            settings = self._tight_settings()
            health_store = InMemoryHealthStore()
            credit_store = InMemoryCreditStore()
            events: list[tuple[tuple, dict]] = []

            class Logger:
                def info(self, *args, **kwargs) -> None:
                    events.append((args, kwargs))

                debug = info
                warning = info

            logger = Logger()
            # Each estimate is ~90 USD against ~190 USD spendable credit, so
            # exactly two of the three concurrent requests fit one shared budget.
            body = {"input": "hi", "max_output_tokens": 3_000_000}
            attempts = [
                ("req-alias-1", "codex-auto-review", True),
                ("req-alias-2", "codex-auto-approve", True),
                ("req-direct", "gpt-6.1-sol", False),
            ]

            async def attempt(request_id: str, requested: str, is_alias: bool) -> tuple:
                resolution = resolve_model_alias(requested, settings.model_aliases)
                assert resolution.resolved_model == "gpt-6.1-sol"
                assert resolution.is_alias is is_alias
                selection = await select_candidate_backend(
                    settings,
                    resolution.resolved_model,
                    operation="responses",
                    body=dict(body),
                    request_id=request_id,
                    health_store=health_store,
                    credit_store=credit_store,
                    logger=logger,
                    requested_model=resolution.requested_model,
                    is_alias=resolution.is_alias,
                )
                return request_id, selection

            results = await asyncio.gather(
                *(
                    attempt(request_id, requested, is_alias)
                    for request_id, requested, is_alias in attempts
                )
            )
            admitted = [
                request_id for request_id, selection in results if selection.backend_id is not None
            ]
            rejected = [
                request_id for request_id, selection in results if selection.backend_id is None
            ]
            # Shared budget admits exactly two; separate per-alias budgets would admit three.
            assert len(admitted) == 2
            assert len(rejected) == 1
            assert len(set(admitted)) == 2
            for _, selection in results:
                if selection.backend_id is not None:
                    assert selection.backend_id == "backend_a"

            # One credit account holds both reservations; aliases create no extra
            # prices, accounts, quotas, or balances.
            assert set(settings.pricing) == {"gpt-6.1-sol"}
            live = await credit_store.live_snapshot(
                ["backend_a"],
                min_credit_reserve_usd=settings.min_credit_reserve_usd,
                min_credit_reserve_percent=settings.min_credit_reserve_percent,
            )
            assert set(live) == {"backend_a"}
            snapshot = live["backend_a"]
            assert snapshot.active_reservations == 2
            assert snapshot.reserved_inflight_usd == pytest.approx(180.00002)
            assert snapshot.estimated_remaining_usd == pytest.approx(200.0)

            # Each reservation finalizes exactly once with its own settlement amount.
            await credit_store.finalize_request(
                admitted[0], backend_id="backend_a", charge_reserved=True, charged_cost_usd=1.5
            )
            await credit_store.finalize_request(
                admitted[1], backend_id="backend_a", charge_reserved=False, charged_cost_usd=None
            )
            # The rejected request holds nothing; finalizing it is a no-op.
            await credit_store.finalize_request(
                rejected[0], backend_id="backend_a", charge_reserved=False, charged_cost_usd=None
            )
            settled = await credit_store.live_snapshot(
                ["backend_a"],
                min_credit_reserve_usd=settings.min_credit_reserve_usd,
                min_credit_reserve_percent=settings.min_credit_reserve_percent,
            )
            assert settled["backend_a"].active_reservations == 0
            assert settled["backend_a"].reserved_inflight_usd == pytest.approx(0.0)
            assert settled["backend_a"].estimated_remaining_usd == pytest.approx(198.5)

        asyncio.run(run())

    def test_concurrent_orchestration_auto_finalizes_under_shared_quota(self) -> None:
        """Concurrent alias + direct requests share one quota budget with automatic cleanup.

        Three requests (two aliases plus direct) run concurrently through the real
        orchestration against rpm=2 with ample credit. Exactly two are admitted;
        the rejected request performs no egress and holds no reservation. Credit
        and quota stores settle automatically: no orphan reservations, exact
        canonical balances, shared quota usage, and canonical once-per-outcome
        metrics. The test itself never calls finalization.
        """
        from functools import partial

        from fastapi.responses import JSONResponse

        from foundry_router.api.common import api_error, finalize_non_streaming_credit
        from foundry_router.credit import InMemoryCreditStore
        from foundry_router.forwarding import BackendRequestResult
        from foundry_router.health import InMemoryHealthStore
        from foundry_router.metrics import InMemoryMetricsStore
        from foundry_router.ratelimit import InMemoryRateLimitStore
        from foundry_router.routing import execute_with_single_failover

        async def run() -> None:
            settings = Settings(
                backends_json='{"backend_a": {"endpoint": "https://a.openai.azure.com", "credential": "key-a", "deployment": "gpt-4-dep"}}',
                models_json='{"gpt-6.1-sol": {"backends": {"backend_a": 1.0}}}',
                client_api_keys_json='["client-key-123"]',
                admin_api_keys_json='["admin-key-789"]',
                model_aliases_json='{"codex-auto-review": "gpt-6.1-sol", "codex-auto-approve": "gpt-6.1-sol"}',
                pricing_json='{"gpt-6.1-sol": {"input_per_million": 10.0, "output_per_million": 30.0}}',
                backend_cycle_start_day_json='{"backend_a": 1}',
                backend_cycle_allowance_usd_json='{"backend_a": 200.0}',
                backend_initial_estimated_remaining_usd_json='{"backend_a": 200.0}',
                quota_group_rate_limits_json='{"backend_a": {"rpm": 2}}',
            )
            health_store = InMemoryHealthStore()
            credit_store = InMemoryCreditStore()
            quota_store = InMemoryRateLimitStore()
            metrics_store = InMemoryMetricsStore()
            backend_calls: list[tuple[str, str]] = []
            events: list[tuple[tuple, dict]] = []

            class Logger:
                def info(self, *args, **kwargs) -> None:
                    events.append((args, kwargs))

                debug = info
                warning = info

            logger = Logger()

            async def attempt(request_id: str, requested: str) -> tuple[str, int]:
                resolution = resolve_model_alias(requested, settings.model_aliases)
                canonical_body = canonical_request_copy(
                    {"model": requested, "input": "hi"}, resolution.resolved_model
                )

                async def execute_backend(backend_id: str, **_kwargs) -> BackendRequestResult:
                    backend_calls.append((request_id, backend_id))
                    return BackendRequestResult(
                        JSONResponse(
                            {"id": "resp", "usage": {"input_tokens": 10, "output_tokens": 5}}
                        ),
                        False,
                    )

                response = await execute_with_single_failover(
                    settings,
                    resolution.resolved_model,
                    operation="responses",
                    body=canonical_body,
                    request_id=request_id,
                    execute_backend=execute_backend,
                    health_store=health_store,
                    credit_store=credit_store,
                    metrics_store=metrics_store,
                    logger=logger,
                    api_error=api_error,
                    finalize_non_streaming_credit=partial(
                        finalize_non_streaming_credit,
                        credit_store=credit_store,
                        rate_limit_store=quota_store,
                    ),
                    rate_limit_store=quota_store,
                    requested_model=resolution.requested_model,
                    is_alias=resolution.is_alias,
                )
                return request_id, response.status_code

            results = await asyncio.gather(
                attempt("req-alias-1", "codex-auto-review"),
                attempt("req-alias-2", "codex-auto-approve"),
                attempt("req-direct", "gpt-6.1-sol"),
            )
            statuses = sorted(status for _, status in results)
            assert statuses == [200, 200, 429]
            # The shared rpm=2 budget admits exactly two; separate per-alias
            # budgets would admit all three.
            assert len(backend_calls) == 2
            admitted_ids = {request_id for request_id, _ in backend_calls}
            assert len(admitted_ids) == 2
            rejected_ids = {request_id for request_id, _ in results} - admitted_ids
            assert len(rejected_ids) == 1
            assert all(backend_id == "backend_a" for _, backend_id in backend_calls)

            # Automatic finalization left no orphan reservations and debited the
            # two actual usage charges (0.00025 each) against canonical prices.
            live = await credit_store.live_snapshot(
                ["backend_a"],
                min_credit_reserve_usd=settings.min_credit_reserve_usd,
                min_credit_reserve_percent=settings.min_credit_reserve_percent,
            )
            assert live["backend_a"].active_reservations == 0
            assert live["backend_a"].reserved_inflight_usd == pytest.approx(0.0)
            assert live["backend_a"].estimated_remaining_usd == pytest.approx(200.0 - 2 * 0.00025)

            # The shared quota budget records exactly the two admitted requests.
            quota_snapshot = (await quota_store.snapshot_quota_groups(["backend_a"]))["backend_a"]
            assert quota_snapshot.rpm_used_60s == 2
            assert quota_snapshot.remaining_rpm == 0

            # Metrics count once per outcome under the canonical model only.
            rendered = await metrics_store.render_prometheus(
                backend_health_states={}, backend_available_credit_usd={}
            )
            assert (
                'foundry_router_requests_total{model="gpt-6.1-sol",backend="backend_a",status="200"} 2'
                in rendered
            )
            assert (
                'foundry_router_requests_total{model="gpt-6.1-sol",backend="none",status="429"} 1'
                in rendered
            )
            assert (
                'foundry_router_estimated_cost_usd_total{model="gpt-6.1-sol",backend="backend_a"} 0.000500000'
                in rendered
            )
            assert "codex-auto" not in rendered

            # Routing diagnostics kept requested/resolved identity per request.
            assert any(
                kwargs.get("requested_model") == "codex-auto-review"
                and kwargs.get("resolved_model") == "gpt-6.1-sol"
                and kwargs.get("alias") is True
                for _args, kwargs in events
            )
            assert any(
                kwargs.get("requested_model") == "gpt-6.1-sol" and kwargs.get("alias") is False
                for _args, kwargs in events
            )

        asyncio.run(run())


class TestAliasedStreaming:
    """Aliased SSE lifecycle: byte passthrough, canonical settlement, failure,
    cancellation, and in-flight configuration freeze."""

    CANONICAL_USAGE_COST = (20 * 10.0 + 10 * 30.0) / 1_000_000  # 0.0005

    @respx.mock
    def test_fragmented_usage_settles_canonical_and_preserves_bytes(self, alias_settings) -> None:
        import httpx

        asyncio.run(_metrics_store.reset())
        head = b'data: {"id":"resp-1","model":"gpt-4-dep"}\n\n'
        usage_json = b'{"usage":{"input_tokens":20,"output_tokens":10}}'
        # Fragment the usage event across chunk boundaries, splitting mid-JSON.
        pieces = [usage_json[:20], usage_json[20:35], usage_json[35:]]
        sse_chunks = [
            head,
            b"data: " + pieces[0],
            pieces[1],
            pieces[2] + b"\n\n",
            b"data: [DONE]\n\n",
        ]
        expected = b"".join(sse_chunks)

        class FragmentedStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                for piece in sse_chunks:
                    yield piece

            async def aclose(self) -> None:
                return None

        route = respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
            side_effect=lambda _request: Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=FragmentedStream(),
            )
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "codex-auto-review", "input": "hi", "stream": True},
        )
        assert response.status_code == 200
        # SSE bytes are forwarded unchanged, including the provider deployment model.
        assert response.content == expected
        assert b'"model":"gpt-4-dep"' in response.content
        # The upstream request carries the canonical deployment model, never the alias.
        sent = json.loads(route.calls[0].request.content.decode())
        assert sent["model"] == "gpt-4-dep"
        assert "codex-auto-review" not in route.calls[0].request.content.decode()
        # Settlement and metrics use canonical identity and canonical prices.
        rendered = asyncio.run(
            _metrics_store.render_prometheus(
                backend_health_states={}, backend_available_credit_usd={}
            )
        )
        assert (
            'foundry_router_estimated_cost_usd_total{model="gpt-6.1-sol",backend="backend_a"} 0.000500000'
            in rendered
        )
        assert "codex-auto-review" not in rendered

    def test_stream_response_fragmented_usage_canonical_charge(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from foundry_router.forwarding import stream_response

        async def exercise() -> None:
            usage = b'data: {"id":"u","model":"gpt-4-dep","usage":{"input_tokens":20,"output_tokens":10}}\n\n'
            parts = [usage[:30], usage[30:55], usage[55:]]

            async def chunks():
                for part in parts[1:]:
                    yield part

            context = SimpleNamespace(__aexit__=AsyncMock())
            credit = SimpleNamespace(finalize_request=AsyncMock())
            metrics = SimpleNamespace(observe_request=AsyncMock())
            quota = SimpleNamespace(finalize_request=AsyncMock())
            stream = stream_response(
                chunks(),
                parts[0],
                context,
                request_id="req-alias-frag",
                backend_id="backend_a",
                cooldown_seconds=10.0,
                model="gpt-6.1-sol",
                pricing={
                    "gpt-6.1-sol": SimpleNamespace(input_per_million=10.0, output_per_million=30.0)
                },
                status_code=200,
                set_backend_cooldown=AsyncMock(),
                credit_store=credit,
                metrics_store=metrics,
                rate_limit_store=quota,
            )
            forwarded = [chunk async for chunk in stream]
            assert b"".join(forwarded) == usage
            credit.finalize_request.assert_awaited_once_with(
                "req-alias-frag",
                backend_id="backend_a",
                charge_reserved=True,
                charged_cost_usd=pytest.approx(self.CANONICAL_USAGE_COST),
            )
            quota.finalize_request.assert_awaited_once_with(
                "req-alias-frag", actual_input_tokens=20
            )
            assert metrics.observe_request.await_args.kwargs["model"] == "gpt-6.1-sol"
            assert metrics.observe_request.await_args.kwargs["estimated_cost_usd"] == pytest.approx(
                self.CANONICAL_USAGE_COST
            )
            context.__aexit__.assert_awaited_once()

        asyncio.run(exercise())

    @respx.mock
    def test_midstream_failure_emits_sse_error_without_failover(self, alias_settings) -> None:
        import httpx

        class BrokenStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'data: {"id":"one","model":"gpt-4-dep"}\n\n'
                raise httpx.ReadError("stream failed")

            async def aclose(self) -> None:
                return None

        route_a = respx.post("https://a.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=BrokenStream(),
            )
        )
        route_b = respx.post("https://b.openai.azure.com/openai/v1/responses").mock(
            return_value=Response(200, headers={"content-type": "text/event-stream"}, content=b"")
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "codex-auto-approve", "input": "hi", "stream": True},
        )
        assert response.status_code == 200
        assert b'"id":"one"' in response.content
        assert b'"type":"upstream_error"' in response.content
        assert route_a.call_count == 1
        assert route_b.call_count == 0

    def test_cancellation_cleans_up_once_under_canonical_identity(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from foundry_router.forwarding import stream_response

        async def exercise() -> None:
            context = SimpleNamespace(__aexit__=AsyncMock())
            credit = SimpleNamespace(finalize_request=AsyncMock())
            metrics = SimpleNamespace(observe_request=AsyncMock())
            quota = SimpleNamespace(finalize_request=AsyncMock())
            arrived = asyncio.Event()
            release = asyncio.Event()

            async def chunks():
                arrived.set()
                await release.wait()
                yield b'data: {"id":"one","model":"gpt-4-dep"}\n\n'

            stream = stream_response(
                chunks(),
                b'data: {"id":"first","model":"gpt-4-dep"}\n\n',
                context,
                request_id="req-alias-cancel",
                backend_id="backend_a",
                cooldown_seconds=10.0,
                model="gpt-6.1-sol",
                pricing={
                    "gpt-6.1-sol": SimpleNamespace(input_per_million=10.0, output_per_million=30.0)
                },
                status_code=200,
                set_backend_cooldown=AsyncMock(),
                credit_store=credit,
                metrics_store=metrics,
                rate_limit_store=quota,
            )
            assert await anext(stream)
            pending = asyncio.create_task(anext(stream))
            # Wait until the consumer is blocked inside the upstream chunks, so
            # cancellation deterministically interrupts an in-flight aliased stream.
            await arrived.wait()
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            release.set()
            await stream.aclose()
            context.__aexit__.assert_awaited_once()
            credit.finalize_request.assert_awaited_once()
            assert credit.finalize_request.await_args.kwargs["charge_reserved"] is True
            metrics.observe_request.assert_awaited_once()
            assert metrics.observe_request.await_args.kwargs["model"] == "gpt-6.1-sol"

        asyncio.run(exercise())

    def test_inflight_stream_frozen_across_settings_replacement(
        self, alias_settings, monkeypatch
    ) -> None:
        """An aliased stream started through the route keeps its captured target.

        The stream is paused mid-flight, the settings loader is replaced (alias
        removed, canonical prices raised 10x), then the stream finishes. The
        settlement must use the original canonical prices; a later request must
        observe the replaced mapping. This fails if completion re-resolves or
        reprices from current settings.
        """
        import threading

        from foundry_router.main import _credit_store

        asyncio.run(_metrics_store.reset())
        arrived = threading.Event()
        release = threading.Event()

        class GatedUpstream:
            status_code = 200

            def __init__(self) -> None:
                self.headers = {"content-type": "text/event-stream"}
                self.exits = 0

            async def aiter_raw(self):
                yield b'data: {"id":"one","model":"gpt-4-dep"}\n\n'
                arrived.set()
                # Park the upstream without blocking the server event loop.
                await asyncio.to_thread(release.wait, 30)
                yield b'data: {"usage":{"input_tokens":20,"output_tokens":10}}\n\n'
                yield b"data: [DONE]\n\n"

            async def aread(self):
                return b""

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                self.exits += 1

        upstream = GatedUpstream()
        backend_calls: list = []

        class GatedBackendClient:
            def stream_backend(self, *args, **kwargs):
                backend_calls.append((args, kwargs))
                return upstream

            async def request_backend(self, *args, **kwargs):
                raise AssertionError("streaming test must not use non-streaming path")

        def get_gated_client() -> GatedBackendClient:
            return GatedBackendClient()

        monkeypatch.setattr("foundry_router.main.get_backend_client", get_gated_client)
        outcome: dict = {}

        def do_post() -> None:
            try:
                outcome["response"] = client.post(
                    "/openai/v1/responses",
                    headers={"api-key": "client-key-123"},
                    json={"model": "codex-auto-review", "input": "hi", "stream": True},
                )
            except Exception as exc:  # re-raised on the main thread below
                outcome["error"] = exc

        thread = threading.Thread(target=do_post, daemon=True)
        thread.start()
        try:
            assert arrived.wait(20), "upstream never produced the first chunk"
            # Replace the loader result mid-flight: the alias disappears and the
            # old canonical prices are raised 10x (0.0005 becomes 0.005).
            new_settings = Settings(
                **_base_kwargs(
                    model_aliases_json="{}",
                    pricing_json='{"gpt-6.1-sol": {"input_per_million": 100.0, "output_per_million": 300.0}, "text-embedding-3-large": {"input_per_million": 0.13, "output_per_million": 0.0}}',
                )
            )
            monkeypatch.setattr("foundry_router.main.load_settings", lambda: new_settings)
            monkeypatch.setattr("foundry_router.auth.load_settings", lambda: new_settings)
            release.set()
            thread.join(30)
            assert not thread.is_alive(), "streaming request did not finish"
        finally:
            release.set()

        assert "error" not in outcome, outcome.get("error")
        response = outcome["response"]
        assert response.status_code == 200
        assert response.content == (
            b'data: {"id":"one","model":"gpt-4-dep"}\n\n'
            b'data: {"usage":{"input_tokens":20,"output_tokens":10}}\n\n'
            b"data: [DONE]\n\n"
        )
        assert upstream.exits == 1
        assert len(backend_calls) == 1
        # Settlement kept the frozen canonical prices, not the replaced ones.
        live = asyncio.run(
            _credit_store.live_snapshot(
                ["backend_a"],
                min_credit_reserve_usd=alias_settings.min_credit_reserve_usd,
                min_credit_reserve_percent=alias_settings.min_credit_reserve_percent,
            )
        )
        assert live["backend_a"].active_reservations == 0
        assert live["backend_a"].estimated_remaining_usd == pytest.approx(
            200.0 - self.CANONICAL_USAGE_COST
        )
        rendered = asyncio.run(
            _metrics_store.render_prometheus(
                backend_health_states={}, backend_available_credit_usd={}
            )
        )
        assert (
            'foundry_router_estimated_cost_usd_total{model="gpt-6.1-sol",backend="backend_a"} 0.000500000'
            in rendered
        )
        assert "codex-auto-review" not in rendered
        # A later request observes the replaced mapping: the alias is gone and
        # no further backend egress occurs for it.
        follow_up = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key-123"},
            json={"model": "codex-auto-review", "input": "hi"},
        )
        assert follow_up.status_code == 404
        assert follow_up.json()["error"]["type"] == "model_not_found"
        assert len(backend_calls) == 1


class TestAliasSelectionContext:
    @staticmethod
    def _settings() -> Settings:
        return Settings(**_base_kwargs(model_aliases_json='{"a": "gpt-6.1-sol"}'))

    def test_select_carries_alias_logging(self) -> None:
        from foundry_router.credit import InMemoryCreditStore
        from foundry_router.health import InMemoryHealthStore
        from foundry_router.routing import select_candidate_backend

        async def run() -> None:
            settings = self._settings()
            events: list[tuple[tuple, dict]] = []

            class Logger:
                def info(self, *args, **kwargs) -> None:
                    events.append((args, kwargs))

                debug = info
                warning = info

            result = await select_candidate_backend(
                settings,
                "gpt-6.1-sol",
                operation="responses",
                body={"input": "hi"},
                request_id="req-1",
                health_store=InMemoryHealthStore(),
                credit_store=InMemoryCreditStore(),
                logger=Logger(),
                requested_model="a",
                is_alias=True,
            )
            assert result.backend_id is not None
            assert any(
                kwargs.get("requested_model") == "a"
                and kwargs.get("resolved_model") == "gpt-6.1-sol"
                and kwargs.get("alias") is True
                for _args, kwargs in events
            )

        asyncio.run(run())

    def test_direct_logging_defaults(self) -> None:
        from foundry_router.credit import InMemoryCreditStore
        from foundry_router.health import InMemoryHealthStore
        from foundry_router.routing import select_candidate_backend

        async def run() -> None:
            settings = self._settings()
            events: list[tuple[tuple, dict]] = []

            class Logger:
                def info(self, *args, **kwargs) -> None:
                    events.append((args, kwargs))

                debug = info
                warning = info

            await select_candidate_backend(
                settings,
                "gpt-6.1-sol",
                operation="responses",
                body={"input": "hi"},
                request_id="req-2",
                health_store=InMemoryHealthStore(),
                credit_store=InMemoryCreditStore(),
                logger=Logger(),
            )
            assert any(
                kwargs.get("requested_model") == "gpt-6.1-sol" and kwargs.get("alias") is False
                for _args, kwargs in events
            )

        asyncio.run(run())
