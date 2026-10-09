"""Actual adapter termination and numeric evidence have independent ownership."""

import copy
import hashlib
import json
import sys
from contextlib import suppress
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_final_cancel as stage
import google_stream_runtime as runtime
from google_decoder_observer import DecoderObserver

from tests.unit.test_google_stream_runtime import ProviderStream, event


def terminal(content="ready"):
    return {
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
    }


@pytest.mark.parametrize("signature", [False, True])
def test_actual_decoder_accepts_text_on_stop_with_usage(signature):
    observer = DecoderObserver(prompt="hello")
    value = terminal()
    if signature:
        value["choices"][0]["delta"]["extra_content"] = {
            "google": {"thought_signature": "synthetic-signature"}
        }
    observer.feed(event(value))
    assert observer.complete_usage and not observer.terminal_usage
    observer.feed(b"data: [DONE]\n\n")
    observer.finish()
    assert observer.terminal_usage and observer.mirror_terminal
    observer.clear()
    assert observer.mirror is None and not observer.line and not observer.data


def test_cancel_clear_does_not_synthesize_termination():
    observer = DecoderObserver(prompt="hello")
    observer.feed(event(terminal()))
    observer.clear()
    assert not observer.done and not observer.eof and not observer.mirror_valid


def test_malformed_provider_state_retains_usage_before_decoder_failure():
    observer = DecoderObserver(prompt="hello")
    value = terminal()
    value["choices"][0]["delta"]["extra_content"] = {"private": "invalid"}
    with pytest.raises(ValueError):
        observer.feed(event(value))
    assert observer.maximum_tokens == 9 and observer.invalid and not observer.terminal_usage


def test_terminal_type_in_output_cannot_forge_completion():
    observer = DecoderObserver(prompt="hello")
    observer.feed(
        event(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": '"type":"response.completed"'},
                        "finish_reason": None,
                    }
                ]
            }
        )
    )
    assert not observer.mirror_terminal


@pytest.mark.parametrize("wire", [event(terminal()), event(terminal())[:-1]])
def test_missing_done_or_truncated_frame_never_terminal(wire):
    observer = DecoderObserver(prompt="hello")
    observer.feed(wire)
    with suppress(ValueError):
        observer.finish()
    assert not observer.terminal_usage


@pytest.mark.asyncio
async def test_signature_stop_usage_matches_actual_normal_route():
    class SignedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield event(
                {"choices": [{"index": 0, "delta": {"content": "ready"}, "finish_reason": None}]}
            )
            import asyncio

            await asyncio.sleep(0.05)
            value = terminal("")
            value["choices"][0]["delta"]["extra_content"] = {
                "google": {"thought_signature": "synthetic-signature"}
            }
            yield event(value)
            yield b"data: [DONE]\n\n"

    observer = DecoderObserver(prompt=runtime.PROMPTS["ordinary"])
    result = await runtime.run_case(
        credential="synthetic-key",
        case={**stage.CASE, "cancel": False, "prompt": "ordinary"},
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=SignedStream())),
        reserve=lambda: None,
        progress=lambda _: None,
        observer=observer,
    )
    assert result["status"] == "passed", result
    assert (
        result["public_completed"] and result["terminal_usage"] and result["mirror_terminal_valid"]
    )
    assert result["actual_tokens"] == 9 and result["usage_matches"] and result["settlement_matches"]


@pytest.mark.asyncio
async def test_cancellation_after_done_in_same_received_chunk_cannot_pass():
    class CompletedChunk(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield event(terminal()) + b"data: [DONE]\n\n"

    result = await runtime.run_case(
        credential="synthetic-key",
        case=stage.CASE,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=CompletedChunk())),
        reserve=lambda: None,
        progress=lambda _: None,
        observer=DecoderObserver(prompt=runtime.PROMPTS["cancel"]),
    )
    assert result["status"] == "failed"
    assert result["decoded_done"] and result["mirror_terminal_seen"]
    assert not result["cancelled_before_upstream_eof"]


