"""Offline direct-probe checks: structure classification and redaction."""

import asyncio
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


def test_write_failure_after_intent_blocks_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    calls = []

    def factory():
        async def handler(_request):
            calls.append(1)
            return httpx.Response(200, content=json.dumps(envelope()).encode())

        return FakeUpstream(handler)

    writes = {"count": 0}
    real_write = probe.write_atomic

    def flaky_write(path, data):
        writes["count"] += 1
        if writes["count"] == 3:
            raise OSError("disk full")
        return real_write(path, data)

    monkeypatch.setattr(probe, "write_atomic", flaky_write)
    with pytest.raises(OSError):
        probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(calls) == 1


def test_reserved_without_outcome_blocks_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    (tmp_path / "results-probe.json").write_text(
        json.dumps({"probe": "openrouter-direct", "reserved": ["probe-gemma"], "attempts": []})
    )
    with pytest.raises(ValueError):
        probe.execute_probes(
            credential="synthetic-key", transport_factory=lambda: FakeUpstream(None)
        )


async def test_timeout_after_entry_reports_dispatched(monkeypatch):
    async def hanging(_request):
        async def chunks():
            await asyncio.sleep(5)
            yield b"x"

        return httpx.Response(200, content=chunks())

    transport = FakeUpstream(hanging)
    monkeypatch.setattr(probe, "PROBE_TIMEOUT_SECONDS", 0.05)
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    assert result["dispatched"] is True
    assert result["error_category"] == "transport_failure"


async def test_oversized_stream_terminates_early(monkeypatch):
    yielded = []

    async def handler(_request):
        async def chunks():
            for _ in range(10):
                yielded.append(1)
                yield b"x" * 16

        return httpx.Response(200, content=chunks())

    transport = FakeUpstream(handler)
    monkeypatch.setattr(probe, "MAX_BODY_BYTES", 32)
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    assert result["error_category"] == "response_bound_exceeded"
    assert len(yielded) < 10


async def test_encoded_response_rejects_without_reading_body():
    read = []

    async def handler(_request):
        async def chunks():
            read.append(1)
            yield b"x"

        return httpx.Response(200, headers={"content-encoding": "gzip"}, content=chunks())

    transport = FakeUpstream(handler)
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    assert result["error_category"] == "encoded_response"
    assert read == []
    assert result["dispatched"] is True


async def test_finish_reason_marker_never_persisted():
    body = envelope()
    body["choices"][0]["finish_reason"] = "synthetic-secret-marker-789"
    transport = ok_transport(json.dumps(body).encode())
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    structure = result["structure"]
    assert structure["finish_reason"] is None
    assert structure["unexpected_finish_reason"] is True
    assert structure["finish_reason_length"] == len(b"synthetic-secret-marker-789")
    assert b"synthetic-secret-marker-789" not in json.dumps(result).encode()


def test_corrupt_results_refused(tmp_path):
    base = {
        "probe_id": "probe-gemma",
        "model": "google/gemma-4-26b-a4b-it:free",
        "http_status": 200,
        "dispatched": True,
        "elapsed_seconds": 0.1,
        "structure": None,
        "error_category": None,
    }
    mutations = [
        {"finish_reason": "weird", "unexpected_finish_reason": False},
        {"content_kind": "novel"},
        {"model": "other/model"},
        {"http_status": 99},
        {"extra": True},
    ]
    for mutation in mutations:
        if "finish_reason" in mutation or "content_kind" in mutation:
            attempt = dict(base)
            attempt["structure"] = {
                "top_fields": [],
                "extra_top_fields": [],
                "finish_reason": mutation.get("finish_reason"),
                "unexpected_finish_reason": False,
                "finish_reason_length": None,
                "message_fields": [],
                "extra_message_fields": [],
                "content_kind": mutation.get("content_kind", "text"),
                "content_length": 1,
                "usage": None,
                "usage_valid": False,
                "metadata_valid": True,
            }
        else:
            attempt = dict(base)
            attempt.update(mutation)
        with pytest.raises(ValueError):
            probe.load_probe_results(
                tmp_path / "missing.json",
                data={"probe": "openrouter-direct", "reserved": [], "attempts": [attempt]},
            )


async def test_probe_model_binding_mismatch_rejected():
    transport = ok_transport(b"{}")
    with pytest.raises(ValueError):
        await probe.run_probe("probe-gemma", "other/model", "synthetic-key", transport)
    assert transport.calls == 0


def test_deleted_results_after_init_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    calls = []

    def factory():
        async def handler(_request):
            calls.append(1)
            return httpx.Response(200, content=json.dumps(envelope()).encode())

        return FakeUpstream(handler)

    probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(calls) == 3
    (tmp_path / "results-probe.json").unlink()
    with pytest.raises(ValueError):
        probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(calls) == 3


def test_deleted_identity_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    (tmp_path / "results-probe.json.identity").write_text("{}")

    def no_egress():
        raise AssertionError("no transport on refused run")

    with pytest.raises(ValueError):
        probe.execute_probes(credential="synthetic-key", transport_factory=no_egress)


async def test_pre_header_timeout_reports_dispatched():
    async def entered_then_hung(_request):
        raise httpx.ReadTimeout("no headers")

    transport = FakeUpstream(entered_then_hung)
    result = await probe.run_probe("probe-openai", "openai/gpt-4o-mini", "synthetic-key", transport)
    assert transport.calls == 1
    assert result["dispatched"] is True
    assert result["error_category"] == "transport_failure"


def test_unknown_root_field_refused(tmp_path):
    with pytest.raises(ValueError):
        probe.load_probe_results(
            tmp_path / "missing.json",
            data={
                "probe": "openrouter-direct",
                "reserved": [],
                "attempts": [],
                "unknown": "synthetic-marker-root",
            },
        )


def test_oversized_envelope_write_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "STAGE_DIR", tmp_path)
    monkeypatch.setattr(probe, "MAX_RESULTS_BYTES", 128)
    calls = []

    def factory():
        async def handler(_request):
            calls.append(1)
            return httpx.Response(200, content=json.dumps(envelope()).encode())

        return FakeUpstream(handler)

    with pytest.raises(ValueError):
        probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        probe.execute_probes(credential="synthetic-key", transport_factory=factory)
    assert len(calls) == 1
