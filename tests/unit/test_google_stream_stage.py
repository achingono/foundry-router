"""Stage gates must retain ambiguous consumption and stop without fetching more keys."""

import copy
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_stream_stage as stage
from google_live_budget import BudgetLedger


def fixture(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    baseline = copy.deepcopy(ledger._read())
    (tmp_path / "ledger-baseline.json").write_text(json.dumps(baseline))
    return ledger


def failed(case, **kwargs):
    result = {
        **case,
        "model": stage.MODEL,
        "status": "failed",
        "http_status": 502,
        "provider_http_status": 429,
        "dispatches": 1,
        "actual_tokens": None,
        "input_tokens": None,
        "output_tokens": None,
        "thought_tokens": None,
        "synthetic_debit_usd": 1.03,
        "settlement_kind": "conservative_reservation",
        "first_upstream_chunk_seconds": None,
        "first_public_text_seconds": None,
        "elapsed_seconds": 0.1,
        "error_category": None,
    }
    result.update(dict.fromkeys(stage.BOOL_RESULT_KEYS, False))
    result.update(kwargs)
    return result


@pytest.mark.parametrize(
    "mutation",
    [
        {"private": "secret"},
        {"status": "passed"},
        {"actual_tokens": True},
        {"provider_http_status": 999},
        {"elapsed_seconds": 31},
        {"error_category": "private-exception"},
        {"natural_cleanup": 1},
    ],
)
def test_result_mutations_rejected(tmp_path, mutation):
    ledger = fixture(tmp_path)
    case = stage.cases()[0]
    ledger.reserve(case["project"], case["case_id"], 1088)
    with pytest.raises(ValueError):
        stage.validate_result(failed(case, **mutation), case, ledger._read())


def test_failed_project_halts_later_cases_and_replay(tmp_path):
    ledger = fixture(tmp_path)
    calls = []

    async def runner(*, case, reserve, progress, **_kwargs):
        calls.append(case["case_id"])
        reserve()
        result = failed(case)
        progress({key: result[key] for key in stage.PROGRESS_KEYS})
        return result

    options = {
        "directory": tmp_path,
        "ledger_path": ledger.path,
        "credentials": ["synthetic"] * 5,
        "transport_factory": lambda: httpx.MockTransport(lambda _: None),
        "runner": runner,
    }
    result = stage.execute("synthetic", **options)
    assert len(result["attempts"]) == len(calls) == 4
    assert all("cancel" not in identity and "reasoning" not in identity for identity in calls)
    stage.execute("synthetic", **options)
    assert len(calls) == 4


def test_missing_saved_result_halts_consumed_project(tmp_path):
    ledger = fixture(tmp_path)
    first = stage.cases()[0]
    ledger.reserve(first["project"], first["case_id"], 1088)
    calls = []

    async def runner(*, case, reserve, **_kwargs):
        calls.append(case["project"])
        reserve()
        return failed(case)

    result = stage.execute(
        "synthetic",
        directory=tmp_path,
        ledger_path=ledger.path,
        credentials=["synthetic"] * 5,
        runner=runner,
        transport_factory=lambda: httpx.MockTransport(lambda _: None),
    )
    assert "project-2" not in calls and len(result["attempts"]) == 3


def test_partial_overrun_halts_entire_stage_even_if_no_final_result(tmp_path):
    ledger = fixture(tmp_path)
    calls = []

    async def runner(*, case, reserve, progress, **_kwargs):
        calls.append(case["project"])
        reserve()
        result = failed(
            case, actual_tokens=2007, input_tokens=7, thought_tokens=2000, budget_overrun=True
        )
        progress({key: result[key] for key in stage.PROGRESS_KEYS})
        raise ValueError("synthetic interruption")

    options = {
        "directory": tmp_path,
        "ledger_path": ledger.path,
        "credentials": ["synthetic"] * 5,
        "runner": runner,
        "transport_factory": lambda: httpx.MockTransport(lambda _: None),
    }
    with pytest.raises(ValueError):
        stage.execute("synthetic", **options)
    assert ledger._read()["projects"]["project-2"]["tokens"] == 2007
    assert stage.execute("synthetic", **options)["attempts"] == []
    assert calls == ["project-2"]


@pytest.mark.parametrize("total,dimension_overrun", [(2007, False), (66, True), (10**100, False)])
def test_ledger_only_overrun_crash_window_stops_all_other_projects(
    tmp_path, total, dimension_overrun
):
    from google_incremental_usage import record_progress

    ledger = fixture(tmp_path)
    baseline = ledger._read()
    first = stage.cases()[0]
    ledger.reserve(first["project"], first["case_id"], 1088)
    allowed = {(case["project"], case["case_id"]) for case in stage.cases()}
    record_progress(
        ledger,
        baseline,
        allowed,
        first["project"],
        first["case_id"],
        total,
        overrun=dimension_overrun,
    )
    calls = []
    result = stage.execute(
        "synthetic",
        directory=tmp_path,
        ledger_path=ledger.path,
        credentials=None,
        transport_factory=lambda: calls.append(True),
    )
    assert result["attempts"] == [] and not calls


def test_large_numeric_usage_progress_retained_before_stage_halt(tmp_path):
    ledger = fixture(tmp_path)
    calls = []

    async def runner(*, case, reserve, progress, **_kwargs):
        calls.append(True)
        reserve()
        result = failed(case, actual_tokens=10**100, output_tokens=10**100, budget_overrun=True)
        progress({key: result[key] for key in stage.PROGRESS_KEYS})
        return result

    result = stage.execute(
        "synthetic",
        directory=tmp_path,
        ledger_path=ledger.path,
        credentials=["synthetic"] * 5,
        runner=runner,
        transport_factory=lambda: httpx.MockTransport(lambda _: None),
    )
    assert len(result["attempts"]) == len(calls) == 1
    assert ledger._read()["projects"]["project-2"]["tokens"] == 10**100


def test_saved_pass_with_corrupt_output_or_debit_cannot_enable_cases(tmp_path):
    ledger = fixture(tmp_path)
    case = stage.cases()[0]
    ledger.reserve(case["project"], case["case_id"], 1088)
    ledger.record_usage(case["project"], case["case_id"], 9)
    valid = failed(
        case,
        status="passed",
        http_status=200,
        provider_http_status=200,
        actual_tokens=9,
        input_tokens=7,
        output_tokens=2,
        terminal_usage=True,
        public_completed=True,
        public_text_before_upstream_eof=True,
        natural_cleanup=True,
        usage_matches=True,
        settlement_matches=True,
        synthetic_debit_usd=0.009,
        settlement_kind="observed_usage",
    )
    stage.validate_result(valid, case, ledger._read())
    for mutation in (
        {"output_tokens": 1025},
        {"input_tokens": 65},
        {"thought_tokens": 3},
        {"synthetic_debit_usd": 0.1},
        {"settlement_kind": "conservative_reservation"},
    ):
        with pytest.raises(ValueError):
            stage.validate_result({**valid, **mutation}, case, ledger._read())
