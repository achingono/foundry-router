"""Isolated Table verifier consumes SSE incrementally and never repeats ambiguous cases."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import table_real_prepare as prepare
import table_real_verify as verify

ORIGIN = "https://synthetic-test.eastus.azurecontainerapps.io"


def private():
    return {
        "origin": ORIGIN,
        "config_fingerprint": "a" * 64,
        "deployment_fingerprint": "b" * 64,
        "client_secret_ref": "https://synthetic.vault.azure.net/secrets/client/" + "c" * 32,
        "admin_secret_ref": "https://synthetic.vault.azure.net/secrets/admin/" + "d" * 32,
        "models": [
            {
                "label": f"model-{index}",
                "model": f"m{index}",
                "backend": f"b{index}",
                "input_per_million": 10,
                "output_per_million": 30,
                "reserve_usd": 0.03136,
            }
            for index in (1, 2)
        ],
    }


def terminal(inputs=7, outputs=2):
    return {
        "status": "completed",
        "output": [{"content": [{"type": "output_text", "text": "ready"}]}],
        "usage": {
            "input_tokens": inputs,
            "output_tokens": outputs,
            "total_tokens": inputs + outputs,
        },
    }


def test_one_byte_sse_with_crlf_and_terminal_usage():
    wire = (
        b"data: "
        + json.dumps({"type": "response.completed", "response": terminal()}).encode()
        + b"\r\n\r\n"
    )
    observer = verify.ResponseObservation()
    for byte in wire:
        observer.feed(bytes([byte]))
    assert observer.accepted() and observer.usage == (7, 2, 9)


def test_larger_observed_usage_not_hidden_by_terminal():
    observer = verify.ResponseObservation()
    observer.observe({"usage": {"input_tokens": 7, "output_tokens": 1500}})
    observer.observe(terminal())
    assert not observer.accepted() and observer.output_tokens == 1500


def test_partial_and_oversize_frame_reject():
    observer = verify.ResponseObservation()
    observer.feed(b"data: {")
    assert not observer.accepted()
    with pytest.raises(ValueError):
        observer.feed(b"x" * verify.MAX_FRAME_BYTES)


@pytest.mark.parametrize(
    "origin",
    ["https://other.azurecontainerapps.io", "http://synthetic-test.eastus.azurecontainerapps.io"],
)
def test_origin_must_match_private_deployment(origin):
    with pytest.raises(ValueError):
        verify.validate_private(private(), origin)


@pytest.mark.asyncio
async def test_ambiguous_requests_never_repeat(tmp_path):
    data = private()
    path = tmp_path / "ledger.json"
    ledger = {
        "fingerprint": data["config_fingerprint"],
        "cases": {
            "model-1-nonstream": {"reserved_usd": 0.03136, "result": None},
            "model-2-nonstream": {"reserved_usd": 0.03136, "result": None},
        },
    }
    path.write_text(json.dumps(ledger))
    calls = []
    result = await verify.execute(
        data,
        ORIGIN,
        ["synthetic"] * 2,
        path,
        httpx.MockTransport(calls.append),
    )
    assert result == ledger and not calls


@pytest.mark.asyncio
async def test_four_cases_settle_and_resume_without_dispatch(tmp_path):
    data = private()
    balances = {"b1": 100.0, "b2": 100.0}
    posts = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "config": {"retry_attempts": 0},
                    "model_aliases": {},
                    "models": {
                        m["model"]: {"backends": {m["backend"]: 1.0}} for m in data["models"]
                    },
                    "backends": {
                        backend: {
                            "live": {
                                "estimated_remaining_usd": amount,
                                "active_reservations": 0,
                                "reserved_inflight_usd": 0,
                                "current_cycle_start_utc": "2026-10-01T00:00:00Z",
                            }
                        }
                        for backend, amount in balances.items()
                    },
                },
            )
        posts.append(request)
        body = json.loads(request.content)
        backend = "b" + body["model"][-1]
        balances[backend] -= 0.00013
        response = terminal()
        if body["stream"]:
            return httpx.Response(
                200,
                content=b"data: "
                + json.dumps({"type": "response.completed", "response": response}).encode()
                + b"\n\n",
            )
        return httpx.Response(200, json=response)

    path = tmp_path / "ledger.json"
    result = await verify.execute(
        data, ORIGIN, ["synthetic"] * 2, path, httpx.MockTransport(handler)
    )
    assert len(posts) == 4 and all(
        item["result"]["status"] == "passed" for item in result["cases"].values()
    )
    await verify.execute(data, ORIGIN, ["synthetic"] * 2, path, httpx.MockTransport(handler))
    assert len(posts) == 4


def test_failed_result_with_arbitrary_field_rejected():
    data = {
        "fingerprint": "a" * 64,
        "cases": {
            "model-1-nonstream": {
                "reserved_usd": 0.03136,
                "result": {"status": "failed", "secret": "private"},
            }
        },
    }
    with pytest.raises(ValueError):
        verify.validate_ledger(data, private())


def settings_values():
    return {
        "backends_json": json.dumps(
            {
                f"b{index}": {
                    "endpoint": f"https://synthetic{index}.openai.azure.com",
                    "credential": "synthetic",
                    "deployment": f"d{index}",
                }
                for index in (1, 2)
            }
        ),
        "models_json": json.dumps(
            {f"m{index}": {"backends": {f"b{index}": 1.0}} for index in (1, 2)}
        ),
        "pricing_json": json.dumps(
            {f"m{index}": {"input_per_million": 10, "output_per_million": 30} for index in (1, 2)}
        ),
        "client_api_keys_json": '["synthetic"]',
        "admin_api_keys_json": '["other"]',
    }


def test_model_contract_requires_single_backend_and_budget():
    values = settings_values()
    assert len(prepare.validate_model_contract(values)) == 2
    values["models_json"] = json.dumps(
        {"m1": {"backends": {"b1": 1.0, "b2": 1.0}}, "m2": {"backends": {"b2": 1.0}}}
    )
    with pytest.raises(ValueError):
        prepare.validate_model_contract(values)


def test_budget_refuses_before_traffic():
    data = private()
    data["models"][0]["output_per_million"] = 3000
    with pytest.raises(ValueError):
        verify.validate_private(data, ORIGIN)


def test_partial_and_total_usage_preserved_independently():
    observer = verify.ResponseObservation()
    observer.observe({"usage": {"input_tokens": 65, "total_tokens": 2000}})
    observer.observe(terminal())
    assert observer.input_tokens == 65 and observer.total_tokens == 2000
    assert not observer.accepted()


def test_terminal_total_must_match_counts():
    response = terminal()
    response["usage"]["total_tokens"] = 2000
    observer = verify.ResponseObservation()
    with pytest.raises(ValueError):
        observer.observe(response)
    assert observer.total_tokens == 2000


@pytest.mark.parametrize(
    "field,value",
    [
        ("config_fingerprint", "private-state"),
        ("client_secret_ref", "https://other/secrets/client"),
    ],
)
def test_private_sensitive_values_fail_before_display(field, value):
    data = private()
    data[field] = value
    with pytest.raises(ValueError):
        verify.validate_private(data, ORIGIN)


def test_exact_pinned_secret_handles_existing_version():
    reference = "https://synthetic.vault.azure.net/secrets/client/" + "c" * 32
    prepare.validate_pinned(reference, {"id": reference})
    with pytest.raises(ValueError):
        prepare.validate_pinned(reference, {"id": reference + "/extra"})


@pytest.mark.asyncio
async def test_partial_overrun_persisted_before_stalled_post_status(tmp_path, monkeypatch):
    import asyncio

    data = private()
    calls = []
    gets = [0]

    async def status(_client, _url, _headers):
        gets[0] += 1
        if gets[0] > 1:
            await asyncio.sleep(1)
        return {
            "config": {"retry_attempts": 0},
            "model_aliases": {},
            "models": {m["model"]: {"backends": {m["backend"]: 1}} for m in data["models"]},
            "backends": {
                m["backend"]: {
                    "live": {
                        "estimated_remaining_usd": 100,
                        "active_reservations": 0,
                        "reserved_inflight_usd": 0,
                        "current_cycle_start_utc": "2026-10-01",
                    }
                }
                for m in data["models"]
            },
        }

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"usage": {"output_tokens": 2000}})

    monkeypatch.setattr(verify, "bounded_get", status)
    monkeypatch.setattr(verify, "DEADLINE_SECONDS", 0.05)
    monkeypatch.setattr(verify, "SETTLEMENT_HEADROOM_SECONDS", 0.01)
    path = tmp_path / "ledger.json"
    await verify.execute(data, ORIGIN, ["synthetic"] * 2, path, httpx.MockTransport(handler))
    saved = json.loads(path.read_text())
    result = saved["cases"]["model-1-nonstream"]["result"]
    assert result["overrun"] and result["output_tokens"] == 2000
    assert result["estimated_debit_usd"] == 0.06 and len(calls) == 1


def test_restart_generation_requires_ready_changed_process():
    import table_real_restart as restart

    replicas = [
        {
            "name": "replica",
            "containers": [
                {
                    "ready": True,
                    "started": True,
                    "containerId": "original",
                    "restartCount": 0,
                    "runningStateDetails": "started-original",
                }
            ],
        }
    ]
    original = restart.replica_generation(replicas)
    replicas[0]["containers"][0]["runningStateDetails"] = "metadata changed"
    assert not restart.fresh_generation(original, restart.replica_generation(replicas))
    replicas[0]["containers"][0]["ready"] = False
    assert restart.replica_generation(replicas) is None
    replicas[0]["containers"][0].update(ready=True, containerId="replacement", restartCount=1)
    assert restart.fresh_generation(original, restart.replica_generation(replicas))


@pytest.mark.asyncio
async def test_whole_case_deadline_bounds_status(monkeypatch):
    import asyncio

    monkeypatch.setattr(verify, "DEADLINE_SECONDS", 0.02)

    async def stalled(*_args):
        await asyncio.sleep(1)

    monkeypatch.setattr(verify, "bounded_get", stalled)
    with pytest.raises(TimeoutError):
        await verify.run_case(
            None, ORIGIN, "synthetic", "other", private()["models"][0], False, private()["models"]
        )
