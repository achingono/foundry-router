"""Phase 10: routing log volume gating (telemetry-local, no behaviour change)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from foundry_router.routing import _emit_routing_decision, select_candidate_backend


class RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    def info(self, event: str, **kwargs) -> None:
        self.events.append(("info", event, kwargs))

    def debug(self, event: str, **kwargs) -> None:
        self.events.append(("debug", event, kwargs))

    def warning(self, event: str, **kwargs) -> None:
        self.events.append(("warning", event, kwargs))


def _candidates() -> list[dict]:
    return [{"backend_id": "b1", "health_state": "active"}]


def test_info_summary_has_no_candidate_array_success() -> None:
    logger = RecordingLogger()
    _emit_routing_decision(
        logger,
        model="m",
        operation="responses",
        request_id="r1",
        selected_backend="b1",
        reason="selected",
        estimated_request_cost_usd=0.01,
        candidates=_candidates(),
        protected_quota_fallback=False,
    )
    infos = [e for e in logger.events if e[0] == "info"]
    assert len(infos) == 1
    assert infos[0][1] == "routing_decision"
    assert "candidates" not in infos[0][2]
    # Summary keeps the decision fields.
    assert infos[0][2]["request_id"] == "r1"
    assert infos[0][2]["selected_backend"] == "b1"
    assert infos[0][2]["reason"] == "selected"
    # Detail is gated at debug, not info.
    debugs = [e for e in logger.events if e[0] == "debug"]
    assert len(debugs) == 1
    assert debugs[0][2]["candidates"] == _candidates()
    assert not [e for e in logger.events if e[0] == "warning"]


def test_info_summary_has_no_candidate_array_failure() -> None:
    logger = RecordingLogger()
    _emit_routing_decision(
        logger,
        model="m",
        operation="responses",
        request_id="r2",
        selected_backend=None,
        reason="no_usable_credit_state",
        estimated_request_cost_usd=0.02,
        candidates=_candidates(),
    )
    infos = [e for e in logger.events if e[0] == "info"]
    assert len(infos) == 1
    assert "candidates" not in infos[0][2]
    warnings = [e for e in logger.events if e[0] == "warning"]
    assert len(warnings) == 1
    assert warnings[0][2]["candidates"] == _candidates()


@pytest.mark.asyncio
async def test_select_candidate_success_emits_gated_detail() -> None:
    from foundry_router.health import BackendHealthSnapshot, BackendHealthState

    logger = RecordingLogger()
    settings = SimpleNamespace(
        models={"m": SimpleNamespace(backends={"b1": 1.0})},
        backends={"b1": SimpleNamespace(credit_metered=False, quota_group=None)},
        pricing={"m": SimpleNamespace(input_per_million=1.0, output_per_million=1.0)},
        quota_group_rate_limits={},
        min_credit_reserve_usd=0.0,
        min_credit_reserve_percent=0.0,
        reservation_max_age_seconds=900.0,
        protected_emergency_fallback=False,
    )

    class Health:
        async def snapshot_backend_health(self, ids):
            return {i: BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0) for i in ids}

    class Credit:
        async def sync_from_settings(self, s):
            return None

        async def finalize_request(self, *a, **k):
            return None

    result = await select_candidate_backend(
        settings,
        "m",
        operation="responses",
        body={"input": "hi"},
        request_id="req-1",
        health_store=Health(),
        credit_store=Credit(),
        logger=logger,
        rate_limit_store=None,
    )
    assert result.backend_id == "b1"
    infos = [e for e in logger.events if e[0] == "info" and e[1] == "routing_decision"]
    assert infos and all("candidates" not in e[2] for e in infos)
    assert [e for e in logger.events if e[0] == "debug"]
