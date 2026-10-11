"""Offline direct-probe checks: structure classification and redaction."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import openrouter_direct_probe as probe


def envelope(**overrides):
    body = {
        "id": "gen-1",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "openai/gpt-4o-mini",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "ready"},
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    body.update(overrides)
    return body


class FakeUpstream(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self.handler = handler
        self.calls = 0
        self.bodies = []
        self.urls = []

    async def handle_async_request(self, request):
        self.calls += 1
        self.bodies.append(bytes(request.content))
        self.urls.append(str(request.url))
        return await self.handler(request)

    async def aclose(self):
        pass


def ok_transport(payload: bytes, status: int = 200):
    async def handler(_request):
        return httpx.Response(status, content=payload)

    return FakeUpstream(handler)


async def run_probe(payload: bytes, status: int = 200):
    transport = ok_transport(payload, status)
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    return result, transport


async def test_normal_envelope_classified_without_content():
    result, transport = await run_probe(json.dumps(envelope()).encode())
    assert result["http_status"] == 200
    assert result["dispatched"] is True
    assert result["error_category"] is None
    structure = result["structure"]
    assert structure["finish_reason"] == "stop"
    assert structure["content_kind"] == "text"
    assert structure["content_length"] == len(b"ready")
    assert structure["usage_valid"] is True
    assert structure["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert transport.calls == 1
    assert b"ready" not in json.dumps(result).encode()
    body = json.loads(transport.bodies[0])
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["max_completion_tokens"] == 128


@pytest.mark.parametrize(
    "content,expected",
    [
        ("", "empty"),
        ("   ", "whitespace"),
        (None, "missing"),
        (["x"], "list-parts"),
        (42, "other"),
    ],
)
async def test_content_classification(content, expected):
    body = envelope()
    body["choices"][0]["message"] = {"role": "assistant", "content": content}
    result, _ = await run_probe(json.dumps(body).encode())
    assert result["structure"]["content_kind"] == expected


async def test_extra_fields_listed_without_values():
    body = envelope()
    body["choices"][0]["message"]["reasoning_content"] = "secret-reasoning"
    body["provider_meta"] = {"secret": True}
    result, _ = await run_probe(json.dumps(body).encode())
    structure = result["structure"]
    assert "reasoning_content" in structure["extra_message_fields"]
    assert "provider_meta" in structure["extra_top_fields"]
    assert b"secret-reasoning" not in json.dumps(result).encode()


async def test_refusal_and_tool_calls_classified():
    refusal = envelope()
    refusal["choices"][0]["message"] = {"role": "assistant", "refusal": "no"}
    result, _ = await run_probe(json.dumps(refusal).encode())
    assert result["structure"]["content_kind"] == "refusal"
    calls = envelope()
    calls["choices"][0]["message"] = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "x", "type": "function"}],
    }
    result, _ = await run_probe(json.dumps(calls).encode())
    assert result["structure"]["content_kind"] == "tool_calls"


async def test_mismapped_usage_flagged():
    body = envelope()
    body["usage"] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 99}
    result, _ = await run_probe(json.dumps(body).encode())
    assert result["structure"]["usage_valid"] is False


async def test_secret_bearing_errors_redacted():
    async def handler(_request):
        raise ValueError("boom synthetic-secret-marker-456")

    transport = FakeUpstream(handler)
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    assert result["error_category"] == "transport_failure"
    dumped = json.dumps(result)
    assert "synthetic-secret-marker-456" not in dumped
    assert "synthetic-key" not in dumped


async def test_exact_body_enforced():
    transport = ok_transport(json.dumps(envelope()).encode())
    await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    assert transport.calls == 1
    sent = json.loads(transport.bodies[0])
    assert sent == {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": probe.PROMPT}],
        "max_completion_tokens": 128,
    }
    assert transport.urls == ["https://openrouter.ai/api/v1/chat/completions"]


def test_execute_runs_each_model_once_and_never_replays(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    calls = []

    def factory():
        async def handler(request):
            calls.append(request.url.path)
            return httpx.Response(200, content=json.dumps(envelope()).encode())

        return FakeUpstream(handler)

    results = probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert [item["probe_id"] for item in results["attempts"]] == [p for p, _ in probe.PROBES]
    assert len(calls) == 3
    rerun = probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(rerun["attempts"]) == 3
    assert len(calls) == 3
    dumped = (tmp_path / "results-probe.json").read_text()
    assert "synthetic-key" not in dumped
    assert "ready" not in dumped


def test_execute_refuses_without_credential(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    with pytest.raises(ValueError):
        probe.execute_probes(credential="  ", transport_factory=lambda: None)


def test_cli_refuses_without_execute(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["openrouter_direct_probe.py"])
    assert probe.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "refused"
