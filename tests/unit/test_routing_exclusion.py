"""Persistent per-combination failure exclusion: predicate, store and routing."""

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response
from fastapi.responses import StreamingResponse

from foundry_router.config import Settings
from foundry_router.credit import CreditAssessment, CreditState
from foundry_router.forwarding import BackendRequestResult
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore
from foundry_router.routing import execute_with_single_failover, select_candidate_backend
from foundry_router.routing.exclusion import (
    EXCLUSION_THRESHOLD,
    CombinationExclusionStore,
    classify_exclusion_event,
    exclusion_stream_mode,
)


@pytest.mark.parametrize(
    ("status", "retryable", "confirmed", "expected"),
    [
        (500, True, False, True),
        (502, True, False, True),
        (503, True, False, True),
        (599, False, False, True),
        (404, False, False, True),
        (429, True, False, False),
        (400, False, False, False),
        (422, False, False, False),
        (200, False, False, False),
        (503, True, True, False),
        (404, False, True, False),
        (None, True, False, False),
        ("503", True, False, False),
        (True, True, False, False),
    ],
)
def test_classify_exclusion_event_truth_table(status, retryable, confirmed, expected):
    assert (
        classify_exclusion_event(
            status, retryable_failure=retryable, confirmed_pre_dispatch=confirmed
        )
        is expected
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"stream": True}, True),
        ({"stream": False}, False),
        ({}, False),
        (None, False),
        ("x", False),
    ],
)
def test_exclusion_stream_mode_strict_bool(body, expected):
    assert exclusion_stream_mode(body) is expected


async def test_store_threshold_decay_expiry_and_probe():
    store = CombinationExclusionStore()
    key = ("b", "responses", False)
    assert await store.record_attempt(*key, success=False, countable_failure=True) is None
    assert await store.record_attempt(*key, success=False, countable_failure=True) is None
    assert await store.record_attempt(*key, success=False, countable_failure=True) == "entered"
    filtered = await store.filter_candidates(["b"], "responses", False)
    assert filtered.eligible == [] or filtered.probe_backend_id == "b"
    assert filtered.excluded["b"]["consecutive_failures"] == 3
    # Non-countable outcomes never move the counter.
    assert await store.record_attempt(*key, success=False, countable_failure=False) is None
    snapshot = await store.snapshot()
    assert snapshot[key]["consecutive_failures"] == 3


async def test_store_decay_accumulates_bursty_flap():
    # Bursty fail/fail/success cycles net +1 per cycle, so a chronic ~67%
    # failure pattern still enters. Full-clear-on-success would sit at 2 here.
    store = CombinationExclusionStore()
    key = ("b", "responses", False)
    for _ in range(2):
        await store.record_attempt(*key, success=False, countable_failure=True)
    assert await store.record_attempt(*key, success=True, countable_failure=False) == "decayed"
    assert await store.record_attempt(*key, success=False, countable_failure=True) is None
    assert await store.record_attempt(*key, success=False, countable_failure=True) == "entered"


async def test_store_expiry_resets_and_probe_picks_oldest(monkeypatch):
    store = CombinationExclusionStore()
    now = time.monotonic()
    moments = [now]
    monkeypatch.setattr(time, "monotonic", lambda: moments[0])
    for backend in ("old", "new"):
        for _ in range(EXCLUSION_THRESHOLD):
            await store.record_attempt(
                backend, "responses", False, success=False, countable_failure=True
            )
        moments[0] += 10
    filtered = await store.filter_candidates(["old", "new"], "responses", False)
    assert filtered.eligible == ["old", "new"] and filtered.probe_backend_id == "old"
    moments[0] += 1800 + 11
    filtered = await store.filter_candidates(["old", "new"], "responses", False)
    assert filtered.eligible == ["old", "new"] and filtered.probe_backend_id is None
    snapshot = await store.snapshot()
    assert snapshot == {}


async def test_store_concurrent_records_share_lock():
    # Ten concurrent in-flight failures: the first three enter exclusion and the
    # remainder refresh (rather than accumulate beyond) the window, with no
    # lost updates or lock errors. A later success still decays.
    store = CombinationExclusionStore()
    await asyncio.gather(
        *(
            store.record_attempt("b", "responses", True, success=False, countable_failure=True)
            for _ in range(10)
        )
    )
    snapshot = await store.snapshot()
    assert snapshot[("b", "responses", True)]["consecutive_failures"] == EXCLUSION_THRESHOLD
    assert snapshot[("b", "responses", True)]["excluded"] is True
    assert (
        await store.record_attempt("b", "responses", True, success=True, countable_failure=False)
        == "cleared"
    )


