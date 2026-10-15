"""Durable eighteen-slot acceptance, immutable binding and fail-closed replay."""

import copy
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path("scripts/quality").resolve()))
import opencode_five_validation as run

IMAGE = "sha256:" + "a" * 64


class FakeRouter:
    def __init__(self, *, failure=None, environment="staging"):
        self.calls = []
        self.failure = failure
        self.remaining = 0.1 if environment == "staging" else 9.9
        self.admin = {
            "models": {
                pool: {"backends": {f"b{i}": 1}, "streaming_enabled": enabled}
                for i, (pool, _, _, _, _, enabled) in enumerate(run.ROSTER)
            },
            "backends": {
                f"b{i}": {
                    "provider": provider,
                    "deployment": deployment,
                    "credit_group": run.GROUP,
                    "api_surface": "native" if provider == "opencode_google" else "openai_compat",
                }
                for i, (_, deployment, provider, _, _, _) in enumerate(run.ROSTER)
            },
            "credit_groups": {
                run.GROUP: {
                    "reserve_policy": {
                        "min_credit_reserve_usd": 0.05,
                        "min_credit_reserve_percent": 5.0,
                    },
                    "cycle_start_day": 1,
                    "cycle_allowance_usd": 0.1 if environment == "staging" else 10,
                    "initial_estimated_remaining_usd": self.remaining,
                    "live": {
                        "active_reservations": 0,
                        "reserved_inflight_usd": 0,
                        "estimated_remaining_usd": self.remaining,
                    },
                }
            },
        }

    async def __call__(self, scope, receive, send):
        path = scope["path"]
        if path == "/admin/status":
            payload = copy.deepcopy(self.admin)
            payload["credit_groups"][run.GROUP]["live"]["estimated_remaining_usd"] = self.remaining
            status = 200
            content = json.dumps(payload).encode()
            content_type = b"application/json"
        else:
            body = json.loads((await receive())["body"])
            self.calls.append(body)
            match = next(row for row in run.ROSTER if row[0] == body["model"])
            output = body["max_output_tokens"] + 1 if self.failure == "overbound" else 5
            self.remaining -= (10 * match[3] + output * match[4]) / 1_000_000
            payload = {
                "status": "completed",
                "output": [{"content": [{"type": "output_text", "text": "synthetic"}]}],
                "usage": {"input_tokens": 10, "output_tokens": output, "total_tokens": 10 + output},
            }
            if self.failure == "usage":
                payload.pop("usage")
            if self.failure == "incomplete":
                payload["status"] = "incomplete"
            if self.failure == "empty":
                payload["output"] = []
            if self.failure == "debit":
                self.remaining -= 0.01
            status = 503 if self.failure == "http" else 200
            if body["stream"]:
                event = {"type": "response.completed", "response": payload}
                content = f"data: {json.dumps(event)}\n\n".encode()
                content_type = b"text/event-stream"
            else:
                content = json.dumps(payload).encode()
                content_type = b"application/json"
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", content_type)],
            }
        )
        await send({"type": "http.response.body", "body": content})


def specification():
    return run.manifest(
        IMAGE,
        {
            env: run.fingerprint(run.policy_projection(FakeRouter(environment=env).admin))
            for env in ("staging", "production")
        },
    )


async def execute(tmp_path, router, environment="staging", image=IMAGE):
    return await run.execute(
        environment,
        directory=tmp_path,
        image=image,
        base_url="https://router.example.test",
        caller="synthetic-caller",
        admin="synthetic-admin",
        transport=httpx.ASGITransport(app=router),
    )


async def test_eighteen_passes_then_replay_refused(tmp_path):
    run.initialize(tmp_path, specification())
    stage = FakeRouter()
    state = await execute(tmp_path, stage)
    assert len(stage.calls) == 9
    with pytest.raises(ValueError, match="no replay"):
        await execute(tmp_path, stage)
    production = FakeRouter(environment="production")
    state = await execute(tmp_path, production, "production")
    assert len(production.calls) == 9 and all(
        e["result"]["status"] == "passed" for e in state["entries"]
    )
    serialized = (tmp_path / "ledger.json").read_text()
    assert (
        "synthetic-caller" not in serialized
        and "synthetic-admin" not in serialized
        and 'synthetic"' not in serialized
    )


