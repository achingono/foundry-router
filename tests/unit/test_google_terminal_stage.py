"""Stop-attached usage needs exact terminal shape, and cancellation needs new proof."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_terminal_stage as stage
from google_incremental_usage import IncrementalUsage
from google_stream_stage import read_file, validate_result

from tests.unit.test_google_incremental_usage import frame, usage


def stop(delta=None):
    return {"index": 0, "delta": {} if delta is None else delta, "finish_reason": "stop"}


def finish(observer):
    observer.feed(b"data: [DONE]\n\n")
    observer.finish()


def test_complete_usage_attached_stop_choice_accepts_with_done_eof():
    observer = IncrementalUsage()
    value = usage()
    value["choices"] = [stop()]
    observer.feed(frame(value))
    assert not observer.terminal_usage
    finish(observer)
    assert observer.terminal_usage and observer.final_usage_shape == "stop_choice"


@pytest.mark.parametrize(
    "choice",
    [
        stop({"content": "meaningful"}),
        stop({"role": "assistant"}),
        stop({"tool_calls": [{"id": "private"}]}),
        stop({"extra_content": {"private": "state"}}),
        {**stop(), "index": 1},
        {**stop(), "index": True},
        {**stop(), "finish_reason": "length"},
    ],
)
def test_noninert_or_wrong_stop_never_terminal(choice):
    observer = IncrementalUsage()
    value = usage()
    value["choices"] = [choice]
    observer.feed(frame(value))
    finish(observer)
    assert not observer.terminal_usage and observer.final_usage_shape == "absent"


def test_multiple_stop_choices_never_terminal():
    observer = IncrementalUsage()
    value = usage()
    value["choices"] = [stop(), stop()]
    observer.feed(frame(value))
    finish(observer)
    assert not observer.terminal_usage


def test_meaningful_output_after_stop_invalidates_terminal():
    observer = IncrementalUsage()
    value = usage()
    value["choices"] = [stop()]
    observer.feed(frame(value))
    observer.feed(
        frame({"choices": [{"index": 0, "delta": {"content": "later"}, "finish_reason": None}]})
    )
    finish(observer)
    assert observer.invalid and not observer.terminal_usage


def test_duplicate_final_usage_invalid():
    observer = IncrementalUsage()
    value = usage()
    value["choices"] = [stop()]
    observer.feed(frame(value))
    observer.feed(frame(usage()))
    finish(observer)
    assert observer.invalid and not observer.terminal_usage


def test_cancellation_prerequisite_requires_new_normal_success():
    cancel = stage.cases()[-1]
    assert not stage.prerequisite(cancel, {})
    assert not stage.prerequisite(cancel, {"normal": {"status": "failed", "cancel": False}})
    assert stage.prerequisite(cancel, {"normal": {"status": "passed", "cancel": False}})
    assert all(stage.prerequisite(case, {}) for case in stage.cases()[:-1])


@pytest.mark.parametrize(
    "mutation",
    [
        {"stop_seen": 1},
        {"done_seen": "private"},
        {"upstream_eof": None},
        {"final_usage_shape": "private-state"},
        {"private": "value"},
    ],
)
def test_terminal_progress_safe_schema(mutation):
    from google_stream_stage import PROGRESS_KEYS

    value = dict.fromkeys(PROGRESS_KEYS, None)
    value.update(dispatches=0, budget_overrun=False, usage_invalid=False, **stage.INITIAL_TERMINAL)
    with pytest.raises(ValueError):
        stage.progress_validator({**value, **mutation})


def test_historical_six_results_unchanged_and_still_readable():
    root = Path(__file__).resolve().parents[2]
    directory = root / "docs/plans/google-compatible-stream-lifecycle"
    current = read_file(
        root / "docs/plans/google-ai-routing-order/ledger-native-text-2026-10-08.json"
    )
    results = read_file(directory / "results.json")
    for value in results["attempts"]:
        case = {key: value[key] for key in ("case_id", "project", "stream", "cancel", "prompt")}
        validate_result(copy.deepcopy(value), case, current)
    assert len(results["attempts"]) == 6
    assert sum(value["status"] == "failed" for value in results["attempts"]) == 4
    assert all("final_usage_shape" not in value for value in results["attempts"])


def test_exact_new_case_roster():
    assert [case["project"] for case in stage.cases()] == [
        "project-3",
        "project-4",
        "project-5",
        "project-2",
    ]
    assert sum(case["cancel"] for case in stage.cases()) == 1
    assert len(json.dumps(stage.cases())) < 4096


def test_new_stage_withholds_cancel_if_all_normal_cases_fail(tmp_path):
    import httpx

    from tests.unit.test_google_stream_stage import failed, fixture

    ledger = fixture(tmp_path)
    calls = []

    async def runner(*, case, reserve, progress, **_kwargs):
        calls.append(case["case_id"])
        reserve()
        result = {**failed(case), **stage.INITIAL_TERMINAL}
        from google_stream_stage import PROGRESS_KEYS

        progress({key: result[key] for key in PROGRESS_KEYS | stage.TERMINAL_KEYS})
        return result

    options = {
        "directory": tmp_path,
        "ledger_path": ledger.path,
        "credentials": ["synthetic"] * 5,
        "case_runner": runner,
        "transport_factory": lambda: httpx.MockTransport(lambda _: None),
    }
    results = stage.run("synthetic", **options)
    assert len(results["attempts"]) == len(calls) == 3
    assert not any("cancel" in identity for identity in calls)
    assert ledger._read()["projects"]["project-2"]["requests"] == 1
    stage.run("synthetic", **options)
    assert len(calls) == 3


def test_new_valid_normal_enables_single_conditional_cancel(tmp_path):
    import httpx
    from google_stream_stage import PROGRESS_KEYS

    from tests.unit.test_google_stream_stage import failed, fixture

    ledger = fixture(tmp_path)
    calls = []

    async def runner(*, case, reserve, progress, **_kwargs):
        calls.append(case["case_id"])
        reserve()
        result = {**failed(case), **stage.INITIAL_TERMINAL}
        if not case["cancel"]:
            result.update(
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
                stop_seen=True,
                done_seen=True,
                upstream_eof=True,
                final_usage_shape="stop_choice",
            )
        progress({key: result[key] for key in PROGRESS_KEYS | stage.TERMINAL_KEYS})
        return result

    options = {
        "directory": tmp_path,
        "ledger_path": ledger.path,
        "credentials": ["synthetic"] * 5,
        "case_runner": runner,
        "transport_factory": lambda: httpx.MockTransport(lambda _: None),
    }
    results = stage.run("synthetic", **options)
    assert len(results["attempts"]) == len(calls) == 4
    assert calls[-1] == "t09-cancel-project-2"
    stage.run("synthetic", **options)
    assert len(calls) == 4