def _google_settings() -> Settings:
    backends = {
        "gm-a": {
            "provider": "google_ai_studio",
            "endpoint": "https://generativelanguage.googleapis.com",
            "credential": "synthetic-a",
            "deployment": "gemini-2.5-flash",
            "quota_group": "pa",
            "credit_metered": False,
        },
        "gm-b": {
            "provider": "google_ai_studio",
            "endpoint": "https://generativelanguage.googleapis.com",
            "credential": "synthetic-b",
            "deployment": "gemini-2.5-flash",
            "quota_group": "pb",
            "credit_metered": False,
        },
    }
    return Settings(
        backends_json=json.dumps(backends),
        models_json=json.dumps({"m": {"backends": {"gm-a": 2.0, "gm-b": 1.0}}}),
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json=json.dumps({"m": {"input_per_million": 0, "output_per_million": 0}}),
        quota_group_rate_limits_json=json.dumps(
            {"pa": {"rpm": 100, "tpm": 100000}, "pb": {"rpm": 100, "tpm": 100000}}
        ),
    )


def _selection_stores():
    metrics = MagicMock()
    metrics.observe_request = AsyncMock()
    return SimpleNamespace(
        health=InMemoryHealthStore(),
        credit=_credit_stub(),
        metrics=metrics,
        rate=InMemoryRateLimitStore(),
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
    )


class _CreditStub:
    async def sync_from_settings(self, _settings: Any) -> None:
        return None

    async def assess(self, _backend_id: str, cost: float, **_kwargs: Any) -> Any:
        return CreditAssessment(CreditState.USABLE, 100.0, 50.0, cost, 100.0)

    async def try_assign_reservation(self, *_args: Any, **_kwargs: Any) -> bool:
        return True

    async def finalize_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _credit_stub() -> Any:
    return _CreditStub()


def _api_error(status: int, message: str, _code: str) -> Response:
    return Response(content=message, status_code=status)


async def _select(settings, stores, body, **kwargs):
    return await select_candidate_backend(
        settings,
        "m",
        operation="responses",
        body=body,
        request_id="req-exclusion",
        health_store=stores.health,
        credit_store=stores.credit,
        logger=stores.logger,
        rate_limit_store=stores.rate,
        **kwargs,
    )


async def test_selection_filters_excluded_stream_only():
    settings = _google_settings()
    stores = _selection_stores()
    store = CombinationExclusionStore()
    body = {"model": "m", "input": "hello", "stream": True}
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt("gm-a", "responses", True, success=False, countable_failure=True)
    selected = await _select(settings, stores, body, exclusion_store=store)
    assert selected.backend_id == "gm-b"
    selected = await _select(
        settings, stores, {"model": "m", "input": "hello"}, exclusion_store=store
    )
    assert selected.backend_id == "gm-a"


async def test_selection_probe_marks_telemetry_when_all_excluded():
    settings = _google_settings()
    seen = []

    class ProbeLogger:
        def info(self, event, **fields):
            seen.append((event, fields))

    stores = _selection_stores()
    stores.logger = ProbeLogger()
    store = CombinationExclusionStore()
    body = {"model": "m", "input": "hello"}
    for backend in ("gm-a", "gm-b"):
        for _ in range(EXCLUSION_THRESHOLD):
            await store.record_attempt(
                backend, "responses", False, success=False, countable_failure=True
            )
    selected = await _select(settings, stores, body, exclusion_store=store)
    assert selected.backend_id in {"gm-a", "gm-b"}
    decisions = [fields for event, fields in seen if event == "routing_decision"]
    assert decisions and decisions[-1]["reason"] == "combination_excluded_probe"
    assert decisions[-1]["combination_excluded_probe"] is True


async def test_selection_without_store_is_unchanged():
    settings = _google_settings()
    stores = _selection_stores()
    selected = await _select(settings, stores, {"model": "m", "input": "hello"})
    assert selected.backend_id == "gm-a"


def _terminal_result(status_code: int, **kwargs: Any) -> BackendRequestResult:
    return BackendRequestResult(Response(content="synthetic", status_code=status_code), **kwargs)


