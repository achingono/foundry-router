"""Lifecycle regressions for the nine Google-adapter runtime findings.

Covers, with real credit/quota/health stores and fake transports: cancellation
during the non-streaming body read (connection closed, consumption preserved),
reservation-deadline enforcement in routing and forwarding, 5xx billable
settlement, no zero-output fabrication on translation failure, operation-aware
fallback estimates for embeddings, per-attempt quota accounting on 429
failover, schema-valid stream failure events, and embeddings request matching.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from foundry_router.api.common import api_error, finalize_non_streaming_credit
from foundry_router.config import Settings
from foundry_router.credit import InMemoryCreditStore
from foundry_router.forwarding import (
    _forward_google_non_streaming,
    _google_stream_response,
    forward_non_streaming_with_retries,
)
from foundry_router.health import BackendHealthState, InMemoryHealthStore
from foundry_router.ratelimit import InMemoryRateLimitStore
from foundry_router.routing import execute_with_single_failover

MODEL = "gemini-text"
EMB_MODEL = "gemini-emb"
PRICING = {"input_per_million": 10.0, "output_per_million": 30.0}


def _google_settings(**overrides: Any) -> Settings:
    backends = {
        "gm-a": {
            "provider": "google_ai_studio",
            "endpoint": "https://generativelanguage.googleapis.com",
            "credential": "synthetic-a-key",
            "deployment": "gemini-2.5-flash",
            "quota_group": "pa",
            "credit_metered": True,
        },
        "gm-b": {
            "provider": "google_ai_studio",
            "endpoint": "https://generativelanguage.googleapis.com",
            "credential": "synthetic-b-key",
            "deployment": "gemini-2.5-flash",
            "quota_group": "pb",
            "credit_metered": True,
        },
    }
    kwargs: dict[str, Any] = {
        "backends_json": json.dumps(backends),
        "models_json": json.dumps({MODEL: {"backends": {"gm-a": 2.0, "gm-b": 1.0}}}),
        "client_api_keys_json": '["client-key"]',
        "admin_api_keys_json": '["admin-key"]',
        "pricing_json": json.dumps({MODEL: PRICING, EMB_MODEL: PRICING}),
        "quota_group_rate_limits_json": json.dumps(
            {"pa": {"rpm": 100, "tpm": 100000}, "pb": {"rpm": 100, "tpm": 100000}}
        ),
        "backend_cycle_start_day_json": json.dumps({"gm-a": 1, "gm-b": 1}),
        "backend_cycle_allowance_usd_json": json.dumps({"gm-a": 200.0, "gm-b": 200.0}),
        "backend_initial_estimated_remaining_usd_json": json.dumps({"gm-a": 200.0, "gm-b": 200.0}),
        "retry_attempts": 2,
        "retry_max_delay_seconds": 0.01,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


def _chat_ok(text: str = "synthetic", prompt: int = 4, completion: int = 2) -> dict[str, Any]:
    return {
        "id": "chatcmpl-s",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gemini-2.5-flash",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


def _chat_chunk(text: str = "", finish: str | None = None) -> bytes:
    choice: dict[str, Any] = {"index": 0, "delta": {}, "finish_reason": finish}
    if text:
        choice["delta"] = {"role": "assistant", "content": text}
    payload = {
        "id": "chatcmpl-s",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gemini-2.5-flash",
        "choices": [choice],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


class FakeUpstream:
    def __init__(
        self,
        status_code: int = 200,
        body: bytes = b"",
        chunks: list[bytes] | None = None,
        hang: bool = False,
    ) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self._body = body
        self._chunks = chunks or []
        self._hang = hang

    async def aiter_bytes(self):  # type: ignore[no-untyped-def]
        if self._hang:
            await asyncio.Event().wait()
            yield b""
        else:
            for piece in self._chunks or ([self._body] if self._body else []):
                yield piece


class FakeStreamContext:
    def __init__(self, upstream: FakeUpstream) -> None:
        self.upstream = upstream
        self.closed = False

    async def __aenter__(self) -> FakeUpstream:
        return self.upstream

    async def __aexit__(self, *args: Any) -> None:
        self.closed = True


class FakeBackendClient:
    """Stream-capable fake routing upstream behavior by backend id."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.contexts: list[FakeStreamContext] = []
        self.handler = None  # type: ignore[assignment]

    def stream_backend(self, backend_id: str, operation: str, **kwargs: Any) -> FakeStreamContext:
        self.calls.append((backend_id, operation))
        context = self.handler(backend_id, operation, kwargs.get("json"))
        self.contexts.append(context)
        return context

    async def request_backend(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("stream transport expected for Google backends")


def _stores(settings: Settings) -> SimpleNamespace:
    metrics = MagicMock()
    metrics.observe_request = AsyncMock()
    return SimpleNamespace(
        settings=settings,
        health=InMemoryHealthStore(),
        credit=InMemoryCreditStore(),
        metrics=metrics,
        rate=InMemoryRateLimitStore(),
    )


async def _credit_remaining(credit_store: InMemoryCreditStore, backend_id: str) -> float:
    snapshot = await credit_store.live_snapshot(
        [backend_id], min_credit_reserve_usd=10.0, min_credit_reserve_percent=5.0
    )
    return snapshot[backend_id].estimated_remaining_usd


async def _quota_used(rate_store: InMemoryRateLimitStore, group: str) -> int:
    snapshot = await rate_store.snapshot_quota_groups([group])
    return snapshot[group].rpm_used_60s


async def _execute(
    body: dict[str, Any],
    *,
    fake: FakeBackendClient,
    stores: SimpleNamespace,
    operation: str = "responses",
    request_id: str = "req-1",
) -> Any:
    from functools import partial

    from foundry_router.forwarding import forward_streaming_with_retries

    async def dispatch(backend_id, *, reservation_deadline_monotonic):
        kwargs = {
            "settings": stores.settings,
            "backend_id": backend_id,
            "headers": {},
            "body": body,
            "get_backend_client": lambda: fake,
            "set_backend_active": stores.health.set_backend_active,
            "set_backend_cooldown": stores.health.set_backend_cooldown,
            "sleep": AsyncMock(),
            "api_error": api_error,
            "reservation_deadline_monotonic": reservation_deadline_monotonic,
        }
        if body.get("stream"):
            return await forward_streaming_with_retries(
                **kwargs,
                request_id=request_id,
                credit_store=stores.credit,
                metrics_store=stores.metrics,
                rate_limit_store=stores.rate,
            )
        return await forward_non_streaming_with_retries(**kwargs, operation=operation)

    return await execute_with_single_failover(
        stores.settings,
        body["model"],
        operation=operation,
        body=body,
        request_id=request_id,
        execute_backend=dispatch,
        health_store=stores.health,
        credit_store=stores.credit,
        metrics_store=stores.metrics,
        logger=MagicMock(),
        api_error=api_error,
        finalize_non_streaming_credit=partial(
            finalize_non_streaming_credit,
            credit_store=stores.credit,
            rate_limit_store=stores.rate,
        ),
        rate_limit_store=stores.rate,
    )


# Estimate for {"model": "gemini-text", "input": "hi"} at 10/30 per million:
# input 1 token, output 4096 reserved -> (10 + 122880) / 1e6.
TEXT_ESTIMATE = (1 * 10.0 + 4096 * 30.0) / 1_000_000


class TestCancellationPreservesConsumption:
    @pytest.mark.parametrize("exit_at", ["active", "error_body"])
    async def test_stream_pre_handoff_exits_keep_consumption(self, exit_at):
        stores = _stores(_google_settings())
        interruption = asyncio.Event()

        class BrokenErrorBody(FakeUpstream):
            async def aiter_bytes(self):
                raise httpx.ReadError("synthetic body failure")
                yield b""

        if exit_at == "active":
            chunk = _chat_chunk("synthetic text")
            usage_chunk = (
                b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\n'
            )
            upstream = FakeUpstream(chunks=[chunk + usage_chunk])

            async def blocked_active(_backend_id):
                interruption.set()
                await asyncio.Event().wait()

            stores.health.set_backend_active = blocked_active
        else:
            upstream = BrokenErrorBody(status_code=500)
        context = FakeStreamContext(upstream)
        fake = FakeBackendClient()
        fake.handler = lambda *_args: context
        task = asyncio.create_task(
            _execute({"model": MODEL, "input": "hi", "stream": True}, fake=fake, stores=stores)
        )
        if exit_at == "active":
            await asyncio.wait_for(interruption.wait(), 0.5)
            task.cancel()
        response = await asyncio.wait_for(task, 0.5)
        assert response.status_code == 502
        assert context.closed
        assert fake.calls == [("gm-a", "responses")]
        expected_cost = TEXT_ESTIMATE
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(200 - expected_cost)
        quota = await stores.rate.snapshot_quota_groups(["pa"])
        assert quota["pa"].rpm_used_60s == 1
        assert quota["pa"].input_tpm_used_60s == (4 if exit_at == "active" else 1)
        snapshot = await stores.credit.live_snapshot(
            ["gm-a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
        )
        assert snapshot["gm-a"].active_reservations == 0

    @pytest.mark.parametrize("cancel_at", ["close", "active"])
    async def test_cancel_after_successful_read_settles_known_usage(self, cancel_at):
        settings = _google_settings()
        stores = _stores(settings)
        interruption = asyncio.Event()

        class InterruptedClose(FakeStreamContext):
            async def __aexit__(self, *args):
                if cancel_at == "close" and not interruption.is_set():
                    interruption.set()
                    await asyncio.Event().wait()
                self.closed = True

        context = InterruptedClose(FakeUpstream(body=json.dumps(_chat_ok()).encode()))
        fake = FakeBackendClient()
        fake.handler = lambda *_args: context
        if cancel_at == "active":

            async def blocked_active(_backend_id):
                interruption.set()
                await asyncio.Event().wait()

            stores.health.set_backend_active = blocked_active
        task = asyncio.create_task(
            _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        )
        await asyncio.wait_for(interruption.wait(), 0.5)
        task.cancel()
        response = await asyncio.wait_for(task, 0.5)
        assert response.status_code == 502
        assert context.closed
        assert fake.calls == [("gm-a", "responses")]
        actual_cost = (4 * 10.0 + 2 * 30.0) / 1_000_000
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(200 - actual_cost)
        quota = await stores.rate.snapshot_quota_groups(["pa"])
        assert quota["pa"].rpm_used_60s == 1
        assert quota["pa"].input_tpm_used_60s == 4
        snapshot = await stores.credit.live_snapshot(
            ["gm-a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
        )
        assert snapshot["gm-a"].active_reservations == 0

    async def test_repeated_cancellation_with_blocked_close_keeps_consumption(self, monkeypatch):
        from foundry_router import forwarding
        from foundry_router.cleanup import protected_cleanup

        async def bounded_cleanup(operations):
            await protected_cleanup(operations, timeout_seconds=0.05)

        monkeypatch.setattr(forwarding, "protected_cleanup", bounded_cleanup)
        settings = _google_settings()
        stores = _stores(settings)
        closing = asyncio.Event()

        class BlockedClose(FakeStreamContext):
            async def __aexit__(self, *args):
                closing.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    self.closed = True

        context = BlockedClose(FakeUpstream(hang=True))
        fake = FakeBackendClient()
        fake.handler = lambda *_args: context
        task = asyncio.create_task(
            _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        )
        await asyncio.sleep(0.01)
        task.cancel()
        await closing.wait()
        task.cancel()
        response = await asyncio.wait_for(task, 0.5)
        assert response.status_code == 502
        assert context.closed
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(200 - TEXT_ESTIMATE)
        assert await _quota_used(stores.rate, "pa") == 1

    async def test_cancel_during_body_read_closes_and_charges(self) -> None:
        settings = _google_settings()
        stores = _stores(settings)
        upstream = FakeUpstream(hang=True)
        context = FakeStreamContext(upstream)

        class HangingClient(FakeBackendClient):
            def stream_backend(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
                self.calls.append((args[0], args[1]))
                self.contexts.append(context)
                return context

        fake = HangingClient()
        task = asyncio.create_task(
            _forward_google_non_streaming(
                settings=settings,
                backend_id="gm-a",
                operation="responses",
                headers={},
                public_body={"model": MODEL, "input": "hi"},
                upstream_body={"model": "gemini-2.5-flash", "messages": []},
                backend_client=fake,
                set_backend_active=stores.health.set_backend_active,
                set_backend_cooldown=stores.health.set_backend_cooldown,
                api_error=api_error,
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        result = await task
        assert result.retryable_failure is False
        assert result.force_charge is True
        assert result.settlement_cost_usd == pytest.approx(TEXT_ESTIMATE)
        assert context.closed is True
        snapshots = await stores.health.snapshot_backend_health(["gm-a"])
        assert snapshots["gm-a"].state == BackendHealthState.ERROR_COOLDOWN

    async def test_cancel_through_routing_settles_estimate(self) -> None:
        settings = _google_settings()
        stores = _stores(settings)
        context = FakeStreamContext(FakeUpstream(hang=True))

        class HangingClient(FakeBackendClient):
            def stream_backend(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
                self.calls.append((args[0], args[1]))
                self.contexts.append(context)
                return context

        fake = HangingClient()
        task = asyncio.create_task(
            _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        response = await task
        assert response.status_code == 502
        assert context.closed is True
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(
            200.0 - TEXT_ESTIMATE
        )
        assert await _quota_used(stores.rate, "pa") == 1


class TestReservationDeadline:
    async def test_failover_expired_before_dispatch_releases_second_reservation(self, monkeypatch):
        from foundry_router import routing

        settings = _google_settings()
        stores = _stores(settings)
        select = routing.select_candidate_backend

        async def delayed_selection(*args, **kwargs):
            result = await select(*args, **kwargs)
            if kwargs.get("excluded"):
                await asyncio.sleep(0.05)
            return result

        monkeypatch.setattr(routing, "select_candidate_backend", delayed_selection)
        monkeypatch.setattr(
            routing, "_reservation_deadline_monotonic", lambda _settings: time.monotonic() + 0.03
        )
        fake = FakeBackendClient()
        fake.handler = lambda *_args: FakeStreamContext(FakeUpstream(429, b"{}"))
        response = await _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        assert response.status_code == 502
        assert fake.calls == [("gm-a", "responses")]
        assert await _credit_remaining(stores.credit, "gm-b") == 200
        assert await _quota_used(stores.rate, "pb") == 0

    @pytest.mark.parametrize("block_start", [False, True])
    async def test_asgi_send_deadline_closes_and_settles(self, block_start):
        from foundry_router.forwarding import forward_streaming_with_retries

        settings = _google_settings()
        stores = _stores(settings)
        await stores.credit.sync_from_settings(settings)
        await stores.credit.try_assign_reservation(
            "send-deadline",
            "gm-a",
            TEXT_ESTIMATE,
            min_credit_reserve_usd=0,
            min_credit_reserve_percent=0,
        )
        await stores.rate.sync_from_settings(settings)
        await stores.rate.try_reserve_estimate("send-deadline", "pa", estimated_input_tokens=1)
        context = FakeStreamContext(FakeUpstream(chunks=[_chat_chunk("hi")], hang=False))
        fake = FakeBackendClient()
        fake.handler = lambda *_args: context
        deadline = time.monotonic() + 0.05
        result = await forward_streaming_with_retries(
            settings=settings,
            backend_id="gm-a",
            request_id="send-deadline",
            headers={},
            body={"model": MODEL, "input": "hi", "stream": True},
            get_backend_client=lambda: fake,
            set_backend_active=stores.health.set_backend_active,
            set_backend_cooldown=stores.health.set_backend_cooldown,
            sleep=AsyncMock(),
            api_error=api_error,
            credit_store=stores.credit,
            metrics_store=stores.metrics,
            rate_limit_store=stores.rate,
            reservation_deadline_monotonic=deadline,
        )
        assert result.response.deadline == deadline

        async def send(message):
            if block_start or message["type"] == "http.response.body":
                await asyncio.Event().wait()

        with pytest.raises(TimeoutError):
            await asyncio.wait_for(result.response.stream_response(send), 0.5)
        assert context.closed
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(200 - TEXT_ESTIMATE)
        assert await _quota_used(stores.rate, "pa") == 1

    async def test_routing_deadline_bounds_slow_backend(self) -> None:
        settings = _google_settings(reservation_max_age_seconds=6.0)
        stores = _stores(settings)

        async def slow_backend(_backend_id: str, **_kwargs: Any) -> Any:
            await asyncio.sleep(5.0)
            from foundry_router.forwarding import BackendRequestResult

            return BackendRequestResult(
                response=api_error(500, "late", "upstream_error"), retryable_failure=False
            )

        from functools import partial

        response = await execute_with_single_failover(
            settings,
            MODEL,
            operation="responses",
            body={"model": MODEL, "input": "hi"},
            request_id="req-deadline",
            execute_backend=slow_backend,
            health_store=stores.health,
            credit_store=stores.credit,
            metrics_store=stores.metrics,
            logger=MagicMock(),
            api_error=api_error,
            finalize_non_streaming_credit=partial(
                finalize_non_streaming_credit,
                credit_store=stores.credit,
                rate_limit_store=stores.rate,
            ),
            rate_limit_store=stores.rate,
        )
        assert response.status_code == 502
        assert "deadline" in response.body.decode().lower()
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(
            200.0 - TEXT_ESTIMATE
        )
        assert await _quota_used(stores.rate, "pa") == 1

    async def test_forwarding_read_bounded_by_deadline(self) -> None:
        settings = _google_settings(reservation_max_age_seconds=6.0)
        stores = _stores(settings)
        context = FakeStreamContext(FakeUpstream(hang=True))

        class HangingClient(FakeBackendClient):
            def stream_backend(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
                self.contexts.append(context)
                return context

        result = await _forward_google_non_streaming(
            settings=settings,
            backend_id="gm-a",
            operation="responses",
            headers={},
            public_body={"model": MODEL, "input": "hi"},
            upstream_body={"model": "gemini-2.5-flash", "messages": []},
            backend_client=HangingClient(),
            set_backend_active=stores.health.set_backend_active,
            set_backend_cooldown=stores.health.set_backend_cooldown,
            api_error=api_error,
        )
        assert result.retryable_failure is False
        assert result.force_charge is True
        assert context.closed is True


class TestAmbiguousSettlement:
    def _client_500(self) -> FakeBackendClient:
        fake = FakeBackendClient()

        def handler(*_args: Any) -> FakeStreamContext:
            return FakeStreamContext(FakeUpstream(status_code=500, body=b'{"error": "x"}'))

        fake.handler = handler
        return fake

    async def test_500_settles_estimate_with_single_dispatch(self) -> None:
        settings = _google_settings()
        stores = _stores(settings)
        fake = self._client_500()
        response = await _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        assert response.status_code == 500
        assert len(fake.calls) == 1
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(
            200.0 - TEXT_ESTIMATE
        )
        assert await _quota_used(stores.rate, "pa") == 1

    async def test_partial_usage_translation_failure_keeps_full_estimate(self) -> None:
        settings = _google_settings()
        stores = _stores(settings)
        fake = FakeBackendClient()

        def handler(*_args: Any) -> FakeStreamContext:
            payload = json.dumps(
                {"id": "chatcmpl-x", "choices": [], "usage": {"prompt_tokens": 50}}
            ).encode()
            return FakeStreamContext(FakeUpstream(status_code=200, body=payload))

        fake.handler = handler
        response = await _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        assert response.status_code == 502
        # Input-only usage (50 tokens -> $0.0005) must not replace the estimate.
        assert await _credit_remaining(stores.credit, "gm-a") == pytest.approx(
            200.0 - TEXT_ESTIMATE
        )


class TestEmbeddingsEstimates:
    async def test_malformed_embedding_settles_reported_input_usage(self):
        stores = _stores(self._emb_settings())
        fake = FakeBackendClient()
        payload = {"data": [], "usage": {"prompt_tokens": 2, "total_tokens": 2}}
        fake.handler = lambda *_args: FakeStreamContext(
            FakeUpstream(body=json.dumps(payload).encode())
        )
        response = await _execute(
            {"model": EMB_MODEL, "input": ["hello", "world"]},
            fake=fake,
            stores=stores,
            operation="embeddings",
        )
        assert response.status_code == 502
        assert await _credit_remaining(stores.credit, "gm-emb") == pytest.approx(200 - 0.00002)
        quota = await stores.rate.snapshot_quota_groups(["pe"])
        assert quota["pe"].input_tpm_used_60s == 2

    def _emb_settings(self) -> Settings:
        backends = {
            "gm-emb": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-emb-key",
                "deployment": "gemini-embedding-001",
                "quota_group": "pe",
                "credit_metered": True,
                "supported_operations": ["embeddings"],
            }
        }
        return Settings(
            backends_json=json.dumps(backends),
            models_json=json.dumps({EMB_MODEL: {"backends": {"gm-emb": 1.0}}}),
            client_api_keys_json='["client-key"]',
            admin_api_keys_json='["admin-key"]',
            pricing_json=json.dumps({EMB_MODEL: PRICING}),
            quota_group_rate_limits_json=json.dumps({"pe": {"rpm": 100, "tpm": 100000}}),
            backend_cycle_start_day_json=json.dumps({"gm-emb": 1}),
            backend_cycle_allowance_usd_json=json.dumps({"gm-emb": 200.0}),
            backend_initial_estimated_remaining_usd_json=json.dumps({"gm-emb": 200.0}),
            retry_attempts=2,
            retry_max_delay_seconds=0.01,
        )

    async def test_embeddings_failure_uses_embeddings_estimate(self) -> None:
        settings = self._emb_settings()
        stores = _stores(settings)
        fake = FakeBackendClient()

        def handler(_backend_id: str, operation: str, _body: Any) -> FakeStreamContext:
            assert operation == "embeddings"
            return FakeStreamContext(
                FakeUpstream(status_code=200, body=b'{"object": "list", "data": []}')
            )

        fake.handler = handler
        body = {"model": EMB_MODEL, "input": ["hello", "world"]}
        response = await _execute(
            body,
            fake=fake,
            stores=stores,
            operation="embeddings",
            request_id="req-emb",
        )
        assert response.status_code == 502
        # Embeddings estimate: 4 input tokens, zero output allowance.
        assert await _credit_remaining(stores.credit, "gm-emb") == pytest.approx(
            200.0 - (4 * 10.0) / 1_000_000
        )

    async def test_embeddings_count_mismatch_rejected(self) -> None:
        settings = self._emb_settings()
        stores = _stores(settings)
        fake = FakeBackendClient()

        def handler(*_args: Any) -> FakeStreamContext:
            payload = json.dumps(
                {
                    "object": "list",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                    "model": "gemini-embedding-001",
                }
            ).encode()
            return FakeStreamContext(FakeUpstream(status_code=200, body=payload))

        fake.handler = handler
        response = await _execute(
            {"model": EMB_MODEL, "input": ["hello", "world"]},
            fake=fake,
            stores=stores,
            operation="embeddings",
            request_id="req-emb2",
        )
        assert response.status_code == 502
        assert len(fake.calls) == 1


class TestFailoverQuotaAccounting:
    async def test_429_failover_counts_both_attempts(self) -> None:
        settings = _google_settings()
        stores = _stores(settings)
        fake = FakeBackendClient()

        def handler(backend_id: str, *_args: Any, **_kwargs: Any) -> FakeStreamContext:
            if backend_id == "gm-a":
                return FakeStreamContext(FakeUpstream(status_code=429, body=b'{"error": "quota"}'))
            return FakeStreamContext(
                FakeUpstream(status_code=200, body=json.dumps(_chat_ok("via-b")).encode())
            )

        fake.handler = handler
        response = await _execute({"model": MODEL, "input": "hi"}, fake=fake, stores=stores)
        assert response.status_code == 200
        assert len(fake.calls) == 2
        assert [call[0] for call in fake.calls] == ["gm-a", "gm-b"]
        # Each dispatched attempt keeps its own quota entry.
        assert await _quota_used(stores.rate, "pa") == 1
        assert await _quota_used(stores.rate, "pb") == 1


class TestStreamFailureSchema:
    async def test_post_commit_failure_event_is_schema_valid(self) -> None:
        from foundry_router.api.adapters import get_adapter

        adapter = get_adapter("google_ai_studio")
        decoder = adapter.create_stream_decoder(logical_model=MODEL)
        prefetched = decoder.feed(_chat_chunk("hi", finish="stop"))
        assert decoder.validated

        async def chunks():  # type: ignore[no-untyped-def]
            yield b"data: {not-json}\n\n"

        context = FakeStreamContext(FakeUpstream())
        credit = MagicMock()
        credit.finalize_request = AsyncMock()
        quota = MagicMock()
        quota.finalize_request = AsyncMock()
        metrics = MagicMock()
        metrics.observe_request = AsyncMock()
        events = [
            chunk
            async for chunk in _google_stream_response(
                chunks(),
                decoder,
                prefetched,
                context,
                request_id="req-s",
                backend_id="gm-a",
                cooldown_seconds=1.0,
                model=MODEL,
                pricing={MODEL: MagicMock(input_per_million=10.0, output_per_million=30.0)},
                status_code=200,
                set_backend_cooldown=AsyncMock(),
                credit_store=credit,
                metrics_store=metrics,
                rate_limit_store=quota,
            )
        ]
        terminals = [
            json.loads(event.split(b"data: ", 1)[1])
            for event in events
            if b"response.completed" in event
            or b"response.incomplete" in event
            or b"response.failed" in event
        ]
        assert len(terminals) == 1
        failed = terminals[0]
        assert failed["type"] == "response.failed"
        assert isinstance(failed["sequence_number"], int)
        created = json.loads(events[0].split(b"data: ", 1)[1])
        assert failed["response"]["id"] == created["response"]["id"]
        assert failed["response"]["status"] == "failed"
        assert context.closed is True
        credit.finalize_request.assert_awaited_once()
