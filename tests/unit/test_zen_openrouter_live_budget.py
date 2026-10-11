"""Offline ledger and manifest gates for the Zen/OpenRouter live harness."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import zen_openrouter_live_budget as budget


def manifest(**overrides):
    base = {
        "version": 1,
        "run": budget.RUN_ID,
        "zen_model": "gpt-5.4",
        "openrouter_model": "organization/model",
        "openrouter_embedding_model": "organization/embed",
        "input_per_million": 1000.0,
        "output_per_million": 1000.0,
        "cases": list(budget.CASE_IDS),
        "case_timeout_seconds": budget.CASE_TIMEOUT_SECONDS,
        "max_observed_bytes": budget.MAX_OBSERVED_BYTES,
        "max_output_tokens": budget.MAX_OUTPUT_TOKENS,
    }
    base.update(overrides)
    return base


def test_manifest_accepts_exact_five_case_binding():
    summary = budget.validate_manifest(manifest())
    assert summary["cases"] == list(budget.CASE_IDS)
    assert summary["max_dispatches"] == 5


@pytest.mark.parametrize(
    "override",
    [
        {"version": 2},
        {"run": "other"},
        {"zen_model": "  "},
        {"openrouter_model": ""},
        {"openrouter_embedding_model": None},
        {"input_per_million": 0},
        {"output_per_million": -1},
        {"input_per_million": True},
        {"cases": ["zen-nonstream"]},
        {"cases": [*list(budget.CASE_IDS), "extra"]},
        {"case_timeout_seconds": 30},
        {"max_output_tokens": 1024},
    ],
)
def test_manifest_mutations_rejected(override):
    with pytest.raises(ValueError):
        budget.validate_manifest(manifest(**override))


def test_reserve_then_outcome_lifecycle(tmp_path):
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    assert ledger.runnable("zen-nonstream") is True
    ledger.reserve("zen-nonstream")
    assert ledger.runnable("zen-nonstream") is False
    with pytest.raises(ValueError):
        ledger.reserve("zen-nonstream")
    ledger.record_outcome("zen-nonstream", 12, failed=False)
    with pytest.raises(ValueError):
        ledger.record_outcome("zen-nonstream", 12, failed=False)
    assert ledger.runnable("zen-stream") is True


def test_failed_outcome_halts_remaining_cases(tmp_path):
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    ledger.reserve("zen-nonstream")
    ledger.record_outcome("zen-nonstream", None, failed=True)
    assert ledger.runnable("zen-stream") is False
    with pytest.raises(ValueError):
        ledger.reserve("zen-stream")


def test_reserved_without_outcome_blocks_reread(tmp_path):
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    ledger.reserve("zen-nonstream")
    reopened = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    assert reopened.runnable("zen-nonstream") is False
    assert reopened.runnable("zen-stream") is True
    with pytest.raises(ValueError):
        reopened.record_outcome("openrouter-nonstream", 5, failed=False)


def test_unknown_case_rejected(tmp_path):
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    with pytest.raises(ValueError):
        ledger.reserve("nope")
    with pytest.raises(ValueError):
        ledger.record_outcome("nope", 1, failed=False)


@pytest.mark.parametrize(
    "mutation",
    [
        {"run": "other"},
        {"dispatches": 99},
        {"halted": "yes"},
        {"cases": {}},
        {"cases": {"zen-nonstream": {"reserved": False, "actual_tokens": None}}},
    ],
)
def test_corrupt_ledger_rejected(tmp_path, mutation):
    path = tmp_path / "ledger.json"
    budget.RunLedger(path, initialize=True)
    data = json.loads(path.read_text())
    data.update(mutation)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        budget.RunLedger(path, initialize=True)


def test_tampered_reserved_count_rejected(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = budget.RunLedger(path, initialize=True)
    ledger.reserve("zen-nonstream")
    data = json.loads(path.read_text())
    data["dispatches"] = 0
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        budget.RunLedger(path, initialize=True)


def test_unhalt_rejected(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = budget.RunLedger(path, initialize=True)
    ledger.reserve("zen-nonstream")
    ledger.record_outcome("zen-nonstream", None, failed=True)
    data = json.loads(path.read_text())
    data["halted"] = False
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        budget.RunLedger(path, initialize=True)


def test_dispatch_count_reports_reserved_attempts(tmp_path):
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    assert ledger.dispatch_count() == 0
    ledger.reserve("zen-nonstream")
    assert ledger.dispatch_count() == 1


def test_five_case_budget_is_final(tmp_path):
    ledger = budget.RunLedger(tmp_path / "ledger.json", initialize=True)
    for case_id in budget.CASE_IDS:
        ledger.reserve(case_id)
        ledger.record_outcome(case_id, 10, failed=False)
    assert ledger._read()["dispatches"] == 5
    with pytest.raises(ValueError):
        ledger.reserve("zen-nonstream")


def test_missing_initialized_ledger_fails_closed(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = budget.RunLedger(path, initialize=True)
    ledger.reserve("zen-nonstream")
    ledger.record_outcome("zen-nonstream", 12, failed=False)
    path.unlink()
    with pytest.raises(ValueError, match="missing"):
        budget.RunLedger(path, initialize=True)