async def test_execute_records_and_routes_around_sick_combination():
    settings = _google_settings()
    stores = _selection_stores()
    # No rate-limit store: quota-headroom balancing would otherwise interleave
    # backends and make the exclusion threshold unreachable deterministically.
    stores.rate = None
    store = CombinationExclusionStore()
    metrics = InMemoryMetricsStore()
    calls = []

    async def execute_backend(backend_id: str, **_kwargs: Any) -> BackendRequestResult:
        calls.append(backend_id)
        if backend_id == "gm-a":
            return _terminal_result(503, retryable_failure=False)
        return _terminal_result(200, retryable_failure=False)

    body = {"model": "m", "input": "hello"}
    common = {
        "operation": "responses",
        "body": body,
        "health_store": stores.health,
        "credit_store": stores.credit,
        "metrics_store": metrics,
        "logger": stores.logger,
        "api_error": _api_error,
        "rate_limit_store": stores.rate,
        "exclusion_store": store,
    }

    async def finalize(*_args: Any, **_kwargs: Any) -> None:
        return None

    for attempt in range(EXCLUSION_THRESHOLD):
        response = await execute_with_single_failover(
            settings,
            "m",
            execute_backend=execute_backend,
            finalize_non_streaming_credit=finalize,
            request_id=f"req-exclusion-exec-{attempt}",
            **common,
        )
        assert response.status_code in {200, 503}
    assert calls.count("gm-a") == EXCLUSION_THRESHOLD
    response = await execute_with_single_failover(
        settings,
        "m",
        execute_backend=execute_backend,
        finalize_non_streaming_credit=finalize,
        request_id="req-exclusion-exec-final",
        **common,
    )
    assert response.status_code == 200
    assert calls[-1] == "gm-b"
    rendered = await metrics.render_prometheus(
        backend_health_states={}, backend_available_credit_usd={}
    )
    assert "combination_exclusion_entries_total" in rendered


async def test_streaming_handoff_decays_without_counting():
    store = CombinationExclusionStore()
    await store.record_attempt("b", "responses", True, success=False, countable_failure=True)
    await store.record_attempt("b", "responses", True, success=False, countable_failure=True)
    from foundry_router.routing import _record_combination_attempt

    async def _body():
        yield b""

    result = BackendRequestResult(StreamingResponse(_body()), retryable_failure=False)
    await _record_combination_attempt(
        store, None, backend_id="b", operation="responses", stream_mode=True, result=result
    )
    snapshot = await store.snapshot()
    assert snapshot[("b", "responses", True)]["consecutive_failures"] == 1


async def test_admin_snapshot_lists_logical_models():
    settings = _google_settings()
    store = CombinationExclusionStore()
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt(
            "gm-a", "responses", False, success=False, countable_failure=True
        )
    snapshot = await store.snapshot()
    assert snapshot[("gm-a", "responses", False)]["excluded"] is True
    affected = sorted(
        model_name for model_name, pool in settings.models.items() if "gm-a" in pool.backends
    )
    assert affected == ["m"]


async def test_probe_success_clears_exclusion_and_window():
    store = CombinationExclusionStore()
    key = ("b", "responses", False)
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt(*key, success=False, countable_failure=True)
    filtered = await store.filter_candidates(["b"], "responses", False)
    assert filtered.probe_backend_id == "b"
    assert await store.record_attempt(*key, success=True, countable_failure=False) == "cleared"
    filtered = await store.filter_candidates(["b"], "responses", False)
    assert filtered.probe_backend_id is None and filtered.eligible == ["b"]
    assert await store.snapshot() == {}


async def test_expired_outcome_starts_a_new_epoch(monkeypatch):
    clock = SimpleNamespace(monotonic=lambda: 100.0, time=lambda: 1000.0)
    monkeypatch.setattr("foundry_router.routing.exclusion.time", clock)
    store = CombinationExclusionStore()
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt("b", "responses", False, success=False, countable_failure=True)
    clock.monotonic = lambda: 2000.0
    await store.record_attempt("b", "responses", False, success=False, countable_failure=True)
    snapshot = await store.snapshot()
    assert snapshot[("b", "responses", False)]["consecutive_failures"] == 1
    assert snapshot[("b", "responses", False)]["excluded_until_wall"] is None