async def test_production_blocks_before_staging(tmp_path):
    run.initialize(tmp_path, specification())
    router = FakeRouter(environment="production")
    with pytest.raises(ValueError, match="Staging"):
        await execute(tmp_path, router, "production")
    assert not router.calls


@pytest.mark.parametrize("failure", ["usage", "incomplete", "empty", "debit", "http", "overbound"])
async def test_failure_consumes_and_halts_without_replay(tmp_path, failure):
    run.initialize(tmp_path, specification())
    router = FakeRouter(failure=failure)
    with pytest.raises(ValueError, match="halted"):
        await execute(tmp_path, router)
    assert len(router.calls) == 1
    with pytest.raises(ValueError):
        await execute(tmp_path, router)
    assert len(router.calls) == 1


async def test_image_and_configuration_binding(tmp_path):
    run.initialize(tmp_path, specification())
    router = FakeRouter()
    with pytest.raises(ValueError, match="digest"):
        await execute(tmp_path, router, image="sha256:" + "b" * 64)
    assert not router.calls
    router.admin["models"][run.ROSTER[0][0]]["streaming_enabled"] = False
    with pytest.raises(ValueError, match="halted"):
        await execute(tmp_path, router)
    assert not router.calls


def test_initialize_and_deleted_state_cannot_reset(tmp_path):
    run.initialize(tmp_path, specification())
    with pytest.raises(ValueError):
        run.initialize(tmp_path, specification())
    (tmp_path / "ledger.json").unlink()
    with pytest.raises(ValueError):
        run.initialize(tmp_path, specification())
    with pytest.raises(ValueError):
        run.read_state(tmp_path)


def test_tampered_manifest_and_sparse_result_refused(tmp_path):
    run.initialize(tmp_path, specification())
    ledger = tmp_path / "ledger.json"
    data = json.loads(ledger.read_text())
    data["entries"][0] = {"reserved": True, "result": {"status": "passed"}}
    ledger.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run.read_state(tmp_path)


async def test_ambiguous_reservation_blocks(tmp_path):
    run.initialize(tmp_path, specification())
    ledger = tmp_path / "ledger.json"
    data = json.loads(ledger.read_text())
    data["entries"][0]["reserved"] = True
    ledger.write_text(json.dumps(data))
    router = FakeRouter()
    with pytest.raises(ValueError):
        await execute(tmp_path, router)
    assert not router.calls


def test_only_reviewed_replacement_identity_preserves_seed_and_original(tmp_path):
    router = FakeRouter()
    hashes = {
        env: run.fingerprint(run.policy_projection(router.admin))
        for env in ("staging", "production")
    }
    original = run.manifest(IMAGE, hashes)
    replacement = run.manifest(IMAGE, hashes, run_id=run.REPLACEMENT_RUN)
    assert original["run"] == run.RUN and original["staging_allocation_usd"] == 0.1
    assert replacement["staging_allocation_usd"] == 0.095982
    assert replacement["production_seed_usd"] == 9.9
    assert replacement["cases"] == original["cases"]
    run.initialize(tmp_path / "original", original)
    run.initialize(tmp_path / "replacement", replacement)
    assert run.read_state(tmp_path / "original")[0] == original
    assert run.read_state(tmp_path / "replacement")[0] == replacement
    with pytest.raises(ValueError, match="Unreviewed"):
        run.manifest(IMAGE, hashes, run_id="arbitrary")
    tampered = {**replacement, "staging_allocation_usd": 0.1}
    with pytest.raises(ValueError):
        run.initialize(tmp_path / "tampered", tampered)


def test_projection_excludes_only_inherited_initial_seed():
    router = FakeRouter()
    base = run.policy_projection(router.admin)
    changed = copy.deepcopy(router.admin)
    group = copy.deepcopy(changed["credit_groups"][run.GROUP])
    changed["credit_groups"]["inherited"] = group
    before = run.policy_projection(changed)
    changed["credit_groups"]["inherited"]["initial_estimated_remaining_usd"] = 123
    assert run.policy_projection(changed) == before
    changed["credit_groups"][run.GROUP]["initial_estimated_remaining_usd"] = 0.095982
    assert run.policy_projection(changed) != before
    assert base["accounts"][run.GROUP]["initial_estimated_remaining_usd"] == 0.1


