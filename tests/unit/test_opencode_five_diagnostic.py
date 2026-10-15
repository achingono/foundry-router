"""Diagnostic authorization, accounting, sanitization and failure boundaries."""

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path("scripts/quality").resolve()))
import opencode_five_diagnostic as d
import pytest
import respx


@pytest.fixture
def bound(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "PRIVATE", tmp_path)
    monkeypatch.setattr(d, "DIRECTORY", tmp_path / "diagnostic-once")
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    spec = d.validation.manifest(
        "sha256:" + "a" * 64, {"staging": "b" * 64, "production": "c" * 64}
    )
    digest = d.fingerprint(spec)
    monkeypatch.setattr(d, "ORIGINAL_MANIFEST", digest)
    files = {
        "runner/manifest.json": spec,
        "failed-stage-final-admin.json": {
            "credit_groups": {
                "opencode-account": {
                    "live": {
                        "estimated_remaining_usd": d.REMAINING,
                        "active_reservations": 0,
                        "reserved_inflight_usd": 0,
                    }
                }
            }
        },
        "failed-stage-stopped-proof.json": {"running": False, "container_id": "synthetic"},
        "runner/ledger.json": {
            "manifest_sha256": digest,
            "entries": [
                {"reserved": True, "result": {"status": "failed", "id": "staging-0-nonstream"}},
                *[{"reserved": False, "result": None} for _ in range(17)],
            ],
        },
        "runner/identity.json": {"manifest_sha256": digest},
        ".local/share/opencode/auth.json": {"opencode": {"key": "synthetic-key"}},
    }
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    (tmp_path / "stage-container-id.txt").write_text("synthetic")
    return tmp_path


@pytest.mark.usefixtures("bound")
def test_consumed_binding_and_no_replay():
    _, _, body = d.prepare()
    marker = json.loads((d.DIRECTORY / "consumed.json").read_text())
    assert marker["native_body_sha256"] == d.fingerprint(body)
    assert marker["remaining_after_usd"] == pytest.approx(0.095982)
    assert marker["profile"]["native_thinking_level"] == "low"
    with pytest.raises(FileExistsError):
        d.prepare()


@pytest.mark.parametrize(
    "field,value",
    [
        ("estimated_remaining_usd", 0.1),
        ("estimated_remaining_usd", float("nan")),
        ("active_reservations", 1),
        ("reserved_inflight_usd", 0.001),
    ],
)
def test_invalid_snapshot_refuses_before_consumption(bound, field, value):
    p = bound / "failed-stage-final-admin.json"
    snapshot = json.loads(p.read_text())
    snapshot["credit_groups"]["opencode-account"]["live"][field] = value
    p.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError):
        d.prepare()
    assert not d.DIRECTORY.exists()


def test_sanitizer_hides_unknown_keys_and_text():
    body = {
        "secret-output": "secret-value",
        "candidates": [
            {
                "content": {"parts": [{"text": "secret-text", "thoughtSignature": "secret-state"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 3},
    }
    out = json.dumps(d.structure(body))
    assert "secret-" not in out
    assert "STOP" in out
    assert d.structure("private", field="finishReason") == {"type": "str"}
    assert d.structure(False, field="promptTokenCount") == {"type": "bool"}
    assert d.structure({}, depth=99) == {"type": "depth_bound"}


def test_bounds():
    with pytest.raises(ValueError):
        d.enforce_bounds(bytearray(d.MAX_BYTES), b"x", float("inf"))
    with pytest.raises(ValueError):
        d.enforce_bounds(b"", b"", 0)


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            200,
            json={
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 0,
                    "totalTokenCount": 12,
                }
            },
        ),
        httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "synthetic"}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 13,
                },
            },
        ),
        httpx.Response(200, content=b"invalid"),
        httpx.Response(200, content=b"x", headers={"content-encoding": "gzip"}),
    ],
)
@pytest.mark.usefixtures("bound")
def test_diagnostic_single_dispatch_preserves_debit(response, capsys):
    route = respx.post(d.ROOT).mock(return_value=response)
    d.execute()
    assert route.call_count == 1
    marker = json.loads((d.DIRECTORY / "consumed.json").read_text())
    assert marker["conservative_debit_usd"] == 0.004
    assert (d.DIRECTORY / "result.json").exists()
    assert route.calls[0].request.headers["accept-encoding"] == "identity"
    with pytest.raises(FileExistsError):
        d.execute()
    assert route.call_count == 1
    capsys.readouterr()


@respx.mock
@pytest.mark.usefixtures("bound")
def test_transport_failure_is_durable():
    route = respx.post(d.ROOT).mock(side_effect=httpx.ConnectError("synthetic"))
    d.execute()
    assert route.call_count == 1
    assert json.loads((d.DIRECTORY / "result.json").read_text())["status"] == "consumed_failed"