async def test_probe_claim_is_exclusive_and_stale_outcomes_ignored():
    store = CombinationExclusionStore()
    ordinary = await store.admit("b", "responses", False)
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt("b", "responses", False, success=False, countable_failure=True)
    await store.record_attempt(
        "b", "responses", False, success=True, countable_failure=False, ticket=ordinary
    )
    assert (await store.snapshot())[("b", "responses", False)]["excluded"]
    claims = await asyncio.gather(
        *(store.admit("b", "responses", False, probe=True) for _ in range(10))
    )
    tickets = [ticket for ticket in claims if ticket is not None]
    assert len(tickets) == 1
    await store.release(tickets[0])
    replacement = await store.admit("b", "responses", False, probe=True)
    assert replacement is not None
    await store.record_attempt(
        "b", "responses", False, success=True, countable_failure=False, ticket=tickets[0]
    )
    assert (await store.snapshot())[("b", "responses", False)]["excluded"]
    assert (
        await store.record_attempt(
            "b", "responses", False, success=True, countable_failure=False, ticket=replacement
        )
        == "cleared"
    )


async def test_reset_invalidates_active_admission():
    store = CombinationExclusionStore()
    ticket = await store.admit("b", "responses", False)
    await store.reset()
    await store.record_attempt(
        "b", "responses", False, success=False, countable_failure=True, ticket=ticket
    )
    assert await store.snapshot() == {}


async def test_probe_uses_credit_admissible_alternative():
    settings = _google_settings()
    for backend in settings.backends.values():
        backend.credit_metered = True
    stores = _selection_stores()

    class ProtectedOldest(_CreditStub):
        async def assess(self, backend_id, cost, **_kwargs):
            return CreditAssessment(
                CreditState.PROTECTED if backend_id == "gm-a" else CreditState.USABLE,
                0 if backend_id == "gm-a" else 100,
                50,
                cost,
                100,
            )

    stores.credit = ProtectedOldest()
    store = CombinationExclusionStore()
    for backend in ("gm-a", "gm-b"):
        for _ in range(EXCLUSION_THRESHOLD):
            await store.record_attempt(
                backend, "responses", False, success=False, countable_failure=True
            )
    selected = await _select(
        settings, stores, {"model": "m", "input": "hello"}, exclusion_store=store
    )
    assert selected.backend_id == "gm-b"
    assert selected.admission_ticket.probe_token is not None
    await store.release(selected.admission_ticket)


async def test_probe_failure_rearms_window_without_new_entry(monkeypatch):
    clock = SimpleNamespace(monotonic=lambda: 100.0, time=lambda: 1000.0)
    monkeypatch.setattr("foundry_router.routing.exclusion.time", clock)
    store = CombinationExclusionStore()
    key = ("b", "responses", False)
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt(*key, success=False, countable_failure=True)
    before = await store.snapshot()
    assert before[key]["excluded"] is True
    clock.monotonic = lambda: 200.0
    clock.time = lambda: 1100.0
    assert await store.record_attempt(*key, success=False, countable_failure=True) is None
    after = await store.snapshot()
    assert after[key]["excluded"] is True
    assert after[key]["consecutive_failures"] == EXCLUSION_THRESHOLD
    assert after[key]["excluded_until_wall"] == 2900.0
    assert before[key]["excluded_until_wall"] == 2800.0
    assert await store.snapshot() != {}


async def test_excluded_until_wall_is_expiry_not_entry(monkeypatch):
    clock = SimpleNamespace(monotonic=lambda: 100.0, time=lambda: 1000.0)
    monkeypatch.setattr("foundry_router.routing.exclusion.time", clock)
    store = CombinationExclusionStore()
    key = ("b", "responses", False)
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt(*key, success=False, countable_failure=True)
    snapshot = await store.snapshot()
    expiry = snapshot[key]["excluded_until_wall"]
    assert expiry == 2800.0


async def test_cleared_transition_emits_reset_metric():
    from foundry_router.routing import _record_combination_attempt

    store = CombinationExclusionStore()
    metrics = InMemoryMetricsStore()
    key = ("b", "responses", False)
    for _ in range(EXCLUSION_THRESHOLD):
        await store.record_attempt(*key, success=False, countable_failure=True)
    failed = SimpleNamespace(
        response=SimpleNamespace(status_code=503),
        retryable_failure=True,
        confirmed_pre_dispatch=False,
    )
    await _record_combination_attempt(
        store, metrics, backend_id="b", operation="responses", stream_mode=False, result=failed
    )
    ok = SimpleNamespace(
        response=SimpleNamespace(status_code=200),
        retryable_failure=False,
        confirmed_pre_dispatch=False,
    )
    await _record_combination_attempt(
        store, metrics, backend_id="b", operation="responses", stream_mode=False, result=ok
    )
    rendered = await metrics.render_prometheus(
        backend_health_states={}, backend_available_credit_usd={}
    )
    assert "combination_exclusion_entries_total" in rendered
    assert "combination_exclusion_resets_total" in rendered
    assert await store.snapshot() == {}
