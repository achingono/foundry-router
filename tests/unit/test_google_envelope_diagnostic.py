"""Safe provider schema flags never persist arbitrary names or values."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_envelope_diagnostic as diagnostic
from google_live_budget import BudgetLedger

from tests.unit.test_google_compatible_verification import chat


def test_schema_redaction_and_fixed_bounds():
    data = chat()
    data["choices"][0]["message"].update(
        {
            "reasoning_content": "private-reasoning",
            "extra_content": {"key": "private-state"},
            "secret-like-key": "private-value",
            "annotations": [],
        }
    )
    result = diagnostic.observe_schema(json.dumps(data).encode())
    assert result["message_fields"]["reasoning_content"] == {
        "type": "string",
        "null": False,
        "empty": False,
    }
    assert result["other_message_field_count"] == 1
    encoded = json.dumps(result)
    for secret in [
        "private-reasoning",
        "private-state",
        "secret-like-key",
        "private-value",
        "ready",
    ]:
        assert secret not in encoded
    assert diagnostic.observe_schema(b"not json") == {"valid_json": False}


async def test_diagnostic_runtime_keeps_numeric_usage_and_schema(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    data = chat()
    data["choices"][0]["message"]["reasoning_content"] = None
    result = await diagnostic.run_diagnostic_case(
        credential="synthetic",
        ledger=ledger,
        project="project-2",
        case_id=diagnostic.CASE_ID,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)),
        stream=False,
    )
    assert result["status"] == "failed" and result["actual_tokens"] == 12
    assert result["safe_schema"]["message_fields"]["reasoning_content"]["null"]


def test_diagnostic_single_dispatch_resume_and_ambiguous(tmp_path):
    baseline = json.loads((diagnostic.DIAGNOSTIC_DIR / "ledger-baseline.json").read_text())
    (tmp_path / "ledger-baseline.json").write_text(json.dumps(baseline))
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(baseline))
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=chat())

    result = diagnostic.execute_diagnostic(
        "unused",
        directory=tmp_path,
        ledger_path=path,
        keys=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert len(calls) == 1 and result["safe_schema"]["finish_stop"]
    diagnostic.execute_diagnostic(
        "unused",
        directory=tmp_path,
        ledger_path=path,
        keys=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert len(calls) == 1
    (tmp_path / "diagnostic-result.json").unlink()
    result = diagnostic.execute_diagnostic(
        "unused",
        directory=tmp_path,
        ledger_path=path,
        keys=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert result["status"] == "ambiguous_consumed" and len(calls) == 1


def test_missing_ledger_refuses_before_creation(tmp_path):
    with pytest.raises(ValueError):
        diagnostic.execute_diagnostic(
            "unused", directory=tmp_path, ledger_path=tmp_path / "missing"
        )
    assert not (tmp_path / "missing").exists()


def test_cli_explicit_execution_and_safe_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["runner"])
    assert diagnostic.main() == 2
    monkeypatch.setattr(sys, "argv", ["runner", "--execute", "--keyvault-ref", "synthetic"])

    def fail(_):
        raise ValueError("secret-like failure")

    monkeypatch.setattr(diagnostic, "execute_diagnostic", fail)
    assert diagnostic.main() == 2 and "secret-like" not in capsys.readouterr().out
    monkeypatch.setattr(diagnostic, "execute_diagnostic", lambda _: {"status": "observed"})
    assert diagnostic.main() == 0


def test_corrupted_persisted_result_refused_without_disclosure(tmp_path):
    baseline = json.loads((diagnostic.DIAGNOSTIC_DIR / "ledger-baseline.json").read_text())
    (tmp_path / "ledger-baseline.json").write_text(json.dumps(baseline))
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(baseline))
    (tmp_path / "diagnostic-result.json").write_text(
        json.dumps({"secret-like-key": "private-value"})
    )
    with pytest.raises(ValueError):
        diagnostic.execute_diagnostic(
            "unused", directory=tmp_path, ledger_path=path, keys=["synthetic"] * 5
        )


@pytest.mark.parametrize("mutation", ["schema_key", "schema_type", "case", "ledger"])
async def test_saved_result_schema_and_ledger_binding(mutation, tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    result = await diagnostic.run_diagnostic_case(
        credential="synthetic",
        ledger=ledger,
        project="project-2",
        case_id=diagnostic.CASE_ID,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=chat())),
        stream=False,
    )
    debit = ledger._read()["projects"]["project-2"]["cases"][diagnostic.CASE_ID]
    if mutation == "schema_key":
        result["safe_schema"]["secret-like-key"] = "private-value"
    elif mutation == "schema_type":
        result["safe_schema"]["message_fields"]["content"]["type"] = "private-output"
    elif mutation == "case":
        result["case_id"] = "another"
    elif mutation == "ledger":
        debit = {**debit, "actual_tokens": 13}
    with pytest.raises(ValueError):
        diagnostic.validate_result(result, debit)
