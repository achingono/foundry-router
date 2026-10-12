"""Offline staging-validation checks with a stateful fake deployed router."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import staging_validation as sv

PLAN_DIR = Path(__file__).resolve().parents[2] / "docs/plans/production-zen-openrouter"


def staging_manifest(**overrides):
    manifest = json.loads((PLAN_DIR / "manifest.staging.json").read_text())
    manifest.update(overrides)
    return manifest


def production_manifest(**overrides):
    manifest = json.loads((PLAN_DIR / "manifest.production.json").read_text())
    manifest.update(overrides)
    return manifest


class FakeApp(httpx.AsyncBaseTransport):
    """Simulates a deployed router with stateful credit balances."""

    def __init__(self, manifest, **options):
        self.manifest = manifest
        self.options = options
        self.calls: list[tuple] = []
        self.groups = {}
        for case in manifest["cases"]:
            group = f"group-{case['pool']}"
            self.groups[group] = 1000.0
        self.backends = {
            f"backend-{case['pool']}": {
                "provider": case["provider"],
                "deployment": case["deployment"],
                "credit_group": f"group-{case['pool']}",
                "supported_operations": ["responses"],
            }
            for case in manifest["cases"]
        }
        self.stuck_reservations = options.get("stuck_reservations", False)
        self.ready = options.get("ready", True)
        self.status_override = options.get("status_override", {})
        self.usage_override = options.get("usage_override", {})
        self.debit_scale = options.get("debit_scale", 1.0)

    def _admin(self):
        return {
            "models": {
                case["pool"]: {"backends": {f"backend-{case['pool']}": 1.0}}
                for case in self.manifest["cases"]
            },
            "backends": {
                backend_id: {
                    "provider": config["provider"],
                    "deployment": config["deployment"],
                    "credit_group": config["credit_group"],
                    "supported_operations": ["responses"],
                    "live": {},
                }
                for backend_id, config in self.backends.items()
            },
            "credit_groups": {
                group: {
                    "live": {
                        "estimated_remaining_usd": remaining,
                        "active_reservations": 1 if self.stuck_reservations else 0,
                        "reserved_inflight_usd": 0.5 if self.stuck_reservations else 0.0,
                    }
                }
                for group, remaining in self.groups.items()
            },
            "config": {"retry_attempts": 2, "retry_max_delay_seconds": 30.0},
        }

    def _usage(self, case_id):
        if case_id in self.usage_override:
            return self.usage_override[case_id]
        return {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}

    def _debit(self, case, usage):
        group = f"group-{case['pool']}"
        cost = (
            usage["input_tokens"] * case["input_per_million"]
            + usage["output_tokens"] * case["output_per_million"]
        ) / 1_000_000
        self.groups[group] -= cost * self.debit_scale
        return cost

    async def handle_async_request(self, request):  # noqa: PLR0911 -- fixed fake routes
        path = request.url.path
        if path == "/health/live":
            return httpx.Response(200, json={"status": "alive"})
        if path == "/health/ready":
            if not self.ready:
                return httpx.Response(503, json={"ready": False, "checks": {}})
            return httpx.Response(200, json={"ready": True, "checks": {}})
        if path == "/admin/status":
            if request.headers.get("x-admin-key") != "admin-key":
                return httpx.Response(401, json={"detail": "nope"})
            return httpx.Response(200, json=self._admin())
        if path == "/openai/v1/responses":
            if request.headers.get("api-key") != "client-key":
                return httpx.Response(401, json={"error": {"message": "auth"}})
            body = json.loads(request.content.decode())
            case = next(
                c
                for c in self.manifest["cases"]
                if c["pool"] == body.get("model") and c["stream"] is bool(body.get("stream"))
            )
            self.calls.append((case["id"], bool(body.get("stream"))))
            if case["id"] in self.status_override:
                status, payload = self.status_override[case["id"]]
                return httpx.Response(status, json=payload)
            usage = self._usage(case["id"])
            self._debit(case, usage)
            if body.get("stream"):
                terminal = json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "ready"}],
                                }
                            ],
                            "usage": usage,
                        },
                    }
                )
                payload = (
                    b'data: {"type":"response.created"}\n\ndata: ' + terminal.encode() + b"\n\n"
                )
                return httpx.Response(
                    200, content=payload, headers={"content-type": "text/event-stream"}
                )
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "ready"}],
                        }
                    ],
                    "usage": usage,
                },
            )
        raise AssertionError(f"unexpected path {path}")

    async def aclose(self):
        pass


def run_validation(tmp_path, manifest_data, app, production=False):
    return sv.execute_validation(
        manifest_data,
        stage_dir=tmp_path,
        base_url="http://staging.test",
        caller_key="client-key",
        admin_key="admin-key",
        production=production,
        transport_factory=lambda: app,
    )


def test_manifests_validate_with_allowance():
    for name in ("manifest.staging.json", "manifest.production.json"):
        manifest = json.loads((PLAN_DIR / name).read_text())
        summary = sv.validate_manifest(manifest)
        assert summary["run"] in (sv.STAGING_RUN_ID, sv.PRODUCTION_RUN_ID)


@pytest.mark.parametrize(
    "override",
    [
        {"version": 2},
        {"run": "other-run"},
        {"environment": "production"},
        {"prompt": "Something else."},
        {"max_output_tokens": 1024},
        {"allowance_usd": 0.0000001},
        {"cases": []},
    ],
)
def test_manifest_mutations_rejected(override):
    manifest = staging_manifest()
    manifest.update(override)
    with pytest.raises(ValueError):
        sv.validate_manifest(manifest)


def test_full_staging_pass_and_idempotent_rerun(tmp_path):
    app = FakeApp(staging_manifest())
    manifest = staging_manifest()
    results = run_validation(tmp_path, manifest, app)
    assert [item["case_id"] for item in results["attempts"]] == list(sv.STAGING_CASES)
    assert all(item["status"] == "passed" for item in results["attempts"])
    assert all(item["settlement_matches"] for item in results["attempts"])
    assert all(item["reservations_cleared"] for item in results["attempts"])
    assert sorted(call[0] for call in app.calls) == sorted(sv.STAGING_CASES)
    assert all(isinstance(item["retry_attempts"], int) for item in results["attempts"])
    rerun = run_validation(tmp_path, manifest, app)
    assert len(rerun["attempts"]) == 4
    assert len(app.calls) == 4
    dumped = (tmp_path / "results-staging.json").read_text() + (
        tmp_path / "ledger-staging.json"
    ).read_text()
    assert "client-key" not in dumped and "admin-key" not in dumped
    assert "Reply with the word ready." not in dumped


def test_first_failure_halts_remaining(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest, status_override={"staging-zen-nonstream": (500, {})})
    results = run_validation(tmp_path, manifest, app)
    assert len(results["attempts"]) == 1
    assert results["attempts"][0]["status"] == "failed"
    assert len(app.calls) == 1
    # A halted run never resumes, even to return its recorded failure.
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 1


def test_usage_over_preflight_bounds_halts(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(
        manifest,
        usage_override={
            "staging-zen-nonstream": {
                "input_tokens": 12,
                "output_tokens": 200,
                "total_tokens": 212,
            }
        },
    )
    results = run_validation(tmp_path, manifest, app)
    assert results["attempts"][0]["status"] == "failed"
    assert results["attempts"][0]["error_category"] == "acceptance_mismatch"
    assert len(app.calls) == 1


def test_settlement_mismatch_halts(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest, debit_scale=2.0)
    results = run_validation(tmp_path, manifest, app)
    assert results["attempts"][0]["status"] == "failed"
    assert results["attempts"][0]["settlement_matches"] is False


def test_stuck_reservations_halt(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest, stuck_reservations=True)
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0


def test_unready_app_blocks_without_outcome(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest, ready=False)
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0
    # The reservation stands without an outcome and blocks any rerun.
    ledger = sv.StagingLedger(
        tmp_path / "ledger-staging.json", initialize=True, run=sv.STAGING_RUN_ID
    )
    assert ledger._read()["dispatches"] == 1
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)


def test_backend_identity_mismatch_blocks(tmp_path):
    manifest = staging_manifest()
    manifest["cases"][0]["deployment"] = "wrong-deployment"
    app = FakeApp(staging_manifest())
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0
    assert not (tmp_path / "ledger-staging.json").exists()


def test_deployed_backend_drift_blocks(tmp_path):
    manifest = staging_manifest()
    drifted = staging_manifest()
    # Both Zen cases share one pool backend; drift the shared deployment.
    drifted["cases"][0]["deployment"] = "drifted-deployment"
    drifted["cases"][1]["deployment"] = "drifted-deployment"
    app = FakeApp(drifted)
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0


def test_wrong_client_key_fails_without_provider_post(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    results = sv.execute_validation(
        manifest,
        stage_dir=tmp_path,
        base_url="http://staging.test",
        caller_key="wrong-key",
        admin_key="admin-key",
        transport_factory=lambda: app,
    )
    assert results["attempts"][0]["status"] == "failed"
    assert len(app.calls) == 0


def test_production_requires_flag_and_staging_pass(tmp_path):
    manifest = production_manifest()
    app = FakeApp(manifest)
    with pytest.raises(ValueError, match="explicit approval"):
        run_validation(tmp_path, manifest, app, production=False)
    assert len(app.calls) == 0
    with pytest.raises(ValueError, match="passing staging results"):
        run_validation(tmp_path, manifest, app, production=True)
    assert len(app.calls) == 0


def test_production_stays_closed_without_independent_evidence(tmp_path):
    staging_app = FakeApp(staging_manifest())
    run_validation(tmp_path, staging_manifest(), staging_app)
    prod_app = FakeApp(production_manifest())
    with pytest.raises(ValueError, match="passing staging results"):
        run_validation(tmp_path, production_manifest(), prod_app, production=True)
    assert len(prod_app.calls) == 0


async def test_production_case_machinery_covered_directly():
    manifest = production_manifest()
    app = FakeApp(manifest)
    transport = app

    async def _run(case):
        return await sv.run_validation_case(
            case=case,
            manifest=manifest,
            base_url="http://staging.test",
            caller_key="client-key",
            admin_key="admin-key",
            transport=transport,
        )

    for case in manifest["cases"]:
        result = await _run(case)
        assert result["status"] == "passed"
        assert result["settlement_matches"] is True
    assert len(app.calls) == 2


def test_reserved_without_outcome_blocks(tmp_path):
    manifest = staging_manifest()
    ledger = sv.StagingLedger(
        tmp_path / "ledger-staging.json", initialize=True, run=sv.STAGING_RUN_ID
    )
    ledger.reserve("staging-zen-nonstream")
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, FakeApp(manifest))


def test_corrupt_state_blocks(tmp_path):
    manifest = staging_manifest()
    (tmp_path / "ledger-staging.json").write_text("corrupt")
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, FakeApp(manifest))
    (tmp_path / "ledger-staging.json").unlink(missing_ok=True)
    (tmp_path / "ledger-staging.json.identity").write_text("{}")
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, FakeApp(manifest))


def test_missing_initialized_state_blocks(tmp_path):
    manifest = staging_manifest()
    (tmp_path / "ledger-staging.json.identity").write_text(
        '{"run": "staging-zen-openrouter-2026-10-11"}'
    )
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, FakeApp(manifest))


def test_outcome_without_result_blocks_resume(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    real_write = sv.write_atomic
    writes = {"count": 0}

    def flaky_write(path, data):
        writes["count"] += 1
        attempts = data.get("attempts", []) if isinstance(data, dict) else []
        if str(path).endswith("results-staging.json") and any(
            item.get("case_id") == "staging-zen-nonstream" for item in attempts
        ):
            # Fail every results write; ledger outcomes still record.
            raise OSError("disk full")
        return real_write(path, data)

    import staging_validation as svmod

    original = svmod.write_atomic
    svmod.write_atomic = flaky_write
    try:
        with pytest.raises(OSError):
            run_validation(tmp_path, manifest, app)
    finally:
        svmod.write_atomic = original
    assert len(app.calls) == 1
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 1


def test_contradictory_ledger_and_results_block(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    run_validation(tmp_path, manifest, app)
    ledger_path = tmp_path / "ledger-staging.json"
    data = json.loads(ledger_path.read_text())
    data["cases"]["staging-zen-nonstream"]["outcome"] = "failed"
    ledger_path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 4


def test_tampered_passed_flag_blocks_production(tmp_path):
    staging_app = FakeApp(staging_manifest())
    run_validation(tmp_path, staging_manifest(), staging_app)
    results_path = tmp_path / "results-staging.json"
    data = json.loads(results_path.read_text())
    data["attempts"][0]["terminated_ok"] = False
    results_path.write_text(json.dumps(data))
    prod_app = FakeApp(production_manifest())
    with pytest.raises(ValueError, match="passing staging results"):
        run_validation(tmp_path, production_manifest(), prod_app, production=True)
    assert len(prod_app.calls) == 0


def test_combined_allowance_overflow_refused():
    expensive = staging_manifest()
    for case in expensive["cases"]:
        case["input_per_million"] = 3.0
        case["output_per_million"] = 3.0
    with pytest.raises(ValueError):
        sv.validate_run_pair(expensive, production_manifest())


def test_combined_committed_manifests_fit_allowance():
    staging = json.loads((PLAN_DIR / "manifest.staging.json").read_text())
    production = json.loads((PLAN_DIR / "manifest.production.json").read_text())
    sv.validate_run_pair(staging, production)
    assert sv.combined_preflight_estimate(staging, production) <= sv.ALLOWANCE_USD


def test_unknown_case_keys_dropped_from_fingerprint():
    manifest = staging_manifest()
    manifest["cases"][0]["injected"] = "synthetic-marker"
    fingerprint = sv.manifest_fingerprint(manifest)
    assert "injected" not in json.dumps(fingerprint)
    assert "synthetic-marker" not in json.dumps(fingerprint)


def test_multi_member_pool_refused(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    original_admin = app._admin

    def two_member_admin():
        payload = original_admin()
        payload["models"]["gpt-5.4-mini-zen"] = {"backends": {"a": 1.0, "b": 1.0}}
        payload["backends"]["a"] = dict(payload["backends"]["backend-gpt-5.4-mini-zen"])
        payload["backends"]["b"] = dict(payload["backends"]["backend-gpt-5.4-mini-zen"])
        return payload

    app._admin = two_member_admin
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0


def test_azure_provider_path_refused(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    original_admin = app._admin

    def azure_admin():
        payload = original_admin()
        payload["backends"]["backend-gpt-5.4-mini-zen"]["provider"] = "azure_foundry"
        return payload

    app._admin = azure_admin
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0


def test_oversized_admin_body_rejected(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    original_admin = app._admin

    def big_admin():
        payload = original_admin()
        payload["padding"] = "x" * (sv.MAX_SETUP_BYTES + 1)
        return payload

    app._admin = big_admin
    with pytest.raises(ValueError, match="setup failed before dispatch"):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0


def test_encoded_response_rejected(tmp_path):
    manifest = staging_manifest()

    class EncodedApp(FakeApp):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            if request.url.path == "/openai/v1/responses":
                return httpx.Response(
                    200,
                    headers={"content-encoding": "gzip"},
                    content=b"compressed-bytes",
                )
            return response

    app = EncodedApp(manifest)
    results = run_validation(tmp_path, manifest, app)
    assert results["attempts"][0]["status"] == "failed"
    assert results["attempts"][0]["error_category"] == "encoded_response"
    assert len(app.calls) == 1


def test_unterminated_terminal_frame_fails(tmp_path):
    manifest = staging_manifest()

    class TruncatedApp(FakeApp):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            if request.url.path == "/openai/v1/responses" and json.loads(
                request.content.decode()
            ).get("stream"):
                terminal = json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "status": "completed",
                            "output": [],
                            "usage": {
                                "input_tokens": 12,
                                "output_tokens": 5,
                                "total_tokens": 17,
                            },
                        },
                    }
                )
                payload = b'data: {"type":"response.created"}\n\n' + b"data: " + terminal.encode()
                return httpx.Response(
                    200, content=payload, headers={"content-type": "text/event-stream"}
                )
            return response

    app = TruncatedApp(manifest)
    results = run_validation(tmp_path, manifest, app)
    zen_stream = [a for a in results["attempts"] if a["case_id"] == "staging-zen-stream"]
    assert zen_stream and zen_stream[0]["status"] == "failed"


def test_incomplete_terminal_fails(tmp_path):
    manifest = staging_manifest()

    class IncompleteApp(FakeApp):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            if request.url.path == "/openai/v1/responses" and json.loads(
                request.content.decode()
            ).get("stream"):
                terminal = json.dumps(
                    {
                        "type": "response.incomplete",
                        "response": {
                            "status": "incomplete",
                            "output": [],
                            "usage": {
                                "input_tokens": 12,
                                "output_tokens": 5,
                                "total_tokens": 17,
                            },
                        },
                    }
                )
                payload = b"data: " + terminal.encode() + b"\n\n"
                return httpx.Response(
                    200, content=payload, headers={"content-type": "text/event-stream"}
                )
            return response

    app = IncompleteApp(manifest)
    results = run_validation(tmp_path, manifest, app)
    zen_stream = [a for a in results["attempts"] if a["case_id"] == "staging-zen-stream"]
    assert zen_stream and zen_stream[0]["status"] == "failed"


def test_contradictory_terminals_fail(tmp_path):
    manifest = staging_manifest()

    class FlipFlopApp(FakeApp):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            if request.url.path == "/openai/v1/responses" and json.loads(
                request.content.decode()
            ).get("stream"):

                def make(status, kind):
                    return (
                        b"data: "
                        + json.dumps(
                            {
                                "type": kind,
                                "response": {
                                    "status": status,
                                    "output": [],
                                    "usage": {
                                        "input_tokens": 12,
                                        "output_tokens": 5,
                                        "total_tokens": 17,
                                    },
                                },
                            }
                        ).encode()
                        + b"\n\n"
                    )

                payload = make("completed", "response.completed") + make(
                    "completed", "response.completed"
                )
                return httpx.Response(
                    200, content=payload, headers={"content-type": "text/event-stream"}
                )
            return response

    app = FlipFlopApp(manifest)
    results = run_validation(tmp_path, manifest, app)
    zen_stream = [a for a in results["attempts"] if a["case_id"] == "staging-zen-stream"]
    assert zen_stream and zen_stream[0]["status"] == "failed"


def test_malformed_sse_frame_fails_stream(tmp_path):
    manifest = staging_manifest()

    class MalformedApp(FakeApp):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            if request.url.path == "/openai/v1/responses" and json.loads(
                request.content.decode()
            ).get("stream"):
                payload = b"data: {broken json\n\ndata: [DONE]\n\n"
                return httpx.Response(
                    200, content=payload, headers={"content-type": "text/event-stream"}
                )
            return response

    app = MalformedApp(manifest)
    results = run_validation(tmp_path, manifest, app)
    zen_stream = [a for a in results["attempts"] if a["case_id"] == "staging-zen-stream"]
    assert zen_stream and zen_stream[0]["status"] == "failed"


def test_multiline_data_frame_accepted(tmp_path):
    manifest = staging_manifest()

    class MultilineApp(FakeApp):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            if request.url.path == "/openai/v1/responses" and json.loads(
                request.content.decode()
            ).get("stream"):
                terminal = json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "ready"}],
                                }
                            ],
                            "usage": {
                                "input_tokens": 12,
                                "output_tokens": 5,
                                "total_tokens": 17,
                            },
                        },
                    }
                )
                head, sep, tail = terminal.partition(', "response":')
                assert sep
                payload = (
                    b"data: " + head.encode() + b"\ndata: " + sep.encode() + tail.encode() + b"\n\n"
                )
                return httpx.Response(
                    200, content=payload, headers={"content-type": "text/event-stream"}
                )
            return response

    app = MultilineApp(manifest)
    results = run_validation(tmp_path, manifest, app)
    zen_stream = [a for a in results["attempts"] if a["case_id"] == "staging-zen-stream"]
    assert zen_stream and zen_stream[0]["status"] == "passed"


def test_zero_debit_with_positive_price_fails(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest, debit_scale=0.0)
    results = run_validation(tmp_path, manifest, app)
    assert results["attempts"][0]["status"] == "failed"
    assert results["attempts"][0]["settlement_matches"] is False


def test_smallest_charges_reconcile(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(
        manifest,
        usage_override={
            "staging-zen-nonstream": {
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
            }
        },
    )
    results = run_validation(tmp_path, manifest, app)
    assert results["attempts"][0]["status"] == "passed"
    assert results["attempts"][0]["settlement_matches"] is True


async def test_timeout_after_entry_reports_dispatched(monkeypatch):
    import asyncio as asyncio_module

    manifest = staging_manifest()
    entered = []

    class HangingApp(FakeApp):
        async def handle_async_request(self, request):
            if request.url.path == "/openai/v1/responses":
                entered.append(1)
                await asyncio_module.sleep(30)
            return await super().handle_async_request(request)

    app = HangingApp(manifest)
    monkeypatch.setattr(sv, "CASE_TIMEOUT_SECONDS", 0.05)
    manifest["case_timeout_seconds"] = 0.05
    result = await sv.run_validation_case(
        case=manifest["cases"][0],
        manifest=manifest,
        base_url="http://staging.test",
        caller_key="client-key",
        admin_key="admin-key",
        transport=app,
    )
    assert entered == [1]
    assert result["dispatched"] is True
    assert result["status"] == "failed"


def test_legacy_crash_state_blocks_resume(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    ledger = sv.StagingLedger(
        tmp_path / "ledger-staging.json", initialize=True, run=sv.STAGING_RUN_ID
    )
    ledger.reserve("staging-zen-nonstream")
    results = {
        "run": sv.STAGING_RUN_ID,
        "manifest": sv.manifest_fingerprint(manifest),
        "attempts": [
            {
                "case_id": "staging-zen-nonstream",
                "pool": "gpt-5.4-mini-zen",
                "stream": False,
                "status": "passed",
                "http_status": 200,
                "provider": "opencode_zen",
                "deployment": "gpt-5.4-mini",
                "dispatched": True,
                "input_tokens": 12,
                "output_tokens": 5,
                "usage_coherent": True,
                "terminated_ok": True,
                "settlement_matches": True,
                "reservations_cleared": True,
                "synthetic_debit_usd": 0.0000315,
                "retry_attempts": 2,
                "retry_max_delay_seconds": 30,
                "independent_upstream_observed": False,
                "error_category": None,
                "elapsed_seconds": 0.5,
            }
        ],
    }
    (tmp_path / "results-staging.json").write_text(json.dumps(results))
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 0


def test_halted_ledger_with_passing_results_blocks(tmp_path):
    manifest = staging_manifest()
    app = FakeApp(manifest)
    run_validation(tmp_path, manifest, app)
    ledger_path = tmp_path / "ledger-staging.json"
    data = json.loads(ledger_path.read_text())
    data["cases"]["staging-zen-nonstream"]["outcome"] = "failed"
    data["halted"] = True
    ledger_path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run_validation(tmp_path, manifest, app)
    assert len(app.calls) == 4
