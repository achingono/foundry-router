"""Flash streaming diagnostic: funding gates, redaction, framing and replay."""

import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest
import respx

sys.path.insert(0, str(Path("scripts/quality").resolve()))
import opencode_five_validation as validation
import opencode_gemini_stream_diagnostic as d

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.config import BackendConfig
from foundry_router.config.google_features import GoogleFeatureProfile

TEXT = "SYNTHETIC-DIAGNOSTIC-TEXT-9f3a"


def usage(n_in, n_out):
    return {
        "promptTokenCount": n_in,
        "candidatesTokenCount": n_out,
        "totalTokenCount": n_in + n_out,
    }


def content_event(text, n_in, n_out, finish=None):
    candidate = {"content": {"role": "model", "parts": [{"text": text}]}}
    if finish is not None:
        candidate["finishReason"] = finish
    return {"candidates": [candidate], "usageMetadata": usage(n_in, n_out)}


def frame(payload):
    return b"data: " + json.dumps(payload).encode() + b"\n\n"


def fresh_decoder():
    adapter = GoogleNativeAdapter(
        profile=GoogleFeatureProfile(native_thinking_level="low", thought_token_pricing=True)
    )
    return adapter.create_stream_decoder(
        logical_model="gemini-3.8-flash-zen", metadata={}, request_body=d.REQUEST
    )


def passed_result(case, output=5):
    pin, pout = case["input_per_million"], case["output_per_million"]
    return {
        "id": case["id"],
        "status": "passed",
        "http_status": 200,
        "input_tokens": 10,
        "output_tokens": output,
        "estimated_debit_usd": (10 * pin + output * pout) / 1_000_000,
        "reservations_cleared": True,
        "error_category": None,
    }


@pytest.fixture
def bound(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "PRIVATE", tmp_path)
    monkeypatch.setattr(d, "DIRECTORY", tmp_path / "stream-diagnostic-v1")
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    fps = {"staging": "b" * 64, "production": "c" * 64}
    spec = validation.manifest(d.CA6_IMAGE, fps, run_id=validation.ANTHROPIC_RUN)
    cases = spec["cases"]
    assert len(cases) == 14
    entries = [{"reserved": True, "result": passed_result(case)} for case in cases[:7]]
    entries += [{"reserved": False, "result": None} for _ in cases[7:]]
    ledger = {"manifest_sha256": d.fingerprint(spec), "entries": entries}
    identity = {"manifest_sha256": d.fingerprint(spec)}
    debit_sum = sum(e["result"]["estimated_debit_usd"] for e in entries[:7])
    final_admin = {
        "credit_groups": {
            "opencode-account": {
                "live": {
                    "estimated_remaining_usd": 0.088 - debit_sum,
                    "active_reservations": 0,
                    "reserved_inflight_usd": 0,
                }
            }
        }
    }
    stopped = {"stopped": True, "unused_allocation_not_transferred": True}
    funds = {
        "credit_groups": {
            "opencode-account": {
                "live": {
                    "estimated_remaining_usd": d.R_FUNDS,
                    "active_reservations": 0,
                    "reserved_inflight_usd": 0,
                }
            }
        }
    }
    files = {
        "runner5/manifest.json": spec,
        "runner5/identity.json": identity,
        "runner5/ledger.json": ledger,
        "staging5-final-admin.json": final_admin,
        "staging5-stopped.json": stopped,
        "stage5-container-id.txt": "synthetic",
        "stream-funds-admin.json": funds,
        ".local/share/opencode/auth.json": {"opencode": {"key": "synthetic-key"}},
    }
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data))
    body = build_body()
    packet = {
        "diagnostic_id": d.IDENTITY,
        "executor_sha256": hashlib.sha256(Path(d.__file__).read_bytes()).hexdigest(),
        "dependency_sha256": d.dependency_hashes(),
        "funds_before_usd": d.R_FUNDS,
        "conservative_debit_usd": d.DEBIT,
        "stage_seed_usd": d.STAGE_SEED,
        "request_sha256": d.fingerprint(d.REQUEST),
        "native_body_sha256": d.fingerprint(body),
        "ca6_manifest_sha256": d.fingerprint(spec),
        "ca6_ledger_sha256": d.fingerprint(ledger),
        "ca6_snapshot_sha256": d.fingerprint(final_admin),
        "ca6_stopped_proof_sha256": d.fingerprint(stopped),
        "container_id_sha256": hashlib.sha256(b"synthetic").hexdigest(),
        "funds_snapshot_sha256": d.fingerprint(funds),
    }
    (tmp_path / "stream-diagnostic-packet.json").write_text(json.dumps(packet))
    return tmp_path