def test_vertex_identity_fixed_budget_and_history_unchanged(tmp_path):
    hashes = {"staging": "a" * 64, "production": "b" * 64}
    spec = run.manifest(IMAGE, hashes, run_id=run.VERTEX_RUN)
    assert spec["staging_allocation_usd"] == 0.095514
    assert spec["production_seed_usd"] == 9.9
    run.initialize(tmp_path, spec)
    assert run.read_state(tmp_path)[0] == spec
    assert run.manifest(IMAGE, hashes)["staging_allocation_usd"] == 0.1
    assert (
        run.manifest(IMAGE, hashes, run_id=run.REPLACEMENT_RUN)["staging_allocation_usd"]
        == 0.095982
    )


def test_nonstream_manifest_cases_and_historical_requests_are_independent():
    hashes = {"staging": "a" * 64, "production": "b" * 64}
    original = run.manifest(IMAGE, hashes)
    spec = run.manifest(IMAGE, hashes, run_id=run.NONSTREAM_RUN)
    assert len(spec["cases"]) == spec["max_dispatches"] == 14
    assert sum(c["environment"] == "staging" for c in spec["cases"]) == 7
    assert spec["staging_allocation_usd"] == 0.09
    assert all(
        not c["stream"] and not c["streaming_enabled"] and c["request"]["max_output_tokens"] == 512
        for c in spec["cases"]
        if c["provider"] == "opencode_google"
    )
    spec["cases"][0]["request"]["input"] = "tampered"
    assert run.manifest(IMAGE, hashes) == original


@pytest.mark.asyncio
async def test_seven_stage_then_seven_production_and_failed_replay(tmp_path):
    router = FakeRouter()
    for pool, _, provider, *_ in run.ROSTER:
        if provider == "opencode_google":
            router.admin["models"][pool]["streaming_enabled"] = False
    hashes = {
        env: run.fingerprint(run.policy_projection(router.admin))
        for env in ("staging", "production")
    }
    spec = run.manifest(IMAGE, hashes, run_id=run.NONSTREAM_RUN)
    run.initialize(tmp_path, spec)
    with pytest.raises(ValueError, match="Staging"):
        await run.execute(
            "production",
            directory=tmp_path,
            image=IMAGE,
            base_url="https://router.test",
            caller="caller",
            admin="admin",
            transport=httpx.ASGITransport(app=router),
        )
    await run.execute(
        "staging",
        directory=tmp_path,
        image=IMAGE,
        base_url="https://router.test",
        caller="caller",
        admin="admin",
        transport=httpx.ASGITransport(app=router),
    )
    assert len(router.calls) == 7
    await run.execute(
        "production",
        directory=tmp_path,
        image=IMAGE,
        base_url="https://router.test",
        caller="caller",
        admin="admin",
        transport=httpx.ASGITransport(app=router),
    )
    assert len(router.calls) == 14
    with pytest.raises(ValueError, match="no replay"):
        await run.execute(
            "production",
            directory=tmp_path,
            image=IMAGE,
            base_url="https://router.test",
            caller="caller",
            admin="admin",
            transport=httpx.ASGITransport(app=router),
        )


def test_anthropic_nullable_run_retains_exact_nonstream_cases_and_seed(tmp_path):
    hashes = {"staging": "a" * 64, "production": "b" * 64}
    spec = run.manifest(IMAGE, hashes, run_id=run.ANTHROPIC_RUN)
    assert spec["staging_allocation_usd"] == 0.088
    assert spec["cases"] == run.manifest(IMAGE, hashes, run_id=run.NONSTREAM_RUN)["cases"]
    assert len(spec["cases"]) == 14
    run.initialize(tmp_path, spec)
    assert run.read_state(tmp_path)[0] == spec


