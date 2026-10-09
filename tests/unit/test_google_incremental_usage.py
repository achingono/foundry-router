"""Incremental usage must retain maxima across fragmentation and cancelled delivery."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_incremental_usage as incremental
from google_live_budget import BudgetLedger


def usage(prompt=7, output=20, total=27, thought=10):
    return {
        "choices": [],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": output,
            "total_tokens": total,
            "completion_tokens_details": {"reasoning_tokens": thought},
        },
    }


def frame(event):
    return b"data: " + json.dumps(event).encode() + b"\n\n"


def test_fragmented_multiline_terminal_usage_requires_protocol_end_and_eof():
    observer = incremental.IncrementalUsage()
    wire = b'data: {"choices": [],\r\ndata: "usage": {"prompt_tokens":7,"completion_tokens":20,"total_tokens":27}}\r\n\r\n'
    for value in wire:
        observer.feed(bytes([value]))
    assert observer.maximum_tokens == 27 and not observer.terminal_usage
    observer.feed(frame({"choices": [{"finish_reason": "stop"}]}))
    observer.feed(b"data: [DONE]\n\n")
    assert not observer.terminal_usage
    observer.finish()
    assert observer.terminal_usage and not observer.invalid


def test_partial_usage_and_cancel_never_inferred_terminal():
    observer = incremental.IncrementalUsage()
    observer.feed(frame({"choices": [], "usage": {"prompt_tokens": 8}}))
    assert observer.maximum_tokens == 8 and not observer.terminal_usage
    observer.finish()
    assert not observer.terminal_usage


@pytest.mark.parametrize(
    "event",
    [
        usage(prompt=65, output=1, total=66, thought=0),
        usage(prompt=1, output=1025, total=1026, thought=0),
        usage(prompt=1, output=1, total=1100, thought=0),
    ],
)
def test_any_dimension_overrun_retained(event):
    observer = incremental.IncrementalUsage()
    observer.feed(frame(event))
    assert observer.overrun and observer.maximum_tokens > 0


def test_nonmonotonic_usage_invalid_and_never_lowers_maximum():
    observer = incremental.IncrementalUsage()
    observer.feed(frame(usage()))
    observer.feed(frame(usage(output=10, total=17, thought=2)))
    assert observer.invalid and observer.maximum_tokens == 27
    assert observer.output_tokens == 20 and observer.thought_tokens == 10


@pytest.mark.parametrize("output", [None, 1])
def test_thought_count_is_inclusive_output_lower_bound_even_in_invalid_frame(output):
    observer = incremental.IncrementalUsage()
    event = usage(prompt=7, output=output, total=None, thought=2000)
    observer.feed(frame(event))
    observer.feed(b"data: malformed\n\n")
    assert observer.invalid and observer.overrun
    assert observer.maximum_tokens == 2007 and not observer.terminal_usage


@pytest.mark.parametrize(
    "event",
    [
        usage(prompt=True),
        usage(output=-1),
        usage(total="27"),
        usage(thought=21),
        {"choices": [], "usage": "private"},
        {"choices": [], "usage": {"completion_tokens_details": "private"}},
    ],
)
def test_malformed_usage_invalid(event):
    observer = incremental.IncrementalUsage()
    observer.feed(frame(event))
    assert observer.invalid


def test_frame_bound_covers_comments_and_whole_response(monkeypatch):
    observer = incremental.IncrementalUsage()
    monkeypatch.setattr(incremental, "MAX_FRAME_BYTES", 8)
    with pytest.raises(ValueError):
        observer.feed(b":123456789")
    assert observer.invalid
    observer = incremental.IncrementalUsage()
    monkeypatch.setattr(incremental, "MAX_GOOGLE_RESPONSE_BYTES", 10)
    with pytest.raises(ValueError):
        observer.feed(b"\n" * 11)


def test_trailing_fragment_and_data_after_done_invalid():
    observer = incremental.IncrementalUsage()
    observer.feed(b"data: partial")
    observer.finish()
    assert observer.invalid
    observer = incremental.IncrementalUsage()
    observer.feed(b"data: [DONE]\n\n")
    observer.feed(frame(usage()))
    assert observer.invalid


def ledger_fixture(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    baseline = copy.deepcopy(ledger._read())
    allowed = {("project-2", "lifecycle-2")}
    ledger.reserve("project-2", "lifecycle-2", 1088)
    return ledger, baseline, allowed


def test_monotonic_progress_keeps_full_reserve_and_halts_dimension_overrun(tmp_path):
    ledger, baseline, allowed = ledger_fixture(tmp_path)
    for total in (8, 27, 27):
        incremental.record_progress(ledger, baseline, allowed, "project-2", "lifecycle-2", total)
    state = ledger._read()["projects"]["project-2"]
    assert state["tokens"] == 1088 and state["cases"]["lifecycle-2"]["actual_tokens"] == 27
    with pytest.raises(ValueError):
        incremental.record_progress(ledger, baseline, allowed, "project-2", "lifecycle-2", 26)
    incremental.record_progress(
        ledger, baseline, allowed, "project-2", "lifecycle-2", 66, overrun=True
    )
    assert ledger._read()["projects"]["project-2"]["halted"]
    assert not ledger.can_reserve("project-2", 1088)


def test_total_overrun_adds_only_new_usage_debit(tmp_path):
    ledger, baseline, allowed = ledger_fixture(tmp_path)
    incremental.record_progress(ledger, baseline, allowed, "project-2", "lifecycle-2", 1200)
    incremental.record_progress(ledger, baseline, allowed, "project-2", "lifecycle-2", 1300)
    assert ledger._read()["projects"]["project-2"]["tokens"] == 1300


def test_unrelated_or_changed_historical_debits_refused(tmp_path):
    ledger, baseline, allowed = ledger_fixture(tmp_path)
    ledger.reserve("project-3", "unrelated", 1088)
    with pytest.raises(ValueError):
        incremental.record_progress(ledger, baseline, allowed, "project-2", "lifecycle-2", 8)


def test_historical_case_progress_forbidden(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.reserve("project-2", "historical", 1088)
    baseline = copy.deepcopy(ledger._read())
    with pytest.raises(ValueError):
        incremental.record_progress(
            ledger, baseline, {("project-2", "historical")}, "project-2", "historical", 8
        )
