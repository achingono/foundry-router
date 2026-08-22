"""Unit tests for credit estimation and reservation behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import Response

from foundry_router import credit
from foundry_router.credit import (
    CreditState,
    InMemoryCreditStore,
    calculate_cycle_window,
    estimate_request_cost,
    estimate_response_usage_cost,
    score_credit_assessment,
)


def _pricing(input_price: float = 10.0, output_price: float = 30.0):
    return {
        "gpt-4": type(
            "Pricing",
            (),
            {
                "input_per_million": input_price,
                "output_per_million": output_price,
            },
        )(),
    }


def _settings_stub() -> object:
    settings = type("SettingsStub", (), {})()
    settings.backends = {"backend_a": {}, "backend_b": {}}
    settings.backend_cycle_start_day = {"backend_a": 1, "backend_b": 1}
    settings.backend_cycle_allowance_usd = {"backend_a": 100.0, "backend_b": 200.0}
    settings.backend_initial_estimated_remaining_usd = {"backend_a": 80.0, "backend_b": 200.0}
    return settings


class TestCycleWindow:
    def test_handles_previous_month_boundary(self) -> None:
        cycle = calculate_cycle_window(datetime(2026, 3, 1, tzinfo=UTC), 15)
        assert cycle.current_cycle_start_utc == datetime(2026, 2, 15, tzinfo=UTC)
        assert cycle.next_reset_utc == datetime(2026, 3, 15, tzinfo=UTC)

    def test_handles_year_rollover(self) -> None:
        cycle = calculate_cycle_window(datetime(2027, 1, 10, tzinfo=UTC), 20)
        assert cycle.current_cycle_start_utc == datetime(2026, 12, 20, tzinfo=UTC)
        assert cycle.next_reset_utc == datetime(2027, 1, 20, tzinfo=UTC)

    def test_accepts_naive_datetime(self) -> None:
        naive_now = datetime(2026, 7, 10, tzinfo=UTC).replace(tzinfo=None)
        cycle = calculate_cycle_window(naive_now, 1)
        assert cycle.current_cycle_start_utc.tzinfo == UTC
        assert cycle.next_reset_utc.tzinfo == UTC


class TestRequestCostEstimation:
    def test_estimates_responses_default_output(self) -> None:
        estimate = estimate_request_cost(
            model="gpt-4",
            operation="responses",
            body={"input": "hello"},
            pricing=_pricing(),
        )
        assert estimate is not None
        assert estimate.output_tokens == 4096

    def test_rejects_invalid_max_output_tokens(self) -> None:
        estimate = estimate_request_cost(
            model="gpt-4",
            operation="responses",
            body={"input": "hello", "max_output_tokens": True},
            pricing=_pricing(),
        )
        assert estimate is None

    def test_estimates_embeddings_from_string_array(self) -> None:
        estimate = estimate_request_cost(
            model="gpt-4",
            operation="embeddings",
            body={"input": ["abc", "defgh"]},
            pricing=_pricing(input_price=1.0, output_price=0.0),
        )
        assert estimate is not None
        assert estimate.input_tokens == 3

    def test_walk_text_chars_nested_values_and_rejects_bytes(self) -> None:
        chars = credit._walk_text_chars({"a": ["ab", {"b": "cde"}]})
        assert chars == 5
        assert credit._walk_text_chars({"bad": b"bytes"}) == -1
        assert credit._walk_text_chars({"num": 123, "flag": True}) == 0
        assert credit._walk_text_chars({"obj": object()}) == -1


class TestResponseUsageEstimation:
    def test_extracts_prompt_completion_tokens(self) -> None:
        response = Response(
            content=b'{"usage":{"prompt_tokens":100,"completion_tokens":20}}',
            media_type="application/json",
        )
        cost = estimate_response_usage_cost(response, "gpt-4", _pricing())
        assert cost == pytest.approx(0.0016)

    def test_falls_back_to_total_tokens(self) -> None:
        response = Response(
            content=b'{"usage":{"total_tokens":50}}',
            media_type="application/json",
        )
        cost = estimate_response_usage_cost(response, "gpt-4", _pricing())
        assert cost == pytest.approx(0.0005)

    def test_invalid_or_negative_usage_returns_none(self) -> None:
        malformed = Response(content=b"{not json", media_type="application/json")
        negative = Response(
            content=b'{"usage":{"input_tokens":-1,"output_tokens":0}}',
            media_type="application/json",
        )
        assert estimate_response_usage_cost(malformed, "gpt-4", _pricing()) is None
        assert estimate_response_usage_cost(negative, "gpt-4", _pricing()) is None


class TestCreditStore:
    def test_sync_assess_and_reservation_finalize_paths(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))

        assigned = asyncio.run(
            store.try_assign_reservation(
                "req-1",
                "backend_a",
                10.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assigned is True

        asyncio.run(store.finalize_request("req-1", charge_reserved=True, charged_cost_usd=5.0))
        assessment = asyncio.run(
            store.assess(
                "backend_a",
                1.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(75.0)

    def test_finalize_without_charge_releases_only_reservation(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))
        asyncio.run(
            store.try_assign_reservation(
                "req-2",
                "backend_b",
                20.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        asyncio.run(store.finalize_request("req-2", charge_reserved=False, charged_cost_usd=None))

        assessment = asyncio.run(
            store.assess(
                "backend_b",
                1.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(200.0)

    def test_rollover_restores_cycle_allowance(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))
        snapshot = store._snapshots["backend_a"]
        snapshot.estimated_remaining_usd = 10.0
        snapshot.cycle_start_utc = datetime(2026, 1, 1, tzinfo=UTC)

        assessment = asyncio.run(
            store.assess(
                "backend_a",
                1.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
                now_utc=datetime(2026, 3, 15, tzinfo=UTC),
            )
        )
        assert assessment.available_credit_usd == pytest.approx(snapshot.cycle_allowance_usd)

    def test_assessment_states_cover_protected_and_insufficient(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))

        protected = asyncio.run(
            store.assess(
                "backend_a",
                1.0,
                min_credit_reserve_usd=90.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert protected.state == CreditState.PROTECTED

        insufficient = asyncio.run(
            store.assess(
                "backend_a",
                500.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert insufficient.state == CreditState.INSUFFICIENT_CAPACITY

    def test_apply_reconciled_remaining_updates_known_backends_only(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))
        updated = asyncio.run(
            store.apply_reconciled_remaining(
                {
                    "backend_a": 40.0,
                    "unknown_backend": 10.0,
                }
            )
        )
        assert updated == 1
        assessment = asyncio.run(
            store.assess(
                "backend_a",
                1.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(40.0)

    def test_apply_reconciled_remaining_clamps_to_cycle_allowance(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))
        updated = asyncio.run(store.apply_reconciled_remaining({"backend_a": 500.0}))
        assert updated == 1

        assessment = asyncio.run(
            store.assess(
                "backend_a",
                1.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        assert assessment.available_credit_usd == pytest.approx(100.0)

    def test_live_snapshot_includes_reservations_and_cycle_bounds(self) -> None:
        store = InMemoryCreditStore()
        settings = _settings_stub()

        asyncio.run(store.sync_from_settings(settings))
        asyncio.run(
            store.try_assign_reservation(
                "req-live",
                "backend_a",
                5.0,
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
            )
        )
        live = asyncio.run(
            store.live_snapshot(
                ["backend_a", "unknown_backend"],
                min_credit_reserve_usd=0.0,
                min_credit_reserve_percent=0.0,
                now_utc=datetime(2026, 6, 10, tzinfo=UTC),
            )
        )

        assert "unknown_backend" not in live
        assert live["backend_a"].active_reservations == 1
        assert live["backend_a"].reserved_inflight_usd == pytest.approx(5.0)
        assert live["backend_a"].next_reset_utc > live["backend_a"].current_cycle_start_utc


class TestScoring:
    def test_scoring_prefers_active_usable_with_headroom(self) -> None:
        strong = score_credit_assessment(
            state=CreditState.USABLE,
            is_health_active=True,
            is_error_cooldown=False,
            available_credit_usd=100.0,
            estimated_request_cost_usd=1.0,
            projected_unused_credit_usd=30.0,
            cycle_allowance_usd=100.0,
        )
        weak = score_credit_assessment(
            state=CreditState.CONSERVATION,
            is_health_active=False,
            is_error_cooldown=True,
            available_credit_usd=1.0,
            estimated_request_cost_usd=10.0,
            projected_unused_credit_usd=0.0,
            cycle_allowance_usd=100.0,
        )
        assert strong > weak
