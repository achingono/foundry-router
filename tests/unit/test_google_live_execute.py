"""Guarded live execution without credentials, network or provider traffic."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

QUALITY = Path(__file__).resolve().parents[2] / "scripts/quality"
sys.path.insert(0, str(QUALITY))
for _name, _file in (
    ("google_live_budget", "google_live_budget.py"),
    ("google_live_execute", "google_live_execute.py"),
):
    _spec = importlib.util.spec_from_file_location(_name, QUALITY / _file)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)

from google_live_budget import BudgetLedger  # noqa: E402
from google_live_execute import execute, fetch_credential, select_cases  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_MANIFEST = ROOT / "docs/plans/google-ai-studio-tools-multimodal/live-runner/manifest.json"
PRICING = "https://ai.google.dev/gemini-api/docs/pricing"

NATIVE_OK = {
    "candidates": [
        {
            "content": {"role": "model", "parts": [{"text": "ready"}]},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 8,
        "candidatesTokenCount": 2,
        "totalTokenCount": 10,
    },
}


def manifest_with(rows):
    manifest = json.loads(SYNTHETIC_MANIFEST.read_text())
    for row in manifest["models"]:
        row["id"] = f"models/{row['id']}"
    for model_id, capability in rows:
        for row in manifest["models"]:
            if row["id"] == f"models/{model_id}":
                row["free_tier_text"] = True
                row["pricing_evidence"] = PRICING
                if "generateContent" not in row["methods"]:
                    row["methods"].append("generateContent")
                row["capabilities"][capability] = "docs_supported_pending_live"
    return manifest


def provider(payload, *, usage=True):
    def handler(_request):
        body = dict(payload)
        if not usage:
            body.pop("usageMetadata", None)
        else:
            total = body["usageMetadata"]["promptTokenCount"]
            total += body["usageMetadata"]["candidatesTokenCount"]
            body["usageMetadata"]["totalTokenCount"] = total
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def _budget_models(monkeypatch):
    import google_live_execute as executor

    monkeypatch.setattr(
        executor,
        "PRIORITY_MODELS",
        ["models/synthetic-validation-model-001", "models/synthetic-validation-model-002"],
    )


def test_select_cases_only_text_nonstream_docs_supported(monkeypatch):
    manifest = manifest_with(
        [
            ("synthetic-validation-model-002", "text_stream"),
            ("synthetic-validation-model-003", "tools"),
        ]
    )
    assert select_cases(manifest) == []
    manifest = manifest_with(
        [
            ("synthetic-validation-model-001", "text_nonstream"),
            ("synthetic-validation-model-002", "text_nonstream"),
        ]
    )
    import google_live_execute as executor

    monkeypatch.setattr(
        executor,
        "PRIORITY_MODELS",
        ["models/synthetic-validation-model-002", "models/synthetic-validation-model-001"],
    )
    cases = select_cases(manifest)
    assert [item["project"] for item in cases] == [
        f"project-{i}" for i in range(1, 6) for _ in range(2)
    ]
    assert [item["model"] for item in cases] == [
        "models/synthetic-validation-model-002",
        "models/synthetic-validation-model-001",
    ] * 5
    assert all(item["capability"] == "text_nonstream" for item in cases)
    assert len({item["case_id"] for item in cases}) == 10


def test_fetch_credential_success_and_failures(monkeypatch):
    class Done:
        def __init__(self, code, out):
            self.returncode = code
            self.stdout = out
            self.stderr = ""

    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: Done(0, "synthetic-credential\n")
    )
    assert fetch_credential("vault-ref") == "synthetic-credential"
    assert "synthetic-credential" not in str(subprocess.run)
    for run in (
        lambda *_args, **_kwargs: Done(1, "synthetic-credential\n"),
        lambda *_args, **_kwargs: Done(0, "\n"),
        lambda *_args, **_kwargs: Done(0, "x" * 9000),
    ):
        monkeypatch.setattr(subprocess, "run", run)
        with pytest.raises(ValueError, match="Credential fetch failed"):
            fetch_credential("vault-ref")
    with pytest.raises(ValueError, match="Credential fetch failed"):
        fetch_credential("")


def test_execute_all_pass_offline(monkeypatch, tmp_path):
    _budget_models(monkeypatch)
    monkeypatch.setattr(
        "google_live_execute.fetch_credential",
        lambda _ref: (
            '["synthetic-key-1","synthetic-key-2","synthetic-key-3","synthetic-key-4","synthetic-key-5"]'
        ),
    )
    manifest = manifest_with([("synthetic-validation-model-001", "text_nonstream")])
    ledger_path = tmp_path / "ledger.json"
    summary, code = execute(
        manifest=manifest,
        keyvault_ref="vault-ref",
        ledger_path=ledger_path,
        transport_factory=lambda: provider(NATIVE_OK),
    )
    assert code == 0
    assert summary["status"] == "completed"
    assert summary["passed"] == 5 and summary["failed"] == 0 and summary["skipped"] == 0
    assert summary["provider_requests"] == 5
    assert all(item["actual_tokens"] == 10 for item in summary["cases"])
    ledger = BudgetLedger(ledger_path)
    _ = ledger
    data = json.loads(ledger_path.read_text())
    assert all(data["projects"][f"project-{i}"]["requests"] == 2 for i in range(1, 6))
    assert "synthetic-key" not in json.dumps(summary)


def test_execute_no_eligible_cases_creates_no_state(tmp_path):
    manifest = json.loads(SYNTHETIC_MANIFEST.read_text())
    ledger_path = tmp_path / "ledger.json"
    summary, code = execute(manifest=manifest, keyvault_ref="vault-ref", ledger_path=ledger_path)
    assert code == 2 and summary["status"] == "no_executable_cases"
    assert summary["provider_requests"] == 0
    assert not ledger_path.exists()


def test_execute_credential_failure_creates_no_state(monkeypatch, tmp_path):
    def missing(_ref):
        raise ValueError("Credential fetch failed")

    monkeypatch.setattr("google_live_execute.fetch_credential", missing)
    manifest = manifest_with([("synthetic-validation-model-001", "text_nonstream")])
    ledger_path = tmp_path / "ledger.json"
    summary, code = execute(manifest=manifest, keyvault_ref="vault-ref", ledger_path=ledger_path)
    assert code == 2 and summary["status"] == "credential_unavailable"
    assert not ledger_path.exists()


def test_execute_overrun_halts_project(monkeypatch, tmp_path):
    _budget_models(monkeypatch)
    monkeypatch.setattr(
        "google_live_execute.fetch_credential",
        lambda _ref: (
            '["synthetic-key-1","synthetic-key-2","synthetic-key-3","synthetic-key-4","synthetic-key-5"]'
        ),
    )
    big = dict(NATIVE_OK)
    big["usageMetadata"] = {
        "promptTokenCount": 400,
        "candidatesTokenCount": 200,
        "totalTokenCount": 600,
    }
    manifest = manifest_with(
        [
            ("synthetic-validation-model-001", "text_nonstream"),
            ("synthetic-validation-model-002", "text_nonstream"),
        ]
    )
    ledger_path = tmp_path / "ledger.json"
    summary, code = execute(
        manifest=manifest,
        keyvault_ref="vault-ref",
        ledger_path=ledger_path,
        transport_factory=lambda: provider(big),
    )
    assert code == 1
    assert summary["provider_requests"] == 5
    assert summary["skipped"] == 5
    assert sum(1 for item in summary["cases"] if item.get("budget_overrun")) == 5
    data = json.loads(ledger_path.read_text())
    assert all(data["projects"][f"project-{i}"]["halted"] for i in range(1, 6))


def test_execute_missing_usage_fails_without_refund(monkeypatch, tmp_path):
    _budget_models(monkeypatch)
    monkeypatch.setattr(
        "google_live_execute.fetch_credential",
        lambda _ref: (
            '["synthetic-key-1","synthetic-key-2","synthetic-key-3","synthetic-key-4","synthetic-key-5"]'
        ),
    )
    manifest = manifest_with([("synthetic-validation-model-001", "text_nonstream")])
    ledger_path = tmp_path / "ledger.json"
    summary, code = execute(
        manifest=manifest,
        keyvault_ref="vault-ref",
        ledger_path=ledger_path,
        transport_factory=lambda: provider(NATIVE_OK, usage=False),
    )
    assert code == 1 and summary["failed"] == 5
    data = json.loads(ledger_path.read_text())
    for i in range(1, 6):
        cases = data["projects"][f"project-{i}"]["cases"]
        assert len(cases) == 1
        [[_label, case]] = list(cases.items())
        assert case["reserved_tokens"] == 512 and case["actual_tokens"] is None


def test_fetch_project_credentials_shapes(monkeypatch):
    from google_live_execute import fetch_project_credentials

    good = '["a","b","c","d","e"]'
    monkeypatch.setattr("google_live_execute.fetch_credential", lambda _ref: good)
    assert fetch_project_credentials("vault-ref") == ["a", "b", "c", "d", "e"]
    for bad in (
        "not-json",
        '{"a": 1}',
        '["only-one"]',
        '["a","b","c","d","e","f"]',
        '["a","","c","d","e"]',
        "[1,2,3,4,5]",
    ):
        monkeypatch.setattr("google_live_execute.fetch_credential", lambda _ref, _b=bad: _b)
        with pytest.raises(ValueError, match="Credential fetch failed"):
            fetch_project_credentials("vault-ref")


def test_project_key_mapping_without_provider_traffic(monkeypatch, tmp_path):
    _budget_models(monkeypatch)
    import google_live_execute as executor

    seen = []

    async def fake_run_text_case(**kwargs):
        seen.append((kwargs["project"], kwargs["credential"]))
        return {
            "case_id": kwargs["case_id"],
            "model": kwargs["model"],
            "project": kwargs["project"],
            "capability": "text_nonstream",
            "http_status": 200,
            "dispatched": False,
            "status": "passed",
            "actual_tokens": 10,
            "budget_overrun": False,
        }

    monkeypatch.setattr(executor, "run_text_case", fake_run_text_case)
    monkeypatch.setattr(
        "google_live_execute.fetch_credential",
        lambda _ref: '["key-1","key-2","key-3","key-4","key-5"]',
    )
    manifest = manifest_with([("synthetic-validation-model-001", "text_nonstream")])
    summary, code = execute(
        manifest=manifest,
        keyvault_ref="vault-ref",
        ledger_path=tmp_path / "ledger.json",
        transport_factory=lambda: None,
    )
    assert code == 0 and summary["provider_requests"] == 0
    assert seen == [(f"project-{i}", f"key-{i}") for i in range(1, 6)]
    assert "key-" not in json.dumps(summary)


def test_level_cases_reserve_level_budget_and_unmapped_refuses(monkeypatch, tmp_path):
    import google_live_execute as executor

    monkeypatch.setattr(
        executor,
        "LEVEL_BY_MODEL",
        {"models/synthetic-validation-model-001": "minimal"},
    )
    monkeypatch.setattr(
        "google_live_execute.fetch_credential",
        lambda _ref: (
            '["synthetic-key-1","synthetic-key-2","synthetic-key-3","synthetic-key-4","synthetic-key-5"]'
        ),
    )
    manifest = manifest_with(
        [
            ("synthetic-validation-model-001", "text_nonstream"),
            ("synthetic-validation-model-002", "text_nonstream"),
        ]
    )
    summary, code = execute(
        manifest=manifest,
        keyvault_ref="vault-ref",
        ledger_path=tmp_path / "ledger.json",
        transport_factory=lambda: provider(NATIVE_OK),
    )
    assert code == 1
    by_case = {item["case_id"]: item for item in summary["cases"]}
    assert summary["skipped"] == 5
    assert all(
        by_case[f"txt-synthetic-validation-model-002-project-{i}"]["reason"]
        == "unsupported_thinking_shape"
        for i in range(1, 6)
    )
    data = json.loads((tmp_path / "ledger.json").read_text())
    for i in range(1, 6):
        cases = data["projects"][f"project-{i}"]["cases"]
        assert len(cases) == 1
        [[_label, case]] = list(cases.items())
        assert case["reserved_tokens"] == 1088


def test_case_id_filter_runs_single_pilot(monkeypatch, tmp_path):
    _budget_models(monkeypatch)
    monkeypatch.setattr(
        "google_live_execute.fetch_credential",
        lambda _ref: (
            '["synthetic-key-1","synthetic-key-2","synthetic-key-3","synthetic-key-4","synthetic-key-5"]'
        ),
    )
    manifest = manifest_with([("synthetic-validation-model-001", "text_nonstream")])
    summary, code = execute(
        manifest=manifest,
        keyvault_ref="vault-ref",
        ledger_path=tmp_path / "ledger.json",
        transport_factory=lambda: provider(NATIVE_OK),
        case_id="txt-synthetic-validation-model-001-project-3",
    )
    assert code == 0 and summary["passed"] == 1 and summary["provider_requests"] == 1
    data = json.loads((tmp_path / "ledger.json").read_text())
    assert data["projects"]["project-3"]["requests"] == 2
    assert all(data["projects"][f"project-{i}"]["requests"] == 1 for i in (1, 2, 4, 5))
