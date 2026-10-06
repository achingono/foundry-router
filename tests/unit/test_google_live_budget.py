"""Persistent project caps survive interruption/rerun and actual usage overruns."""

import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts/quality/google_live_budget.py"
spec = importlib.util.spec_from_file_location("google_live_budget", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BudgetLedger = module.BudgetLedger


def test_rerun_and_failed_attempt_reservations_remain(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = BudgetLedger(path)
    ledger.reserve("project-1", "case1", 10000)
    del ledger
    ledger = BudgetLedger(path)
    ledger.reserve("project-1", "case2", 10000)
    with pytest.raises(ValueError):
        ledger.reserve("project-1", "case3", 1)
    ledger.record_usage("project-1", "case1", 1)
    with pytest.raises(ValueError):
        ledger.reserve("project-1", "case3", 1)
    assert json.loads(path.read_text())["projects"]["project-1"]["requests"] == 3


def test_project_isolation_request_cap_and_overrun(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    for i in range(19):
        ledger.reserve("project-1", f"case{i}", 1)
    with pytest.raises(ValueError):
        ledger.reserve("project-1", "extra", 1)
    ledger.reserve("project-2", "case", 100)
    ledger.record_usage("project-2", "case", 101)
    with pytest.raises(ValueError):
        ledger.reserve("project-2", "extra", 1)
    with pytest.raises(ValueError):
        ledger.record_usage("project-2", "case", 101)


def test_concurrent_instances_cannot_double_reserve(tmp_path):
    path = tmp_path / "ledger.json"
    BudgetLedger(path)

    def reserve(i):
        try:
            BudgetLedger(path).reserve("project-1", f"case{i}", 12000)
            return True  # noqa: TRY300
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(reserve, range(4))) == 1


def test_malformed_existing_ledger_fails_closed(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text('{"session":"wrong"}')
    with pytest.raises(ValueError):
        BudgetLedger(path)


def test_ledger_tampering_does_not_reset_reserved_tokens(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = BudgetLedger(path)
    ledger.reserve("project-1", "case", 10000)
    data = json.loads(path.read_text())
    data["projects"]["project-1"]["tokens"] = 0
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        BudgetLedger(path)


def test_overrun_halt_cannot_be_removed_below_total_cap(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = BudgetLedger(path)
    ledger.reserve("project-1", "case", 100)
    ledger.record_usage("project-1", "case", 101)
    data = json.loads(path.read_text())
    data["projects"]["project-1"]["halted"] = False
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        BudgetLedger(path)
