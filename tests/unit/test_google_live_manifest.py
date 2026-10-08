"""Dormant live CLI validates all model statuses and cannot fetch credentials."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/quality/google-live-validation.py"
MANIFEST = ROOT / "docs/plans/google-ai-studio-tools-multimodal/live-runner/manifest.json"


@pytest.mark.parametrize("execute", [False, True])
def test_dormant_cli_no_credential_or_network_access(tmp_path, execute):
    # No az executable is reachable: execution must reject before attempting credentials.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(MANIFEST),
            *(["--execute"] if execute else []),
        ],
        env={"PATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    summary = json.loads(result.stdout)
    assert result.returncode == (2 if execute else 0)
    assert summary["provider_requests"] == 0
    if execute:
        assert summary["status"] == "missing_execution_arguments"
    else:
        assert summary["dispatch_eligible_cases"] == 0
    assert summary["models"] == 61 and not result.stderr


def test_execute_without_eligible_cases_attempts_no_credentials(tmp_path):
    # Synthetic manifest carries no executable rows: rejection precedes any
    # credential attempt even when az exists and arguments are complete.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(MANIFEST),
            "--execute",
            "--keyvault-ref",
            "vault-ref",
            "--ledger",
            str(tmp_path / "ledger.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    summary = json.loads(result.stdout)
    assert result.returncode == 2
    assert summary["status"] == "no_executable_cases"
    assert summary["provider_requests"] == 0
    assert not (tmp_path / "ledger.json").exists()
    assert not result.stderr


@pytest.mark.parametrize("mutation", ["budget", "status", "capability", "duplicate", "pricing"])
def test_manifest_errors_fail_closed(tmp_path, mutation):
    manifest = copy.deepcopy(json.loads(MANIFEST.read_text()))
    if mutation == "budget":
        manifest["max_tokens_per_project"] = 20001
    elif mutation == "status":
        manifest["models"][0]["capabilities"]["text_nonstream"] = "approved"
    elif mutation == "capability":
        manifest["models"][0]["capabilities"]["execute_tool"] = "pending_case"
    elif mutation == "duplicate":
        manifest["models"].append(manifest["models"][0])
    else:
        manifest["models"][0]["free_tier_text"] = True
        manifest["models"][0]["pricing_evidence"] = "unverified"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status": "invalid_manifest", "provider_requests": 0}
    assert not result.stderr
