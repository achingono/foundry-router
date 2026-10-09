"""Guarded compatible inference, pessimistic budgets and durable stage resume."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_compatible_runtime as runtime
import google_compatible_stage as stage
from google_live_budget import BudgetLedger


def chat(prompt=10, completion=2):
    return {
        "id": "chatcmpl-synthetic",
        "object": "chat.completion",
        "created": 1700000000,
        "model": runtime.MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ready"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


def stream_wire(data):
    return (
        "data: "
        + json.dumps(
            {
                "id": data["id"],
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "ready"},
                        "finish_reason": None,
                    }
                ],
            }
        )
        + "\n\n"
        + "data: "
        + json.dumps(
            {"id": data["id"], "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        )
        + "\n\n"
        + "data: "
        + json.dumps({"id": data["id"], "choices": [], "usage": data.get("usage")})
        + "\n\ndata: [DONE]\n\n"
    ).encode()


@pytest.mark.parametrize("stream", [False, True])
async def test_exact_dispatch_usage_and_metered_cleanup(tmp_path, stream):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    calls = []

    def handle(request):
        calls.append(request)
        assert ledger._read()["projects"]["project-1"]["cases"]["case"]["reserved_tokens"] == 1088
        assert request.headers["authorization"] == "Bearer synthetic"
        if stream:
            return httpx.Response(
                200, content=stream_wire(chat()), headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json=chat())

    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(handle),
        stream=stream,
    )
    assert result["status"] == "passed" and len(calls) == 1
    assert (
        result["actual_tokens"] == 12
        and result["synthetic_debit_usd"] == 0.012
        and result["reservations_cleared"]
    )
    assert "ready" not in json.dumps(result) and 'synthetic"' not in json.dumps(result)


@pytest.mark.parametrize(
    "kind", ["missing", "inconsistent", "overcap", "overrun", "reasoning", "http", "refusal"]
)
async def test_failed_or_malformed_evidence_retains_debit(tmp_path, kind):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    data = chat()
    if kind == "missing":
        data.pop("usage")
    elif kind == "inconsistent":
        data["usage"]["total_tokens"] = 15
    elif kind == "overcap":
        data = chat(10, 1025)
    elif kind == "overrun":
        data = chat(10, 2000)
    elif kind == "reasoning":
        data["usage"]["completion_tokens_details"] = {"reasoning_tokens": 3}
    elif kind == "refusal":
        data["choices"][0]["message"] = {
            "role": "assistant",
            "content": None,
            "refusal": "synthetic refusal",
        }
    status = 429 if kind == "http" else 200
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=data)),
        stream=False,
    )
    assert result["status"] == "failed" and result["dispatched"]
    debit = ledger._read()["projects"]["project-1"]
    assert debit["tokens"] >= 1088
    assert debit["halted"] == (kind == "overrun")


@pytest.mark.parametrize("mutation", ["url", "authorization", "body"])
async def test_guard_rejects_before_ledger(tmp_path, mutation):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    guard = runtime.CompatibleGuard(
        httpx.MockTransport(lambda _: httpx.Response(200, json=chat())),
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id="case",
        stream=False,
    )
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    if mutation == "url":
        url = "https://evil.example/chat/completions"
    body = {
        "model": runtime.MODEL,
        "messages": [{"role": "user", "content": runtime.PROMPT}],
        "max_completion_tokens": 1024,
    }
    if mutation == "body":
        body["max_completion_tokens"] = 1025
    request = httpx.Request(
        "POST",
        url,
        headers={
            "authorization": "Bearer wrong" if mutation == "authorization" else "Bearer synthetic",
            "accept-encoding": "identity",
        },
        json=body,
    )
    with pytest.raises(ValueError):
        await guard.handle_async_request(request)
    assert not guard.dispatched and ledger._read()["projects"]["project-1"]["requests"] == 1
    await guard.aclose()


def fixtures(tmp_path):
    baseline = json.loads(stage.BASELINE_PATH.read_text())
    (tmp_path / "ledger-baseline.json").write_text(json.dumps(baseline))
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps(baseline))
    return ledger


def test_missing_or_reset_ledger_refused(tmp_path):
    ledger = fixtures(tmp_path)
    baseline = json.loads((tmp_path / "ledger-baseline.json").read_text())
    ledger.unlink()
    with pytest.raises(ValueError):
        stage.validate_ledger(ledger, baseline)
    assert not ledger.exists()
    BudgetLedger(ledger)
    with pytest.raises(ValueError):
        stage.validate_ledger(ledger, baseline)


def test_crash_after_reservation_halts_project_on_resume(tmp_path, monkeypatch):
    ledger_path = fixtures(tmp_path)
    ledger = BudgetLedger(ledger_path)
    first = stage.stage_cases()[0]
    ledger.reserve(first[0], first[2], 1088)
    seen = []

    async def fail(**kwargs):
        seen.append(kwargs["project"])
        return {
            "case_id": kwargs["case_id"],
            "project": kwargs["project"],
            "stream": kwargs["stream"],
            "model": runtime.MODEL,
            "status": "failed",
            "dispatched": False,
            "actual_tokens": None,
        }

    monkeypatch.setattr(stage, "run_compatible_case", fail)
    stage.execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger_path,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: None,
    )
    assert "project-1" not in seen and len(seen) == 4
    seen.clear()
    stage.execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger_path,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: None,
    )
    assert seen == []


def test_success_stage_stream_prerequisite_and_caps(tmp_path):
    ledger_path = fixtures(tmp_path)
    calls = []

    def handle(request):
        calls.append(request)
        if json.loads(request.content).get("stream"):
            return httpx.Response(
                200, content=stream_wire(chat()), headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json=chat())

    result = stage.execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger_path,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert len(calls) == 9 and all(r["status"] == "passed" for r in result["attempts"])
    stage.execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger_path,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert (
        len(calls) == 9
        and BudgetLedger(ledger_path)._read()["projects"]["project-1"]["requests"] == 20
    )


@pytest.mark.parametrize("mode", ["bytes", "encoding", "deadline", "terminal"])
async def test_bounds_deadline_and_missing_terminal(tmp_path, monkeypatch, mode):
    import asyncio

    ledger = BudgetLedger(tmp_path / "ledger.json")

    async def handle(_request):
        if mode == "deadline":
            await asyncio.sleep(10)
        if mode == "bytes":
            return httpx.Response(200, content=b"x" * 65)
        if mode == "encoding":
            return httpx.Response(200, json=chat(), headers={"content-encoding": "unsupported"})
        return httpx.Response(
            200, content=b'data: {"choices":[]}\n\n', headers={"content-type": "text/event-stream"}
        )

    if mode == "bytes":
        monkeypatch.setattr(runtime, "MAX_GOOGLE_RESPONSE_BYTES", 64)
    if mode == "deadline":
        monkeypatch.setattr(runtime, "CASE_TIMEOUT_SECONDS", 0.02)
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(handle),
        stream=mode == "terminal",
    )
    assert result["status"] == "failed" and result["dispatched"]
    assert ledger._read()["projects"]["project-1"]["tokens"] == 1088


def test_failed_project_stays_halted_on_resume(tmp_path):
    ledger = fixtures(tmp_path)
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(429)

    first = stage.execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert len(first["attempts"]) == 5 and len(calls) == 5
    stage.execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
    )
    assert len(calls) == 5


def test_wrong_project_and_result_ledger_binding_refused(tmp_path):
    path = fixtures(tmp_path)
    ledger = BudgetLedger(path)
    case = stage.stage_cases()[0][2]
    ledger.reserve("project-2", case, 1088)
    with pytest.raises(ValueError):
        stage.validate_ledger(path, json.loads((tmp_path / "ledger-baseline.json").read_text()))


def test_whole_stage_lock_serializes_competing_process(tmp_path):
    import subprocess
    import time

    from google_live_budget import locked

    lock_path = tmp_path / "stage"
    marker = tmp_path / "acquired"
    script = (
        "from pathlib import Path\nfrom google_live_budget import locked\nwith locked(Path("
        + repr(str(lock_path))
        + ")):\n Path("
        + repr(str(marker))
        + ').write_text("acquired")\n'
    )
    with locked(lock_path):
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(stage.STAGE_DIR.parents[2] / "scripts/quality"),
            },
        )
        time.sleep(0.1)
        assert not marker.exists()
    process.wait(timeout=10)
    assert process.returncode == 0 and marker.exists()


@pytest.mark.parametrize("stream", [False, True])
async def test_partial_or_earlier_usage_overrun_halts_ledger(tmp_path, stream):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    partial = {"total_tokens": 2000, "prompt_tokens": None, "completion_tokens": None}
    if stream:
        wire = (
            b"data: "
            + json.dumps({"choices": [], "usage": partial}).encode()
            + b"\n\n"
            + stream_wire(chat())
        )
        reply = httpx.Response(200, content=wire, headers={"content-type": "text/event-stream"})
    else:
        data = chat()
        data["usage"] = partial
        reply = httpx.Response(200, json=data)
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(lambda _: reply),
        stream=stream,
    )
    assert (
        result["status"] == "failed"
        and result["actual_tokens"] == 2000
        and result["budget_overrun"]
    )
    assert ledger._read()["projects"]["project-1"]["halted"]


def test_cli_refuses_without_execute_before_secret(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["runner"])
    assert stage.main() == 2
    assert json.loads(capsys.readouterr().out)["provider_requests"] == 0


def test_cli_safe_error_and_completed_paths(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["runner", "--execute", "--keyvault-ref", "synthetic-reference"]
    )

    def fail(_):
        raise ValueError("secret-like error")

    monkeypatch.setattr(stage, "execute_stage", fail)
    assert stage.main() == 2 and "secret-like" not in capsys.readouterr().out
    monkeypatch.setattr(stage, "execute_stage", lambda _: {"attempts": [{"status": "passed"}]})
    assert stage.main() == 0


async def test_explicit_usage_retained_despite_malformed_trailing_sse(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json")
    data = chat(10, 2000)
    wire = stream_wire(data) + b"data: malformed\n\n"
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=ledger,
        project="project-1",
        case_id="case",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=wire, headers={"content-type": "text/event-stream"}
            )
        ),
        stream=True,
    )
    assert result["status"] == "failed" and result["actual_tokens"] == 2010
    assert ledger._read()["projects"]["project-1"]["halted"]