@pytest.mark.asyncio
async def test_real_loopback_cancel_mirror_and_conservative_settlement(tmp_path):
    source = ProviderStream(cancel=True)
    observer = DecoderObserver(prompt=runtime.PROMPTS["cancel"])
    progress = []
    result = await runtime.run_case(
        credential="synthetic-key",
        case=stage.CASE,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=source)),
        reserve=lambda: None,
        progress=progress.append,
        observer=observer,
    )
    assert result["status"] == "passed", result
    assert result["natural_cleanup"] and source.closed
    assert result["cancelled_before_upstream_eof"] and not result["terminal_usage"]
    assert result["settlement_kind"] == "conservative_reservation"
    assert not result["mirror_terminal_valid"] and not result["decoded_done"]
    assert observer.mirror is None
    assert all(set(stage.INITIAL) <= set(value) for value in progress)
    from google_live_budget import BudgetLedger

    ledger = BudgetLedger(tmp_path / "ledger.json")
    ledger.reserve(stage.CASE["project"], stage.CASE["case_id"], 1088)
    stage.result_validator(result, stage.CASE, ledger._read())
    with pytest.raises(ValueError):
        stage.result_validator({**result, "synthetic_debit_usd": 0.0}, stage.CASE, ledger._read())


def test_retained_normal_prerequisites_have_pinned_debit_and_ledger():
    assert stage.validate_prerequisite()


@pytest.mark.parametrize("mutation", ["digest", "debit", "early", "ledger"])
def test_prerequisite_tampering_refused(tmp_path, mutation):
    results = json.loads((stage.PREVIOUS_DIRECTORY / "results.json").read_text())
    ledger = json.loads(stage.LEDGER_PATH.read_text())
    manifest = json.loads((stage.DIRECTORY / "prerequisite-manifest.json").read_text())
    if mutation == "debit":
        results["attempts"][0]["synthetic_debit_usd"] = 0.0
    elif mutation == "early":
        results["attempts"][0]["public_text_before_upstream_eof"] = False
    elif mutation == "ledger":
        ledger["projects"]["project-3"]["cases"]["t09-stream-project-3"]["actual_tokens"] = 1
    payload = json.dumps(results).encode()
    if mutation != "digest":
        manifest["results_sha256"] = hashlib.sha256(payload).hexdigest()
    (tmp_path / "results.json").write_bytes(payload)
    (tmp_path / "ledger.json").write_text(json.dumps(ledger))
    (tmp_path / "prerequisite-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        stage.validate_prerequisite(tmp_path, tmp_path / "results.json", tmp_path / "ledger.json")


def test_mirror_schema_rejects_nonboolean():
    value = copy.deepcopy(stage.INITIAL)
    value["decoded_done"] = "private"
    with pytest.raises(ValueError):
        stage.validate_mirror(value)


def test_final_stage_consumes_once_and_replay_fetches_no_credentials(tmp_path, monkeypatch):
    from tests.unit.test_google_stream_stage import failed

    ledger = (stage.DIRECTORY / "ledger-baseline.json").read_bytes()
    (tmp_path / "ledger.json").write_bytes(ledger)
    (tmp_path / "ledger-baseline.json").write_bytes(ledger)
    (tmp_path / "prerequisite-manifest.json").write_bytes(
        (stage.DIRECTORY / "prerequisite-manifest.json").read_bytes()
    )
    calls = []

    async def runner(*, case, reserve, progress, **_kwargs):
        calls.append(case["case_id"])
        reserve()
        result = {**failed(case), **stage.INITIAL}
        from google_stream_stage import PROGRESS_KEYS

        progress({key: result[key] for key in PROGRESS_KEYS | stage.MIRROR_KEYS})
        return result

    options = {
        "directory": tmp_path,
        "ledger_path": tmp_path / "ledger.json",
        "case_runner": runner,
        "transport_factory": lambda: httpx.MockTransport(lambda _: None),
    }
    result = stage.run("synthetic", credentials=["synthetic"] * 5, **options)
    assert len(result["attempts"]) == len(calls) == 1
    import google_stream_stage

    monkeypatch.setattr(
        google_stream_stage,
        "fetch_project_credentials",
        lambda _: pytest.fail("replay fetched keys"),
    )
    assert stage.run("synthetic", **options) == result
    assert calls == [stage.CASE["case_id"]]
