"""Offline harness checks: guards, runner, observation and redaction."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import zen_openrouter_live_budget as budget
import zen_openrouter_live_runtime as runtime

SECRET = "synthetic-credential-value"


def ledger(tmp_path):
    return budget.RunLedger(tmp_path / "ledger.json", initialize=True)


class FakeUpstream(httpx.AsyncBaseTransport):
    """Canned provider bytes with call counting and failure injection."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = 0

    async def handle_async_request(self, request):
        self.calls += 1
        return await self.handler(request)

    async def aclose(self):
        pass


def zen_body(usage=True):
    body = {
        "id": "resp_1",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "ready"}],
            }
        ],
        "model": "gpt-5.4",
    }
    if usage:
        body["usage"] = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    return body


def chat_body():
    return {
        "choices": [
            {"message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def run_case(kind, transport, tmp_path, **overrides):
    params = {
        "kind": kind,
        "credential": SECRET,
        "ledger": ledger(tmp_path),
        "case_id": kind,
        "transport": transport,
        "zen_model": "gpt-5.4",
        "openrouter_model": "organization/model",
        "embedding_model": "organization/embed",
        "input_per_million": 1000.0,
        "output_per_million": 1000.0,
    }
    params.update(overrides)
    return runtime.run_live_case(**params)


def ok_transport(payload: bytes, status: int = 200):
    async def handler(_request):
        return httpx.Response(status, content=payload)

    return FakeUpstream(handler)


async def test_zen_nonstream_pass(tmp_path):
    transport = ok_transport(json.dumps(zen_body()).encode())
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "passed"
    assert result["usage_matches"] is True
    assert result["settlement_matches"] is True
    assert result["reservations_cleared"] is True
    assert result["dispatched"] is True
    assert transport.calls == 1
    assert SECRET not in json.dumps(result)


async def test_zen_stream_pass(tmp_path):
    payload = (
        b'data: {"type":"response.created"}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"ready"}]}],"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15}}}\n\n'
    )
    transport = ok_transport(payload)
    result = await run_case("zen-stream", transport, tmp_path)
    assert result["status"] == "passed"
    assert result["terminated_ok"] is True
    assert result["usage_matches"] is True
    assert transport.calls == 1


async def test_openrouter_nonstream_pass(tmp_path):
    transport = ok_transport(json.dumps(chat_body()).encode())
    result = await run_case("openrouter-nonstream", transport, tmp_path)
    assert result["status"] == "passed"
    assert result["usage_matches"] is True
    assert result["settlement_matches"] is True


async def test_openrouter_stream_pass(tmp_path):
    payload = (
        b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\n'
        b'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\n'
        b"data: [DONE]\n\n"
    )
    transport = ok_transport(payload)
    result = await run_case("openrouter-stream", transport, tmp_path)
    assert result["status"] == "passed"
    assert result["terminated_ok"] is True


async def test_openrouter_embeddings_pass(tmp_path):
    body = {
        "data": [
            {"index": 0, "embedding": [0.5, 1.0]},
            {"index": 1, "embedding": [1.5, 2.0]},
        ],
        "usage": {"prompt_tokens": 6, "total_tokens": 6},
    }
    transport = ok_transport(json.dumps(body).encode())
    result = await run_case("openrouter-embeddings", transport, tmp_path)
    assert result["status"] == "passed"
    assert result["vector_count"] == 2
    assert result["dimensions"] == 2
    assert result["order_matches"] is True
    assert result["vector_values_match"] is True
    assert result["usage_matches"] is True
    assert result["settlement_matches"] is True


async def test_second_dispatch_rejected_at_observer(tmp_path):
    transport = ok_transport(json.dumps(zen_body()).encode())
    first = await run_case("zen-nonstream", transport, tmp_path)
    assert first["status"] == "passed"
    assert transport.calls == 1
    # A reserved case never reaches transport twice: the stage refuses, and a
    # direct rerun fails closed at the ledger reservation.
    led = ledger(tmp_path)
    assert led.runnable("zen-nonstream") is False


async def test_crash_after_intent_blocks_replay(tmp_path):
    async def handler(_request):
        raise httpx.ConnectError("down")

    transport = FakeUpstream(handler)
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["dispatched"] is True
    led = ledger(tmp_path)
    assert led.runnable("zen-nonstream") is False
    # A rerun with the same ledger refuses before egress.
    transport2 = ok_transport(json.dumps(zen_body()).encode())
    rerun = await run_case(
        "zen-nonstream",
        transport2,
        tmp_path,
        ledger=led,
    )
    assert rerun["status"] == "failed"
    assert rerun["dispatched"] is False
    assert transport2.calls == 0


async def test_provider_401_counts_as_dispatched(tmp_path):
    transport = ok_transport(b"no", status=401)
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["provider_http_status"] == 401
    assert result["dispatched"] is True


async def test_mismapped_usage_rejected(tmp_path):
    body = zen_body()
    body["usage"] = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 99}
    transport = ok_transport(json.dumps(body).encode())
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["usage_matches"] is False


async def test_over_cap_output_rejected(tmp_path):
    body = zen_body()
    body["usage"] = {"input_tokens": 10, "output_tokens": 129, "total_tokens": 139}
    transport = ok_transport(json.dumps(body).encode())
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"


async def test_missing_usage_rejected(tmp_path):
    transport = ok_transport(json.dumps(zen_body(usage=False)).encode())
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"


async def test_truncated_stream_rejected(tmp_path):
    payload = b'data: {"type":"response.created"}\n\n'
    transport = ok_transport(payload)
    result = await run_case("zen-stream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["terminated_ok"] is False


async def test_truncated_trailing_failure_rejected(tmp_path):
    payload = (
        b'data: {"type":"response.created"}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"ready"}]}],"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15}}}\n\n'
        b'data: {"type":"response.failed","response":{"status":"incompl'
    )
    transport = ok_transport(payload)
    result = await run_case("zen-stream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["terminated_ok"] is False


async def test_stream_bytes_forwarded_unchanged(tmp_path):
    upstream = (
        b'data: {"type":"response.created"}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed","output":[],"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15}}}\n\n'
    )
    seen = []

    async def handler(_request):
        async def chunks():
            for index in range(0, len(upstream), 7):
                seen.append(upstream[index : index + 7])
                yield upstream[index : index + 7]

        return httpx.Response(200, content=chunks())

    led = ledger(tmp_path)
    guard = runtime.ZenGuard(
        FakeUpstream(handler),
        ledger=led,
        case_id="zen-stream",
        credential=SECRET,
        deployment="gpt-5.4",
        stream=True,
    )
    body = json.dumps(
        {"model": "gpt-5.4", "input": runtime.PROMPT, "max_output_tokens": 128, "stream": True}
    ).encode()
    request = httpx.Request(
        "POST",
        "https://opencode.ai/zen/v1/responses",
        content=body,
        headers={"authorization": f"Bearer {SECRET}", "accept-encoding": "identity"},
    )
    response = await guard.handle_async_request(request)
    forwarded = b""
    async for chunk in response.aiter_bytes():
        forwarded += chunk
    assert forwarded == upstream
    assert guard.terminated_ok is True
    assert guard.truncated is False


async def test_embeddings_order_error_rejected(tmp_path):
    body = {
        "data": [
            {"index": 1, "embedding": [0.5]},
            {"index": 0, "embedding": [1.5]},
        ],
        "usage": {"prompt_tokens": 6, "total_tokens": 6},
    }
    transport = ok_transport(json.dumps(body).encode())
    result = await run_case("openrouter-embeddings", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["order_matches"] is False


async def test_bound_breach_rejected(tmp_path):
    transport = ok_transport(b"x" * (runtime.MAX_OBSERVED_BYTES + 1))
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["error_category"] == runtime.ERROR_BOUND
    assert result["dispatched"] is True


async def test_timeout_after_dispatch_reports_facts(tmp_path, monkeypatch):
    async def slow(_request):
        import asyncio as aio

        await aio.sleep(5)
        return httpx.Response(200, content=json.dumps(zen_body()).encode())

    transport = FakeUpstream(slow)
    monkeypatch.setattr(runtime, "CASE_TIMEOUT_SECONDS", 0.05)
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"
    assert result["error_category"] == runtime.ERROR_UPSTREAM
    assert result["dispatched"] is True


async def test_secret_bearing_errors_redacted(tmp_path):
    async def handler(_request):
        raise ValueError("boom synthetic-secret-marker-123")

    transport = FakeUpstream(handler)
    result = await run_case("zen-nonstream", transport, tmp_path)
    assert result["status"] == "failed"
    dumped = json.dumps(result)
    assert "synthetic-secret-marker-123" not in dumped
    assert SECRET not in dumped
    assert runtime.PROMPT not in dumped


async def test_unexpected_url_rejected_without_reserve(tmp_path):
    led = ledger(tmp_path)
    guard = runtime.ZenGuard(
        ok_transport(b"{}"),
        ledger=led,
        case_id="zen-nonstream",
        credential=SECRET,
        deployment="gpt-5.4",
    )
    request = httpx.Request("POST", "https://evil.test/zen/v1/responses", content=b"{}")
    with pytest.raises(ValueError):
        await guard.handle_async_request(request)
    assert led.runnable("zen-nonstream") is True


async def test_embeddings_value_translation_mismatch_rejected(tmp_path):
    public = {
        "data": [
            {"index": 0, "embedding": [0.5, 1.0]},
            {"index": 1, "embedding": [1.5, 2.1]},
        ],
        "usage": {"prompt_tokens": 6, "total_tokens": 6},
    }
    guard = runtime.OpenRouterEmbeddingsGuard(
        ok_transport(b"{}"),
        ledger=budget.RunLedger(tmp_path / "ledger.json", initialize=True),
        case_id="openrouter-embeddings",
        credential=SECRET,
        deployment="organization/embed",
    )
    guard.upstream_vectors = [[0.5, 1.0], [1.5, 2.0]]
    guard.vector_count = 2
    guard.dimensions = 2
    guard.order_ok = True
    guard.usage = (6, 0)
    acceptance = {
        "http_status": 200,
        "usage_matches": False,
        "terminated_ok": False,
        "vector_count": 0,
        "dimensions": 0,
        "order_matches": False,
        "vector_values_match": False,
    }
    assert runtime._accept_embeddings(public, guard, acceptance) is False
    assert acceptance["order_matches"] is True
    assert acceptance["vector_values_match"] is False


class StubResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class StubClient:
    def __init__(self, routes):
        self.routes = routes

    async def get(self, path, headers=None):
        _ = headers
        status, payload = self.routes[path]
        return StubResponse(status, payload)


def admin_payload(remaining=1000.0, active=0, inflight=0.0):
    return {
        "credit_groups": {
            "v": {
                "live": {
                    "estimated_remaining_usd": remaining,
                    "active_reservations": active,
                    "reserved_inflight_usd": inflight,
                }
            }
        }
    }


def ready_payload(ready=True):
    return {"ready": ready, "checks": {}}


async def test_ready_and_quiet_returns_canonical_balance():
    client = StubClient(
        {
            "/health/live": (200, {"status": "alive"}),
            "/health/ready": (200, ready_payload(True)),
            "/admin/status": (200, admin_payload(999.5)),
        }
    )
    assert await runtime._verify_ready_and_quiet(client, "admin-key") == 999.5


async def test_readiness_failure_blocks_before_dispatch():
    client = StubClient(
        {
            "/health/live": (200, {"status": "alive"}),
            "/health/ready": (503, ready_payload(False)),
            "/admin/status": (200, admin_payload()),
        }
    )
    with pytest.raises(runtime.VerificationSetupError):
        await runtime._verify_ready_and_quiet(client, "admin-key")


async def test_busy_account_blocks_before_dispatch():
    client = StubClient(
        {
            "/health/live": (200, {"status": "alive"}),
            "/health/ready": (200, ready_payload(True)),
            "/admin/status": (200, admin_payload(active=1)),
        }
    )
    with pytest.raises(runtime.VerificationSetupError):
        await runtime._verify_ready_and_quiet(client, "admin-key")


async def test_malformed_admin_evidence_blocks():
    client = StubClient(
        {
            "/health/live": (200, {"status": "alive"}),
            "/health/ready": (200, ready_payload(True)),
            "/admin/status": (200, {"credit_groups": {}}),
        }
    )
    with pytest.raises(runtime.VerificationSetupError):
        await runtime._verify_ready_and_quiet(client, "admin-key")


async def test_admin_auth_failure_blocks_before_dispatch():
    client = StubClient(
        {
            "/health/live": (200, {"status": "alive"}),
            "/health/ready": (200, ready_payload(True)),
            "/admin/status": (401, {"detail": "Invalid admin API key"}),
        }
    )
    with pytest.raises(runtime.VerificationSetupError):
        await runtime._verify_ready_and_quiet(client, "wrong-key")


async def test_readiness_failure_blocks_live_dispatch_end_to_end(tmp_path, monkeypatch):
    transport = ok_transport(b"{}")
    real_settings = runtime.verification_settings

    def unready_settings(**kwargs):
        return real_settings(**kwargs).model_copy(update={"pricing": {}})

    monkeypatch.setattr(runtime, "verification_settings", unready_settings)
    led = ledger(tmp_path)
    with pytest.raises(runtime.VerificationSetupError):
        await runtime.run_live_case(
            kind="zen-nonstream",
            credential=SECRET,
            ledger=led,
            case_id="zen-nonstream",
            transport=transport,
            zen_model="gpt-5.4",
            openrouter_model="organization/model",
            embedding_model="organization/embed",
            input_per_million=1000.0,
            output_per_million=1000.0,
        )
    assert transport.calls == 0
    assert led.runnable("zen-nonstream") is True