def test_streaming_run_binds_fresh_seed_and_both_gemini_streams(tmp_path):
    hashes = {"staging": "a" * 64, "production": "b" * 64}
    spec = run.manifest(IMAGE, hashes, run_id=run.STREAMING_RUN)
    assert spec["run"] == "opencode-zen-five-gemini-streaming-v1"
    assert spec["staging_allocation_usd"] == 0.10
    assert spec["production_seed_usd"] == 9.9
    assert len(spec["cases"]) == spec["max_dispatches"] == 18
    assert sum(c["environment"] == "staging" for c in spec["cases"]) == 9
    google = [c for c in spec["cases"] if c["provider"] == "opencode_google"]
    assert len(google) == 8
    for env in ("staging", "production"):
        pairs = {(c["deployment"], c["stream"]) for c in google if c["environment"] == env}
        assert pairs == {
            ("gemini-3.8-flash", False),
            ("gemini-3.8-flash", True),
            ("gemini-4-argon", False),
            ("gemini-4-argon", True),
        }
    assert all(c["streaming_enabled"] for c in google)
    assert {(c["pool"], c["streaming_enabled"]) for c in spec["cases"]} == {
        ("gemini-3.8-flash-zen", True),
        ("gemini-4-argon-zen", True),
        ("claude-sonnet-5.5-zen", False),
        ("grok-4.7-zen", True),
        ("muse-spark-1.3-zen", True),
    }
    assert [c["id"] for c in spec["cases"]] == [
        f"{env}-{i}-{'stream' if s else 'nonstream'}"
        for env in ("staging", "production")
        for i, s in (
            (0, False),
            (0, True),
            (1, False),
            (1, True),
            (2, False),
            (3, False),
            (3, True),
            (4, False),
            (4, True),
        )
    ]
    assert all(
        (c["request"]["max_output_tokens"] == 128)
        if c["pool"] == "claude-sonnet-5.5-zen"
        else (c["request"]["max_output_tokens"] == 512)
        for c in spec["cases"]
    )
    assert all(c["request"]["stream"] == c["stream"] for c in spec["cases"])
    run.initialize(tmp_path, spec)
    assert run.read_state(tmp_path)[0] == spec


def test_subset_run_binds_three_pools_and_fresh_seed(tmp_path):
    hashes = {"staging": "a" * 64, "production": "b" * 64}
    spec = run.manifest(IMAGE, hashes, run_id=run.SUBSET_RUN)
    assert spec["run"] == "opencode-zen-five-subset-20261014"
    assert spec["staging_allocation_usd"] == 0.09
    assert spec["production_seed_usd"] == 9.9
    assert len(spec["cases"]) == spec["max_dispatches"] == 10
    assert sum(c["environment"] == "staging" for c in spec["cases"]) == 5
    assert {c["pool"] for c in spec["cases"]} == set(run.SUBSET_POOLS)
    assert "grok-4.7-zen" not in {c["pool"] for c in spec["cases"]}
    assert "muse-spark-1.3-zen" not in {c["pool"] for c in spec["cases"]}
    assert [c["id"] for c in spec["cases"]] == [
        f"{env}-{i}-{'stream' if s else 'nonstream'}"
        for env in ("staging", "production")
        for i, s in ((0, False), (0, True), (1, False), (1, True), (2, False))
    ]
    assert {(c["pool"], c["streaming_enabled"]) for c in spec["cases"]} == {
        ("gemini-3.8-flash-zen", True),
        ("gemini-4-argon-zen", True),
        ("claude-sonnet-5.5-zen", False),
    }
    run.initialize(tmp_path, spec)
    assert run.read_state(tmp_path)[0] == spec


def test_subset2_run_binds_lower_seed_and_live_production_fp(tmp_path):
    hashes = {"staging": "a" * 64, "production": "b" * 64}
    spec = run.manifest(IMAGE, hashes, run_id=run.SUBSET2_RUN)
    assert spec["run"] == "opencode-zen-five-subset2-20261014"
    assert spec["staging_allocation_usd"] == 0.085
    assert spec["production_seed_usd"] == 9.9
    assert len(spec["cases"]) == spec["max_dispatches"] == 10
    assert sum(c["environment"] == "staging" for c in spec["cases"]) == 5
    assert {c["pool"] for c in spec["cases"]} == set(run.SUBSET_POOLS)
    assert spec["cases"] == run.manifest(IMAGE, hashes, run_id=run.SUBSET_RUN)["cases"]
    run.initialize(tmp_path, spec)
    assert run.read_state(tmp_path)[0] == spec
