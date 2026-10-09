"""Same-wire diagnostic redaction and remaining surface-slot attempt bounds."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_38_usage_diagnostic as usage

from tests.unit.test_google_compatible_verification import chat


def test_numeric_shape_does_not_capture_strings_or_content():
    data = chat()
    data["usage"]["completion_tokens_details"] = {"reasoning_tokens": 96, "secret": "sensitive"}
    safe = usage.numeric_shape(json.dumps(data).encode())
    assert safe["counts"]["reasoning_tokens"]["value"] == 96
    assert "sensitive" not in json.dumps(safe) and "ready" not in json.dumps(safe)
    data["usage"]["prompt_tokens"] = "secret"
    assert usage.numeric_shape(json.dumps(data).encode())["counts"]["prompt_tokens"] == {
        "type": "other",
        "value": None,
    }


async def test_exact_same_wire_callbacks_and_old_ledger_preservation(tmp_path, monkeypatch):
    original = b'{"halted":true,"attempts":{"g38-native-project-1":{"physical_attempts":[{}]},"g38-nonstream-project-1":{"physical_attempts":[{}]}}}'
    (tmp_path / "ledger.json").write_bytes(original)
    monkeypatch.setattr(usage, "ORIGINAL_SHA256", hashlib.sha256(original).hexdigest())
    historical = tmp_path / "historical.json"
    historical.write_bytes(b"historical")
    monkeypatch.setattr(usage.diagnostic, "DIRECTORY", tmp_path)
    monkeypatch.setattr(usage.diagnostic, "HISTORICAL", historical)
    stage = tmp_path.parent / "google-compatible-text-verification"
    stage.mkdir(exist_ok=True)
    monkeypatch.setattr(usage, "fetch_project_credentials", lambda _secret: ["synthetic"] * 5)
    data = chat()
    monkeypatch.setattr(
        usage.httpx,
        "AsyncHTTPTransport",
        lambda **_kwargs: httpx.MockTransport(lambda _request: httpx.Response(200, json=data)),
    )
    result = await usage.execute("reference")
    assert (tmp_path / "ledger.json").read_bytes() == original
    assert result["numeric_observation"]["wire_equal"]
    assert result["numeric_observation"]["observer"] == result["numeric_observation"]["guard"]
    assert result["usage_callbacks"] == [
        {"source": "observer", "tokens": 12},
        {"source": "guard", "tokens": 12},
    ]
    ledger = usage.Ledger(tmp_path / "test.json", b"historical")
    ledger.reserve("project-1", usage.CASE, 1088)
    ledger.start_physical(usage.CASE)
    ledger.start_physical(usage.CASE)
    with pytest.raises(ValueError):
        ledger.start_physical(usage.CASE)


def test_edited_original_ledger_cannot_reopen_allowance(monkeypatch):
    raw = b'{"halted":true,"attempts":{"g38-native-project-1":{"physical_attempts":[{}]},"g38-nonstream-project-1":{"physical_attempts":[{}]}}}'
    monkeypatch.setattr(usage, "ORIGINAL_SHA256", hashlib.sha256(raw).hexdigest())
    assert usage.validate_original(raw)["halted"]
    with pytest.raises(ValueError):
        usage.validate_original(raw.replace(b"true", b"false"))