def build_body():
    config = BackendConfig.model_validate(
        {
            "provider": "opencode_google",
            "api_surface": "native",
            "endpoint": "https://opencode.ai/inference/v1",
            "credential": "synthetic-key",
            "deployment": "gemini-3.8-flash",
            "google_features": {"native_thinking_level": "low", "thought_token_pricing": True},
        }
    )
    adapter = get_adapter(config.provider, google_features=config.google_features)
    return adapter.build_upstream_body(
        "responses",
        d.REQUEST,
        deployment=config.deployment,
        default_output_tokens=512,
    )


@pytest.mark.usefixtures("bound")
def test_consumed_binding_and_no_replay():
    _, _, body = d.prepare()
    marker = json.loads((d.DIRECTORY / "consumed.json").read_text())
    assert marker["diagnostic_id"] == d.IDENTITY
    assert marker["native_body_sha256"] == d.fingerprint(body)
    assert marker["funds_before_usd"] == pytest.approx(d.R_FUNDS)
    assert marker["conservative_debit_usd"] == d.DEBIT
    assert marker["stage_seed_usd"] == d.STAGE_SEED
    assert (
        marker["packet_sha256"]
        == hashlib.sha256((d.PRIVATE / "stream-diagnostic-packet.json").read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="already claimed"):
        d.prepare()


@pytest.mark.parametrize(
    "field,value",
    [
        ("estimated_remaining_usd", 0.10),
        ("estimated_remaining_usd", float("nan")),
        ("active_reservations", 1),
        ("reserved_inflight_usd", 0.001),
    ],
)
def test_invalid_funds_refuses_before_consumption(bound, field, value):
    p = bound / "stream-funds-admin.json"
    snapshot = json.loads(p.read_text())
    snapshot["credit_groups"]["opencode-account"]["live"][field] = value
    p.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_production_slots_must_remain_unconsumed(bound):
    p = bound / "runner5" / "ledger.json"
    ledger = json.loads(p.read_text())
    ledger["entries"][7] = {"reserved": True, "result": {"status": "passed"}}
    p.write_text(json.dumps(ledger))
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_split_frames_handles_both_delimiters():
    raw = b"data: {}\n\n" + b"data: {}" + b"\r\n\r\n" + b": heartbeat\n\n"
    parts = d.split_events(raw)
    assert len(parts) == 3
    assert all(delimiter for _, delimiter in parts)
    assert d.event_data(parts[2][0]) == b""


def test_split_frames_bound(monkeypatch):
    monkeypatch.setattr(d, "MAX_EVENTS", 2)
    with pytest.raises(ValueError):
        d.split_events(b"data: {}\n\n" * 3)


def test_unclean_eof_matches_production_rejection():
    payload = content_event(TEXT, 10, 5, finish="STOP")
    terminated = d.classify_stream(fresh_decoder(), frame(payload))
    assert terminated["finish"] == "accepted"
    assert terminated["events"][0]["kind"] == "data"
    raw = b"data: " + json.dumps(payload).encode()
    outcome = d.classify_stream(fresh_decoder(), raw)
    assert outcome["events"][0]["kind"] == "unterminated"
    assert outcome["events"][0]["decoder"] == "buffered"
    assert outcome["finish"] == "Native stream ended without clean finish evidence"
    assert TEXT not in json.dumps(outcome)


def test_structure_hides_text_and_unknown_names():
    out = json.dumps(
        d.structure(
            {
                "mystery": "SECRET-VALUE",
                "candidates": [{"content": {"parts": [{"text": TEXT}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 3},
            }
        )
    )
    assert "SECRET" not in out and TEXT not in out
    assert "STOP" in out


def test_valid_stream_accepts_without_text_leak():
    raw = frame(content_event(TEXT, 10, 5)) + frame(content_event(TEXT, 10, 8, finish="STOP"))
    outcome = d.classify_stream(fresh_decoder(), raw)
    assert outcome["finish"] == "accepted"
    assert outcome["usage"] == {"input_tokens": 10, "output_tokens": 8}
    assert outcome["unprocessed"] == 0
    assert all(e["decoder"] == "accepted" for e in outcome["events"])
    dumped = json.dumps(outcome)
    assert TEXT not in dumped and "STOP" in dumped


def test_unknown_envelope_field_rejected_with_count():
    payload = content_event(TEXT, 10, 5, finish="STOP")
    payload["mystery"] = "SECRET-VALUE"
    outcome = d.classify_stream(fresh_decoder(), frame(payload))
    assert outcome["events"][0]["decoder"] == "Unsupported native envelope or provider state"
    assert outcome["events"][0]["structure"]["unknown_field_count"] == 1
    assert outcome["finish"] == "not_attempted_after_rejection"
    assert "SECRET" not in json.dumps(outcome) and TEXT not in json.dumps(outcome)


def test_usage_decrease_rejected():
    raw = frame(content_event(TEXT, 10, 8)) + frame(content_event(TEXT, 10, 5, finish="STOP"))
    outcome = d.classify_stream(fresh_decoder(), raw)
    assert outcome["events"][1]["decoder"] == "Native cumulative usage decreased"
    assert outcome["unprocessed"] == 0


def test_truncated_stream_finish_rejected():
    outcome = d.classify_stream(fresh_decoder(), frame(content_event(TEXT, 10, 5)))
    assert outcome["finish"] == "Native stream ended without clean finish evidence"


def test_content_after_finish_rejected():
    raw = frame(content_event(TEXT, 10, 5, finish="STOP")) + frame(content_event(TEXT, 10, 6))
    outcome = d.classify_stream(fresh_decoder(), raw)
    assert outcome["events"][1]["decoder"] == "Native content arrived after finish"


def test_fragmented_feed_accepted():
    decoder = fresh_decoder()
    payload = frame(content_event(TEXT, 10, 5, finish="STOP"))
    part, rest = payload[:11], payload[11:]
    assert decoder.feed(part) == []
    reason, _ = d.feed_event(decoder, rest.rstrip(b"\n"), b"\n\n")
    assert reason is None
    decoder.finish()


def test_oversized_frame_halts(monkeypatch):
    monkeypatch.setattr(d, "EVENT_BYTES", 16)
    outcome = d.classify_stream(fresh_decoder(), frame(content_event(TEXT, 10, 5)))
    assert outcome["events"][0]["kind"] == "oversized"


def sse_response(payloads, status=200, headers=None):
    body = b"".join(frame(p) for p in payloads)
    merged = {"content-type": "text/event-stream"}
    merged.update(headers or {})
    return httpx.Response(status, content=body, headers=merged)


@respx.mock
@pytest.mark.usefixtures("bound")
def test_live_valid_stream_single_dispatch_preserves_debit(capsys):
    route = respx.post(d.ROOT).mock(
        return_value=sse_response(
            [content_event(TEXT, 10, 5), content_event(TEXT, 10, 8, finish="STOP")]
        )
    )
    d.execute()
    assert route.call_count == 1
    assert route.calls[0].request.headers["accept-encoding"] == "identity"
    result = json.loads((d.DIRECTORY / "result.json").read_text())
    assert result["status"] == "diagnostic_complete"
    assert result["finish"] == "accepted"
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 8}
    assert TEXT not in (d.DIRECTORY / "result.json").read_text()
    marker = json.loads((d.DIRECTORY / "consumed.json").read_text())
    assert marker["conservative_debit_usd"] == d.DEBIT
    with pytest.raises(ValueError, match="already claimed"):
        d.execute()
    assert route.call_count == 1
    capsys.readouterr()


@respx.mock
@pytest.mark.usefixtures("bound")
def test_live_unknown_field_reports_reason():
    payload = content_event(TEXT, 10, 5, finish="STOP")
    payload["mystery"] = 1
    respx.post(d.ROOT).mock(return_value=sse_response([payload]))
    d.execute()
    result = json.loads((d.DIRECTORY / "result.json").read_text())
    assert result["status"] == "diagnostic_complete"
    assert result["events"][0]["decoder"] == "Unsupported native envelope or provider state"


@respx.mock
@pytest.mark.parametrize("status", [307, 429, 502])
@pytest.mark.usefixtures("bound")
def test_unexpected_status_is_durable(status):
    route = respx.post(d.ROOT).mock(return_value=httpx.Response(status, content=b"{}"))
    d.execute()
    assert route.call_count == 1
    result = json.loads((d.DIRECTORY / "result.json").read_text())
    assert result["status"] == "consumed_failed"
    assert result["http_status"] == status


@respx.mock
@pytest.mark.usefixtures("bound")
def test_compressed_response_rejected():
    import gzip

    payload = frame(content_event(TEXT, 10, 5))
    response = httpx.Response(
        200,
        content=gzip.compress(payload),
        headers={"content-type": "text/event-stream", "content-encoding": "gzip"},
    )
    route = respx.post(d.ROOT).mock(return_value=response)
    d.execute()
    assert route.call_count == 1
    assert json.loads((d.DIRECTORY / "result.json").read_text())["status"] == "consumed_failed"


@respx.mock
@pytest.mark.usefixtures("bound")
def test_transport_failure_is_durable():
    route = respx.post(d.ROOT).mock(side_effect=httpx.ConnectError("synthetic"))
    d.execute()
    assert route.call_count == 1
    assert json.loads((d.DIRECTORY / "result.json").read_text())["status"] == "consumed_failed"


@respx.mock
@pytest.mark.usefixtures("bound")
def test_result_only_state_refused_before_egress():
    route = respx.post(d.ROOT).mock(
        return_value=sse_response([content_event(TEXT, 10, 5, finish="STOP")])
    )
    (d.DIRECTORY).mkdir(parents=True, exist_ok=True)
    (d.DIRECTORY / "result.json").write_text("{}")
    with pytest.raises(ValueError, match="already claimed"):
        d.execute()
    assert route.call_count == 0


def test_function_call_rejected_with_specific_reason():
    payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "id": "call_1",
                                "name": "undeclared_fn",
                                "args": {},
                            }
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": usage(10, 5),
    }
    outcome = d.classify_stream(fresh_decoder(), frame(payload))
    assert outcome["events"][0]["decoder"] == "Unsupported Google tool deltas"
    assert outcome["finish"] == "not_attempted_after_rejection"


def test_unparseable_frame_reports_bounded_json_reason():
    outcome = d.classify_stream(fresh_decoder(), b"data: not-json{{{\n\n")
    assert outcome["events"][0]["structure"] == {"kind": "unparseable"}
    assert outcome["events"][0]["decoder"] == "Invalid bounded JSON"


def test_structure_depth_bound():
    deep = {}
    cursor = deep
    for _ in range(d.MAX_DEPTH + 2):
        cursor["candidates"] = {}
        cursor = cursor["candidates"]
    dumped = json.dumps(d.structure(deep))
    assert "depth_bound" in dumped


def test_enforce_bounds_deadline_and_size(monkeypatch):
    with pytest.raises(ValueError):
        d.enforce_bounds(bytearray(8), b"", 0)
    monkeypatch.setattr(d, "MAX_BYTES", 8)
    with pytest.raises(ValueError):
        d.enforce_bounds(bytearray(4), b"x" * 5, float("inf"))


@pytest.mark.usefixtures("bound")
def test_concurrent_prepare_single_winner():
    import threading

    barrier = threading.Barrier(2)
    results = []

    def attempt():
        barrier.wait()
        try:
            d.prepare()
            results.append("consumed")
        except (FileExistsError, ValueError):
            results.append("refused")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == ["consumed", "refused"]


@respx.mock
@pytest.mark.usefixtures("bound")
def test_read_timeout_is_durable():
    route = respx.post(d.ROOT).mock(side_effect=httpx.ReadTimeout("synthetic"))
    d.execute()
    assert route.call_count == 1
    assert json.loads((d.DIRECTORY / "result.json").read_text())["status"] == "consumed_failed"


def test_heartbeat_frame_accepted_as_no_data():
    raw = (
        b": heartbeat\n\n"
        + frame(content_event(TEXT, 10, 5))
        + frame(content_event(TEXT, 10, 8, finish="STOP"))
    )
    outcome = d.classify_stream(fresh_decoder(), raw)
    assert outcome["events"][0]["kind"] == "no_data"
    assert outcome["events"][0]["decoder"] == "accepted"
    assert outcome["finish"] == "accepted"


def test_rejected_heartbeat_halts_without_finish(monkeypatch):
    real_feed = d.feed_event

    def poisoned(decoder, frame, delimiter):
        if not d.event_data(frame).strip():
            return "Native cumulative usage decreased", 0
        return real_feed(decoder, frame, delimiter)

    monkeypatch.setattr(d, "feed_event", poisoned)
    raw = b": heartbeat\n\n" + frame(content_event(TEXT, 10, 5, finish="STOP"))
    outcome = d.classify_stream(fresh_decoder(), raw)
    assert outcome["events"][0]["kind"] == "no_data"
    assert outcome["events"][0]["decoder"] == "Native cumulative usage decreased"
    assert outcome["finish"] == "not_attempted_after_rejection"
    assert outcome["unprocessed"] == 1


def test_oversized_state_file_refused(bound, monkeypatch):
    monkeypatch.setattr(d, "MAX_BYTES", 16)
    (bound / "runner5" / "manifest.json").write_text(json.dumps({"oversized": "x" * 64}))
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_tampered_ca6_manifest_refused(bound):
    p = bound / "runner5" / "manifest.json"
    manifest = json.loads(p.read_text())
    manifest["run"] = "tampered"
    p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_failed_ca6_staging_entry_refused(bound):
    p = bound / "runner5" / "ledger.json"
    ledger = json.loads(p.read_text())
    ledger["entries"][0]["result"]["status"] = "failed"
    p.write_text(json.dumps(ledger))
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_missing_packet_refused(bound):
    (bound / "stream-diagnostic-packet.json").unlink()
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_packet_executor_mismatch_refused(bound):
    p = bound / "stream-diagnostic-packet.json"
    packet = json.loads(p.read_text())
    packet["executor_sha256"] = "0" * 64
    p.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="executor binding"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_packet_history_pin_mismatch_refused(bound):
    p = bound / "stream-diagnostic-packet.json"
    packet = json.loads(p.read_text())
    packet["ca6_ledger_sha256"] = "0" * 64
    p.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="history binding"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_packet_funding_mismatch_refused(bound):
    p = bound / "stream-diagnostic-packet.json"
    packet = json.loads(p.read_text())
    packet["stage_seed_usd"] = 0.09
    p.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="funding binding"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_packet_request_mismatch_refused(bound):
    p = bound / "stream-diagnostic-packet.json"
    packet = json.loads(p.read_text())
    packet["request_sha256"] = "0" * 64
    p.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="request binding"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_debit_history_reconciliation_refused(bound):
    p = bound / "staging5-final-admin.json"
    snapshot = json.loads(p.read_text())
    live = snapshot["credit_groups"]["opencode-account"]["live"]
    live["estimated_remaining_usd"] = live["estimated_remaining_usd"] + 0.001
    p.write_text(json.dumps(snapshot))
    q = bound / "stream-diagnostic-packet.json"
    q.write_text(
        json.dumps({**json.loads(q.read_text()), "ca6_snapshot_sha256": d.fingerprint(snapshot)})
    )
    with pytest.raises(ValueError, match="does not reconcile"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_packet_identity_mismatch_refused(bound):
    p = bound / "stream-diagnostic-packet.json"
    packet = json.loads(p.read_text())
    packet["diagnostic_id"] = "other"
    p.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="packet unavailable"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_packet_dependency_mismatch_refused(bound):
    p = bound / "stream-diagnostic-packet.json"
    packet = json.loads(p.read_text())
    packet["dependency_sha256"] = {"google_native": "0" * 64}
    p.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="dependency binding"):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_stopped_flag_missing_refused(bound):
    p = bound / "staging5-stopped.json"
    stopped = json.loads(p.read_text())
    del stopped["unused_allocation_not_transferred"]
    p.write_text(json.dumps(stopped))
    (bound / "stream-diagnostic-packet.json").write_text(
        json.dumps(
            {
                **json.loads((bound / "stream-diagnostic-packet.json").read_text()),
                "ca6_stopped_proof_sha256": d.fingerprint(stopped),
            }
        )
    )
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()
