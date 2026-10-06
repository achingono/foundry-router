"""Owned settings and actual-dispatch guard tested without real credentials or egress."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

QUALITY = Path(__file__).resolve().parents[2] / "scripts/quality"
sys.path.insert(0, str(QUALITY))
spec = importlib.util.spec_from_file_location(
    "google_live_runtime", QUALITY / "google_live_runtime.py"
)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
from google_live_budget import BudgetLedger  # noqa: E402


def test_settings_ignore_ambient_production(monkeypatch):
    monkeypatch.setenv("FOUNDRY_STATE_BACKEND", "table")
    monkeypatch.setenv("FOUNDRY_BACKENDS_JSON", '{"PRIVATE":"ambient"}')
    monkeypatch.setenv("FOUNDRY_GOOGLE_STATE_KEYS_JSON", "PRIVATE")
    settings = runtime.isolated_settings(
        credential="synthetic", model="configured", caller_key="caller"
    )
    assert settings.state_backend == "memory" and set(settings.backends) == {"g"}
    assert settings.google_state_keys is None and settings.retry_attempts == 0


async def test_owned_mock_case_dispatch_debits_and_known_usage(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    calls = []

    def respond(request):
        calls.append(request)
        data = json.loads(ledger.path.read_text())
        assert data["projects"]["project-1"]["cases"]["case"]["reserved_tokens"] == 512
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "ready"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 11,
                },
            },
        )

    summary = await runtime.run_text_case(
        credential="synthetic",
        model="configured",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(respond),
    )
    assert summary["status"] == "passed" and len(calls) == 1
    assert "ready" not in json.dumps(summary) and "synthetic" not in json.dumps(summary)
    data = json.loads(ledger.path.read_text())
    assert data["projects"]["project-1"]["requests"] == 2
    assert data["projects"]["project-1"]["cases"]["case"]["actual_tokens"] == 11


@pytest.mark.parametrize(
    "url",
    [
        "https://other.example/v1beta/models/configured:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/configured:generateContent?x=1",
    ],
)
async def test_guard_rejects_other_targets_without_debit(tmp_path, url):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    guard = runtime.GuardedTransport(
        httpx.MockTransport(lambda _: pytest.fail("egress")),
        ledger=ledger,
        project="project-1",
        case_id="case",
        model="configured",
    )
    async with httpx.AsyncClient(transport=guard) as client:
        with pytest.raises(ValueError):
            await client.post(url, json={})
    assert json.loads(ledger.path.read_text())["projects"]["project-1"]["requests"] == 1


async def test_provider_error_retains_debit_and_cannot_retry(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "PRIVATE_OUTPUT"}})

    summary = await runtime.run_text_case(
        credential="PRIVATE_KEY",
        model="configured",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(respond),
    )
    assert summary["status"] == "failed" and len(calls) == 1
    data = json.loads(ledger.path.read_text())
    assert data["projects"]["project-1"]["tokens"] == 512
    assert "PRIVATE" not in json.dumps(summary) + ledger.path.read_text()


@pytest.mark.parametrize("scenario", ["incomplete", "refusal", "missing_usage", "overrun"])
async def test_inference_evidence_failures_are_not_success(tmp_path, scenario):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    raw = {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": "partial"}]},
                "finishReason": "MAX_TOKENS" if scenario == "incomplete" else "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 1, "totalTokenCount": 11},
    }
    if scenario == "refusal":
        raw = {"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": raw["usageMetadata"]}
    elif scenario == "missing_usage":
        raw.pop("usageMetadata")
    elif scenario == "overrun":
        raw["usageMetadata"] = {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 1,
            "totalTokenCount": 1001,
        }
    summary = await runtime.run_text_case(
        credential="synthetic",
        model="configured",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
    )
    assert summary["status"] == "failed"
    project = json.loads(ledger.path.read_text())["projects"]["project-1"]
    assert project["tokens"] >= 512 and project["requests"] == 2
    assert project["halted"] == (scenario == "overrun")


async def test_compressed_response_rejected_before_decoder(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")

    def respond(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=httpx.ByteStream(b"INVALID_COMPRESSED"),
        )

    with pytest.raises(ValueError, match="Encoded validation response rejected"):
        await runtime.run_text_case(
            credential="synthetic",
            model="configured",
            ledger=ledger,
            project="project-1",
            case_id="case",
            transport=httpx.MockTransport(respond),
        )
    assert json.loads(ledger.path.read_text())["projects"]["project-1"]["tokens"] == 512
