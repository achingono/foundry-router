"""Fresh diagnostic budgets, redaction and exact 3.8 Responses forwarding."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_38_diagnostics as diagnostic
import google_compatible_runtime as runtime

from tests.unit.test_google_compatible_verification import chat, stream_wire


def observation(status=200, error=None, phase=None):
    return {
        "provider_http_status": status,
        "provider_error_status": error,
        "failure_phase": phase,
        "response_schema": None,
        "dimension_overrun": False,
        "retry_after_seconds": None,
    }


def native_result(status="passed", actual=9):
    return {
        "status": status,
        "actual_tokens": actual,
        "surface": "native",
        "model": diagnostic.MODEL,
        "http_status": 200 if status == "passed" else 503,
        "input_tokens": 7 if actual else None,
        "output_tokens": 2 if actual else None,
        "budget_overrun": False,
        "public_completed": status == "passed",
        "elapsed_seconds": 1.0,
    }


def test_budget_all_projects_no_replay_and_ambiguous_stop(tmp_path):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"historical")
    for i in range(1, 6):
        for surface in ("native", "nonstream", "stream"):
            project = f"project-{i}"
            case = f"g38-{surface}-{project}"
            ledger.reserve(project, case, 1088)
            with pytest.raises(ValueError):
                ledger.reserve(project, case, 1088)
            persisted = json.loads(ledger.path.read_text())
            assert persisted["attempts"][case]["result"] is None
            ledger.finish(case, native_result(), observation())
    assert len(ledger.data["attempts"]) == 15
    assert sum(x["reserved_tokens"] for x in ledger.data["attempts"].values()) == 16320
    with pytest.raises(ValueError):
        diagnostic.DiagnosticLedger(ledger.path, b"historical")


@pytest.mark.parametrize(
    "status,error,phase,halted",
    [
        (503, "UNAVAILABLE", None, False),
        (400, "INVALID_ARGUMENT", None, True),
        (429, "RESOURCE_EXHAUSTED", None, True),
        (None, None, "response_headers", False),
        (200, None, None, True),
        (503, "other", None, False),
    ],
)
def test_failure_stop_policy(tmp_path, status, error, phase, halted):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    ledger.reserve("project-1", "g38-native-project-1", 1088)
    ledger.finish(
        "g38-native-project-1",
        native_result("failed", None),
        observation(status, error, phase),
    )
    assert ledger.data["halted"] is halted


@pytest.mark.parametrize("stream", [False, True])
async def test_actual_responses_route_uses_selected_model_and_preserves_signature(tmp_path, stream):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    data = chat()
    data["model"] = diagnostic.MODEL
    data["choices"][0]["message"]["extra_content"] = {
        "google": {"thought_signature": "secret-signature"}
    }
    calls = []

    def handle(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body["model"] == diagnostic.MODEL
        assert body["max_completion_tokens"] == 1024
        assert "reasoning_effort" not in body
        assert (
            ledger.data["attempts"][f"g38-{'stream' if stream else 'nonstream'}-project-1"][
                "result"
            ]
            is None
        )
        return httpx.Response(
            200, content=stream_wire(data) if stream else json.dumps(data).encode()
        )

    case = f"g38-{'stream' if stream else 'nonstream'}-project-1"
    observer = diagnostic.ObservingTransport(httpx.MockTransport(handle), ledger, "project-1", case)
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id=case,
        transport=observer,
        stream=stream,
        model=diagnostic.MODEL,
    )
    assert result["status"] == "passed" and result["reservations_cleared"] and len(calls) == 1
    assert result["model"] == diagnostic.MODEL
    assert ledger.data["attempts"][case]["actual_tokens"] == 12
    safe = json.dumps(observer.observation)
    assert "secret-signature" not in safe and "ready" not in safe and "synthetic" not in safe


async def test_safe_error_enum_and_timeout_phase(tmp_path):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    case = "g38-native-project-1"
    ledger.reserve("project-1", case, 1088)

    def handle(request):
        raise httpx.ReadTimeout("secret-like-details", request=request)

    observer = diagnostic.ObservingTransport(httpx.MockTransport(handle), ledger, "project-1", case)
    with pytest.raises(httpx.ReadTimeout):
        await observer._once(httpx.Request("POST", "https://example.test"))
    assert observer.observation["failure_phase"] == "response_headers"
    assert (
        diagnostic.error_status(b'{"error":{"status":"UNAVAILABLE","message":"secret"}}')
        == "UNAVAILABLE"
    )
    assert diagnostic.error_status(b'{"error":{"status":"secret"}}') == "other"
    assert "secret" not in json.dumps(observer.observation)


async def test_malformed_stream_usage_retains_overrun_before_public_failure(tmp_path):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    case = "g38-stream-project-1"
    ledger.reserve("project-1", case, 1088)
    wire = b'data: {"usage":{"prompt_tokens":10,"completion_tokens":2000,"total_tokens":2010}}\n\ndata: malformed\n\n'
    observer = diagnostic.ObservingTransport(
        httpx.MockTransport(lambda _request: httpx.Response(200, content=wire)),
        ledger,
        "project-1",
        case,
    )
    await observer.handle_async_request(
        httpx.Request("POST", "https://example.test", json={"stream": True})
    )
    assert ledger.data["halted"]
    assert json.loads(ledger.path.read_text())["attempts"][case]["actual_tokens"] == 2010


@pytest.mark.parametrize(
    "scenario,expected_calls,expected_waits",
    [
        ("recover", 2, [2]),
        ("exhaust", 3, [2, 4]),
        ("parameter", 1, []),
        ("quota", 1, []),
        ("long_wait", 1, []),
    ],
)
async def test_bounded_retries_and_waits_are_durable(
    tmp_path, scenario, expected_calls, expected_waits
):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    case = "g38-nonstream-project-1"
    calls = []
    waits = []

    def handle(request):
        calls.append(request)
        physical = ledger.data["attempts"][case]["physical_attempts"]
        assert len(physical) == len(calls) and physical[-1]["observation"] is None
        status = 400 if scenario == "parameter" else 429 if scenario == "quota" else 503
        if scenario == "recover" and len(calls) == 2:
            return httpx.Response(200, json=chat())
        return httpx.Response(
            status,
            json={
                "error": {
                    "status": "UNAVAILABLE"
                    if status == 503
                    else "INVALID_ARGUMENT"
                    if status == 400
                    else "RESOURCE_EXHAUSTED"
                }
            },
            headers={"retry-after": "35"} if scenario == "long_wait" else {},
        )

    observer = diagnostic.ObservingTransport(httpx.MockTransport(handle), ledger, "project-1", case)

    async def sleep(delay):
        assert ledger.data["attempts"][case]["physical_attempts"][-1]["retry_wait_seconds"] == delay
        waits.append(delay)

    observer.sleep = sleep
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id=case,
        transport=observer,
        stream=False,
        model=diagnostic.MODEL,
    )
    assert len(calls) == expected_calls and waits == expected_waits
    assert result["status"] == ("passed" if scenario == "recover" else "failed")
    assert len(ledger.data["attempts"][case]["physical_attempts"]) == expected_calls


async def test_stream_bytes_prevent_retry_after_partial_failure(tmp_path):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    case = "g38-stream-project-1"
    ledger.reserve("project-1", case, 1088)

    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[]}\n\n'
            raise httpx.ReadError("private")

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, stream=BrokenStream())

    observer = diagnostic.ObservingTransport(httpx.MockTransport(handle), ledger, "project-1", case)
    with pytest.raises(httpx.ReadError):
        await observer.handle_async_request(
            httpx.Request("POST", "https://example.test", json={"stream": True})
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": 65, "completion_tokens": 1, "total_tokens": 66},
        {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
            "completion_tokens_details": {"reasoning_tokens": 1025},
        },
    ],
)
async def test_dimension_and_reasoning_overruns_halt_even_below_total_budget(tmp_path, usage):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    case = "g38-nonstream-project-1"
    ledger.reserve("project-1", case, 1088)
    observer = diagnostic.ObservingTransport(
        httpx.MockTransport(lambda _request: httpx.Response(200, json={"usage": usage})),
        ledger,
        "project-1",
        case,
    )
    await observer.handle_async_request(httpx.Request("POST", "https://example.test", json={}))
    assert ledger.data["halted"] and observer.observation["dimension_overrun"]


def test_unknown_result_field_and_observation_value_rejected():
    result = native_result()
    result["unexpected"] = "secret"
    with pytest.raises(ValueError):
        diagnostic.validate_result(result, observation())
    unsafe = observation()
    unsafe["failure_phase"] = "secret"
    with pytest.raises(ValueError):
        diagnostic.validate_observation(unsafe)


async def test_authentication_headers_prevent_retry_even_when_body_fails(tmp_path):
    ledger = diagnostic.DiagnosticLedger(tmp_path / "ledger.json", b"old")
    case = "g38-nonstream-project-1"
    ledger.reserve("project-1", case, 1088)
    calls = []

    class BrokenError(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise httpx.ReadTimeout("private error")
            yield b""

    def handle(request):
        calls.append(request)
        return httpx.Response(401, stream=BrokenError())

    observer = diagnostic.ObservingTransport(httpx.MockTransport(handle), ledger, "project-1", case)
    with pytest.raises(httpx.ReadTimeout):
        await observer.handle_async_request(httpx.Request("POST", "https://example.test", json={}))
    assert len(calls) == 1
