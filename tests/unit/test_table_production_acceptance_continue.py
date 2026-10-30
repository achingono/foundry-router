"""No-network continuation tests with byte-preserved frozen helper dependencies."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/quality"))
SPEC = importlib.util.spec_from_file_location(
    "table_production_acceptance_continue",
    ROOT / "scripts/quality/table_production_acceptance_continue.py",
)
assert SPEC and SPEC.loader
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "readonly_recovery_fixtures",
    Path(__file__).with_name("test_table_production_acceptance_recovery.py"),
)
assert FIXTURE_SPEC and FIXTURE_SPEC.loader
recovery_tests = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(recovery_tests)


def rewrite(path: Path, value: dict[str, Any]) -> None:
    # Synthetic fixtures only. Real continuation never overwrites prior artifacts.
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture
def capsule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:  # noqa: PLR0915
    original_dir, recovery_dir, test = recovery_tests.program.__wrapped__(tmp_path, monkeypatch)
    r = recovery_tests.r
    monkeypatch.setattr(c, "r", r)
    # Preserve the fields that the old API rejected, then consistently rebind the synthetic prefix.
    test.deployment["properties"]["template"]["scale"].update(
        cooldownPeriod=300, pollingInterval=30
    )
    test.deployment["properties"]["configuration"]["ingress"]["targetPortHttpScheme"] = "http"
    original = r.read(original_dir / "prepared.json")
    old = test.show()
    old["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = []
    original["test_projection"] = c.h.projection(old)
    proposal = c.h.template_proposal(old, original["image"])
    original["template_proposal_sha256"] = c.h.digest(proposal)
    rewrite(original_dir / "prepared.json", original)
    packet_sha = c.h.file_hash(original_dir / "prepared.json")
    monkeypatch.setattr(r, "ORIGINAL_PACKET_SHA", packet_sha)
    prior_approval = r.read(original_dir / "approval.json")
    prior_approval["packet_sha256"] = packet_sha
    rewrite(original_dir / "approval.json", prior_approval)
    rewrite(original_dir / "consumed.json", {"packet_sha256": packet_sha})
    ledger = r.read(original_dir / "program-ledger.json")
    ledger.update(packet_sha256=packet_sha, approval_sha256=c.h.digest(prior_approval))
    rewrite(original_dir / "program-ledger.json", ledger)
    rewrite(original_dir / "update-proposal.json", proposal)
    binding = r.read(original_dir / "update-proposal-binding.json")
    binding.update(
        body_sha256=c.h.digest(proposal),
        file_sha256=c.h.file_hash(original_dir / "update-proposal.json"),
    )
    rewrite(original_dir / "update-proposal-binding.json", binding)
    test.live = False
    recovery_tests.prepared((original_dir, recovery_dir, test))
    test.fault = (
        "patch_uncertain"  # Fixture rejects before any write, modeling the confirmed schema400.
    )
    with pytest.raises(TimeoutError):
        r.apply(
            argparse.Namespace(artifact_dir=recovery_dir, approval=recovery_dir / "approval.json")
        )
    r.h.create(
        recovery_dir / "apply-summary.log",
        {
            "status": "recovery_stopped_unverified",
            "reason": "Azure command unsuccessful; raw output withheld",
        },
    )
    monkeypatch.setattr(c, "RECOVERY_PREP_SHA", c.h.file_hash(recovery_dir / "prepared.json"))
    test.fault = ""
    test.draining = 0
    validation_dir, continuation_dir = tmp_path / "validation", tmp_path / "continuation"
    validation_dir.mkdir(mode=0o700)
    continuation_dir.mkdir(mode=0o700)
    app = test.show()
    envelope: dict[str, Any] = {
        "$schema": "synthetic-validation",
        "contentVersion": "1.0.0.0",
        "resources": [
            {
                "type": "Microsoft.App/containerApps",
                "apiVersion": c.API_VERSION,
                "name": app["name"],
                "identity": app.get("identity"),
                "location": app.get("location"),
                "properties": {
                    "configuration": copy.deepcopy(app["properties"]["configuration"]),
                    "template": copy.deepcopy(proposal["properties"]["template"]),
                },
            }
        ],
    }
    ingress = envelope["resources"][0]["properties"]["configuration"]["ingress"]
    ingress.pop("fqdn")
    ingress.pop("targetPortHttpScheme")
    r.h.create(validation_dir / "template.json", envelope)
    monkeypatch.setattr(c, "VALIDATION_SHA", c.h.file_hash(validation_dir / "template.json"))
    changes = [
        {"resource_id": app["id"], "change_type": "Modify"},
        {"resource_id": "/synthetic/other", "change_type": "Ignore"},
    ]
    r.h.create(
        validation_dir / "validation-result.json",
        {
            "id": "synthetic-validation",
            "id_kind": "response_id",
            "provisioning_state": "Succeeded",
            "response_keys": ["id", "properties"],
        },
    )
    r.h.create(
        validation_dir / "what-if-result.json",
        {
            "id": "synthetic-request-target",
            "id_kind": "request_target",
            "status": "Succeeded",
            "response_keys": ["status", "changes"],
            "changes": changes,
        },
    )
    r.h.create(
        validation_dir / "evidence.json",
        {
            "schema": "g1-api-validation-v1",
            "api_version": c.API_VERSION,
            "supported_api_versions": [c.API_VERSION],
            "validation_status": "Succeeded",
            "what_if_status": "Succeeded",
            "template_sha256": c.VALIDATION_SHA,
            "proposal_sha256": c.h.file_hash(original_dir / "update-proposal.json"),
            "validation_id": "synthetic-validation",
            "validation_id_kind": "response_id",
            "validation_result_sha256": c.h.file_hash(validation_dir / "validation-result.json"),
            "what_if_id": "synthetic-request-target",
            "what_if_id_kind": "request_target",
            "what_if_result_sha256": c.h.file_hash(validation_dir / "what-if-result.json"),
            "changes": changes,
        },
    )
    rejection_path = tmp_path / "rejection.json"
    r.h.create(
        rejection_path,
        {
            "schema": "g1-api-rejection-v1",
            "api_version": c.REJECTED_API,
            "http_status": 400,
            "status": "Failed",
            "error_code": None,
            "problem_type": c.PROBLEM_TYPE,
            "problem_title": c.PROBLEM_TITLE,
            "validation_errors": [c.SCALE_ERROR],
            "unknown_fields": ["cooldownPeriod", "pollingInterval"],
            "no_commit_confirmed": True,
            "correlation_id": "synthetic-correlated-event",
            "event_id": "synthetic-activity-event",
            "current_template_sha256": c.h.digest(app["properties"]["template"]),
            "expected_template_sha256": c.h.digest(app["properties"]["template"]),
            "operation": "Microsoft.App/containerApps/write",
            "resource_id": app["id"],
            "recovery_prepared_sha256": c.h.file_hash(recovery_dir / "prepared.json"),
            "update_consumed_sha256": c.h.file_hash(original_dir / "update-consumed.json"),
            "proposal_sha256": c.h.file_hash(original_dir / "update-proposal.json"),
        },
    )
    mutations_before = test.mutations.copy()
    original_command = recovery_tests.FakeAzure.app_command
    enumeration_calls: list[list[str]] = []

    def metadata(self: Any, arguments: list[str]) -> Any:
        if arguments[:2] == ["revision", "list"]:
            enumeration_calls.append(arguments.copy())
            current = self.deployment["properties"]["latestReadyRevisionName"]
            names = list(dict.fromkeys([current, "old", "historical-1", "historical-2"]))
            revisions = [
                {"name": name, "properties": {"active": self.active and name == current}}
                for name in names
            ]
            return (
                revisions
                if "--all" in arguments
                else [rev for rev in revisions if rev["properties"]["active"]]
            )
        if arguments[:2] == ["replica", "list"]:
            name = arguments[arguments.index("--revision") + 1]
            if (self.draining and name == "old") or name == getattr(
                self, "hidden_worker_revision", None
            ):
                return [{"name": "hidden-inactive-worker", "properties": {"containers": []}}]
            if (
                self.active
                and self.live
                and name == self.deployment["properties"]["latestReadyRevisionName"]
            ):
                return [
                    {
                        "name": "replica",
                        "properties": {
                            "containers": [
                                {
                                    "ready": True,
                                    "started": True,
                                    "containerId": self.container,
                                    "restartCount": self.restart_count,
                                }
                            ]
                        },
                    }
                ]
            return []
        return original_command(self, arguments)

    monkeypatch.setattr(recovery_tests.FakeAzure, "app_command", metadata)

    # Base is the already-loaded dynamic script class; real wrapper behavior remains under test.
    class MockAllRevisions(c.AllRevisionsAzure):  # type: ignore[name-defined,misc]
        def __init__(self, subscription: str, resource_group: str, app: str, budget: Any):
            super().__init__(subscription, resource_group, app, budget)
            self.state = recovery_tests.FakeAzure.instances[app]
            self.env = self.state.env

        def run(self, arguments: list[str]) -> Any:
            if arguments[0] == "containerapp":
                assert arguments[-4:] == ["-g", self.resource_group, "-n", self.app]
                command = arguments[1:-4]
                return self.state.show() if command == ["show"] else self.state.app_command(command)
            return self.state.run(arguments)

        def ingress(self, app_id: str, policy: list[dict[str, Any]]) -> None:
            self.state.ingress(app_id, policy)

        def snapshot(self) -> dict[str, Any]:
            return dict(self.state.snapshot())

    monkeypatch.setattr(c, "AllRevisionsAzure", MockAllRevisions)
    original_public = c.h.get_public_async

    async def phase_public(origin: str, path: str, key: str | None = None) -> tuple[int, bytes]:
        if not test.active:
            return 404, b"inactive route"
        status, body = await original_public(origin, path, key)
        return int(status), bytes(body)

    monkeypatch.setattr(c.h, "get_public_async", phase_public)
    original_run = recovery_tests.FakeAzure.run

    def versioned(self: Any, arguments: list[str]) -> Any:
        url = arguments[arguments.index("--url") + 1]
        assert url.endswith("?api-version=2025-01-01")
        assert (original_dir / "api-2025-update-consumed.json").exists()
        assert (original_dir / c.GUARD).exists()
        return original_run(self, arguments)

    monkeypatch.setattr(recovery_tests.FakeAzure, "run", versioned)
    return {
        "original": original_dir,
        "recovery": recovery_dir,
        "validation": validation_dir,
        "new": continuation_dir,
        "rejection": rejection_path,
        "test": test,
        "before": mutations_before,
        "original_value": original,
        "enumeration_calls": enumeration_calls,
    }


def arguments(data: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        original_dir=data["original"],
        recovery_dir=data["recovery"],
        validation_dir=data["validation"],
        artifact_dir=data["new"],
        rejection_evidence=data["rejection"],
        executor_ip="192.0.2.25",
    )


def prepared(data: dict[str, Any]) -> Path:
    c.prepare(arguments(data))
    packet = c.r.read(data["new"] / "prepared.json")
    value = {
        "verdict": "approved",
        "packet_sha256": c.h.file_hash(data["new"] / "prepared.json"),
        "independent_reviewer": "synthetic-independent-review",
        "api_version": c.API_VERSION,
        "prior_hashes_sha256": c.h.digest(packet["prior_hashes"]),
        "old_drained_sha256": packet["prior_hashes"]["original"]["old-drained.json"],
        "rejection_evidence_sha256": packet["evidence"]["rejection_sha256"],
        "validation_template_sha256": packet["evidence"]["template_sha256"],
        "continuation_accepted": True,
        "unused_slots_verified": True,
        "stopped_old_writer_verified": True,
        "previous_executors_exited": True,
        "production_writer_paused": True,
        "staged_fenced_completion_accepted": True,
    }
    path = data["new"] / "approval.json"
    c.h.create(path, value)
    return Path(path)


def test_complete_continuation_only2025_preserves_all_failed_history_and_slots(
    capsule: dict[str, Any],
) -> None:
    prior_original = {name: c.h.file_hash(capsule["original"] / name) for name in c.ORIGINAL_FILES}
    prior_recovery = {name: c.h.file_hash(capsule["recovery"] / name) for name in c.RECOVERY_FILES}
    proposal_bytes = (capsule["original"] / "update-proposal.json").read_bytes()
    approval = prepared(capsule)
    assert capsule["test"].mutations == capsule["before"]
    assert c.r.read(capsule["new"] / "prepared.json")["financial_baseline_deferred_until_successor"]
    c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    c.r.immutable(capsule["original"], prior_original)
    c.r.immutable(capsule["recovery"], prior_recovery)
    assert (capsule["original"] / "update-proposal.json").read_bytes() == proposal_bytes
    scale = c.r.read(capsule["original"] / "update-proposal.json")["properties"]["template"][
        "scale"
    ]
    assert scale["cooldownPeriod"] == 300 and scale["pollingInterval"] == 30
    fresh = capsule["test"].mutations[len(capsule["before"]) :]
    assert fresh == ["patch", "allow", "case-0", "case-1", "case-2", "case-3", "deny", "restart"]
    assert not recovery_tests.FakeAzure.instances["production"].mutations
    result = c.r.read(capsule["original"] / "results.json")
    assert (
        result["schema"] == "g1-fence-recovery-result-v1" and not result["original_apply_completed"]
    )
    assert result["api_version"] == "2025-01-01" and len(result["case_hashes"]) == 4
    assert result["recovery_link"] and result["continuation_link"]
    assert len(capsule["enumeration_calls"]) >= 4  # prepare/apply stopped, successor and restart
    assert all(call.count("--all") == 1 for call in capsule["enumeration_calls"])
    with pytest.raises(c.h.RefusalError, match="already consumed"):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))


@pytest.mark.parametrize(
    "fault",
    [
        "patch_uncertain",
        "missing_current_counter",
        "paid_uncertain",
        "between_cases",
        "same_restart_process",
        "restart_balance",
    ],
)
def test_failed_or_ambiguous_continuation_never_retries_or_advances_later_slots(
    capsule: dict[str, Any], fault: str
) -> None:
    approval = prepared(capsule)
    capsule["test"].fault = fault
    with pytest.raises((c.h.RefusalError, TimeoutError, httpx.ReadTimeout)):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert (capsule["original"] / c.GUARD).exists()
    assert not (capsule["original"] / "results.json").exists()
    if fault in {"patch_uncertain", "missing_current_counter"}:
        assert not (capsule["original"] / "case-0-consumed.json").exists()
    if fault in {"paid_uncertain", "between_cases"}:
        assert (capsule["original"] / "case-0-consumed.json").exists()
        assert not (capsule["original"] / "case-1-consumed.json").exists()
    assert c.r.read(capsule["original"] / "program-ledger.json")[
        "phase1_reserved_usd"
    ] == pytest.approx(0.01792)


@pytest.mark.parametrize(
    "where,name",
    [
        ("original", "case-0-consumed.json"),
        ("original", "case-2-observed-http.json"),
        ("original", "restart-consumed.json"),
        ("original", "results.json"),
        ("recovery", "case-0-ownership.json"),
        ("original", "continuation-consumed.json"),
        ("original", "unknown-journal.json"),
    ],
)
def test_started_or_conflicting_prefix_refuses_without_promotion(
    capsule: dict[str, Any], where: str, name: str
) -> None:
    c.h.create(capsule[where] / name, {})
    with pytest.raises(c.h.RefusalError):
        c.prepare(arguments(capsule))
    assert capsule["test"].mutations == capsule["before"]
    assert not (capsule["new"] / "prepared.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("http_status", 500),
        ("no_commit_confirmed", False),
        ("api_version", "2025-01-01"),
        ("unknown_fields", ["unrelated"]),
        ("correlation_id", ""),
        ("resource_id", "/synthetic/wrong"),
        ("proposal_sha256", "drift"),
        ("update_consumed_sha256", "drift"),
    ],
)
def test_uncorrelated_or_ambiguous400_evidence_refuses(
    capsule: dict[str, Any], field: str, value: Any
) -> None:
    proof = c.r.read(capsule["rejection"])
    proof[field] = value
    rewrite(capsule["rejection"], proof)
    with pytest.raises(c.h.RefusalError):
        c.prepare(arguments(capsule))
    assert capsule["test"].mutations == capsule["before"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("api_version", "2024-03-01"),
        ("supported_api_versions", []),
        ("validation_status", "Failed"),
        ("what_if_status", "Failed"),
        ("template_sha256", "wrong"),
        ("changes", [{"resource_id": "/synthetic/other", "change_type": "Modify"}]),
        (
            "changes",
            [
                {"resource_id": "/synthetic/test", "change_type": "Modify"},
                {"resource_id": "/synthetic/new", "change_type": "Create"},
            ],
        ),
    ],
)
def test_wrong_api_validation_or_whatif_scope_refuses(
    capsule: dict[str, Any], field: str, value: Any
) -> None:
    path = capsule["validation"] / "evidence.json"
    data = c.r.read(path)
    data[field] = value
    rewrite(path, data)
    with pytest.raises(c.h.RefusalError):
        c.prepare(arguments(capsule))
    assert not (capsule["new"] / "prepared.json").exists()


@pytest.mark.parametrize("state", ["active", "draining", "image_drift", "seed_drift"])
def test_initial_workers_or_configuration_drift_refuse_without_new_stop(
    capsule: dict[str, Any], state: str
) -> None:
    test = capsule["test"]
    if state == "active":
        test.active, test.live = True, True
    elif state == "draining":
        test.draining = 1
    elif state == "image_drift":
        test.deployment["properties"]["template"]["containers"][0]["image"] = "unreviewed"
    else:
        test.env["FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON"] = '{"one":101,"two":100}'
        next(
            entry
            for entry in test.deployment["properties"]["template"]["containers"][0]["env"]
            if entry["name"] == "FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON"
        )["value"] = test.env["FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON"]
    with pytest.raises(c.h.RefusalError):
        c.prepare(arguments(capsule))
    assert test.mutations == capsule["before"]


def test_bad_successor_finances_stop_before_first_paid_marker(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = prepared(capsule)
    original_run = recovery_tests.FakeAzure.run

    def bad(self: Any, args: list[str]) -> Any:
        result = original_run(self, args)
        self.balances["two"]["estimated_remaining_usd"] += 1
        return result

    monkeypatch.setattr(recovery_tests.FakeAzure, "run", bad)
    with pytest.raises(c.h.RefusalError, match="Persisted account state changed"):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert not (capsule["original"] / "case-0-consumed.json").exists()


@pytest.mark.parametrize(
    "which",
    [
        "api_version",
        "unused_slots_verified",
        "stopped_old_writer_verified",
        "production_writer_paused",
    ],
)
def test_exact_approval_and_locks_cannot_be_bypassed(capsule: dict[str, Any], which: str) -> None:
    approval = prepared(capsule)
    data = c.r.read(approval)
    data[which] = "2024-03-01" if which == "api_version" else False
    rewrite(approval, data)
    with pytest.raises(c.h.RefusalError):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert not (capsule["original"] / c.GUARD).exists()
    assert capsule["test"].mutations == capsule["before"]


def test_available_original_recovery_locks_required(capsule: dict[str, Any]) -> None:
    approval = prepared(capsule)
    with (
        c.r.lock(capsule["recovery"] / "execution.lock", existing=True),
        pytest.raises(BlockingIOError),
    ):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert not (capsule["original"] / c.GUARD).exists()


def test_worker_deadline_does_not_retry_new_patch(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = prepared(capsule)
    monkeypatch.setattr(
        c.r,
        "workers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(c.h.RefusalError("Worker deadline")),
    )
    with pytest.raises(c.h.RefusalError, match="Worker deadline"):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert capsule["test"].mutations.count("patch") == 1
    assert not (capsule["original"] / "case-0-consumed.json").exists()


def test_public_propagation_helper_is_bounded_and_readonly(monkeypatch: pytest.MonkeyPatch) -> None:
    recovery_tests.test_total_public_wait_handles_delay_and_trickle_without_paid_retry(monkeypatch)


def test_main_withholds_native_cli_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "continuation",
            "apply",
            "--artifact-dir",
            "/synthetic",
            "--approval",
            "/synthetic/approval",
        ],
    )
    monkeypatch.setattr(c, "apply", lambda _: (_ for _ in ()).throw(TimeoutError("credential")))
    assert c.main() == 2
    assert "credential" not in capsys.readouterr().out


def test_truthful_problem_details_and_only_two_readonly_omissions_pass(
    capsule: dict[str, Any],
) -> None:
    app_before = capsule["test"].show()
    envelope = c.r.read(capsule["validation"] / "template.json")
    ingress = envelope["resources"][0]["properties"]["configuration"]["ingress"]
    assert "fqdn" not in ingress and "targetPortHttpScheme" not in ingress
    assert "fqdn" in app_before["properties"]["configuration"]["ingress"]
    assert "targetPortHttpScheme" in app_before["properties"]["configuration"]["ingress"]
    c.prepare(arguments(capsule))
    proof = c.r.read(capsule["new"] / "prepared.json")["evidence"]
    assert proof["error_code"] is None
    assert proof["problem_title"] == "One or more validation errors occurred."
    assert proof["validation_errors"] == [c.SCALE_ERROR]
    assert proof["rejection_classification"] == "schema_validation_problem_details"
    assert proof["validation_id_kind"] == "response_id"
    assert proof["what_if_id_kind"] == "request_target"
    assert capsule["test"].show() == app_before


@pytest.mark.parametrize(
    "field,value",
    [
        ("error_code", "InvalidRequestContent"),
        ("problem_title", "invented"),
        ("problem_type", "invented"),
        ("validation_errors", ["unrelated"]),
        ("event_id", ""),
        ("current_template_sha256", "different"),
    ],
)
def test_unobserved_provider_code_or_problem_details_refused(
    capsule: dict[str, Any],
    field: str,
    value: Any,
) -> None:
    proof = c.r.read(capsule["rejection"])
    proof[field] = value
    rewrite(capsule["rejection"], proof)
    with pytest.raises(c.h.RefusalError):
        c.prepare(arguments(capsule))
    assert capsule["test"].mutations == capsule["before"]


@pytest.mark.parametrize("drift", ["remove_allowInsecure", "change_targetPort", "template"])
def test_readonly_exclusions_do_not_allow_other_configuration_drift(
    capsule: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    path = capsule["validation"] / "template.json"
    envelope = c.r.read(path)
    props = envelope["resources"][0]["properties"]
    if drift == "remove_allowInsecure":
        props["configuration"]["ingress"].pop("allowInsecure")
    elif drift == "change_targetPort":
        props["configuration"]["ingress"]["targetPort"] = 9999
    else:
        props["template"]["scale"]["maxReplicas"] = 3
    rewrite(path, envelope)
    # Isolate the comparison predicate; a real changed envelope is independently refused by its pin.
    monkeypatch.setattr(c, "VALIDATION_SHA", c.h.file_hash(path))
    with pytest.raises(c.h.RefusalError, match="Validated envelope differs"):
        c.prepare(arguments(capsule))


@pytest.mark.parametrize(
    "field,value",
    [
        ("validation_id_kind", "request_target"),
        ("what_if_id_kind", "response_id"),
        ("what_if_id_kind", "invented_unique_operation_id"),
        ("validation_result_sha256", "wrong"),
        ("what_if_result_sha256", "wrong"),
    ],
)
def test_actual_reference_kinds_and_capture_hashes_are_required(
    capsule: dict[str, Any],
    field: str,
    value: Any,
) -> None:
    path = capsule["validation"] / "evidence.json"
    proof = c.r.read(path)
    proof[field] = value
    rewrite(path, proof)
    with pytest.raises(c.h.RefusalError):
        c.prepare(arguments(capsule))


def test_inactive404_proof_is_bound_and_rechecked_at_apply(capsule: dict[str, Any]) -> None:
    approval = prepared(capsule)
    proof = c.r.read(capsule["new"] / "prepared.json")["stopped_route_proof"]
    assert proof["http_status"] == 404 and proof["classification"] == "inactive_route_absent"
    assert proof["all_revisions_inactive"] and proof["workers"] == 0 and proof["deny_bound"]
    c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    actual = c.r.read(capsule["new"] / "consumed.json")["stopped_route_proof"]
    assert actual == proof


def test_inactive403_is_also_accepted_without_live_route_claim(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def denied(_origin: str, _path: str, _key: str | None = None) -> tuple[int, bytes]:
        return 403, b""

    monkeypatch.setattr(c.h, "get_public_async", denied)
    c.prepare(arguments(capsule))
    proof = c.r.read(capsule["new"] / "prepared.json")["stopped_route_proof"]
    assert proof["http_status"] == 403 and proof["classification"] == "inactive_route_denied"


def test_stopped200_is_rejected_without_promotion(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def live(_origin: str, _path: str, _key: str | None = None) -> tuple[int, bytes]:
        return 200, b'{"ready":true}'

    monkeypatch.setattr(c.h, "get_public_async", live)
    with pytest.raises(c.h.RefusalError, match="never live"):
        c.prepare(arguments(capsule))
    assert capsule["test"].mutations == capsule["before"]


def test_active_revision_with_zero_workers_cannot_use404_exception(capsule: dict[str, Any]) -> None:
    capsule["test"].active = True
    capsule["test"].live = False
    with pytest.raises(c.h.RefusalError, match="active or unknown revisions"):
        c.prepare(arguments(capsule))
    assert not (capsule["new"] / "prepared.json").exists()


@pytest.mark.parametrize("phase", ["after_promotion", "after_restart"])
def test_live404_never_proves_fence_or_completes_g1(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    approval = prepared(capsule)
    original_public = c.h.get_public_async

    async def observed(origin: str, path: str, key: str | None = None) -> tuple[int, bytes]:
        test = capsule["test"]
        fail = test.ticks == ("30" if phase == "after_promotion" else "40")
        if fail:
            return 404, b""
        status, body = await original_public(origin, path, key)
        return int(status), bytes(body)

    monkeypatch.setattr(c.h, "get_public_async", observed)
    with pytest.raises(c.h.RefusalError, match="Unexpected recovery public status"):
        c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert not (capsule["original"] / "results.json").exists()
    if phase == "after_promotion":
        assert not (capsule["original"] / "case-0-consumed.json").exists()
        assert "allow" not in capsule["test"].mutations[len(capsule["before"]) :]
    else:
        assert (capsule["original"] / "case-3-passed.json").exists()
        assert not (capsule["original"] / "restart-passed.json").exists()


def test_all_flag_wrapper_preserves_arguments_and_target_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    azure = c.AllRevisionsAzure(
        "synthetic-subscription", "synthetic-rg", "synthetic-app", recovery_tests.FastBudget()
    )
    calls: list[list[str]] = []

    def capture(arguments: list[str]) -> list[dict[str, Any]]:
        calls.append(arguments)
        return []

    monkeypatch.setattr(azure, "run", capture)
    original = ["revision", "list"]
    azure.app_command(original)
    azure.app_command(["revision", "list", "--all"])
    azure.app_command(["show"])
    assert original == ["revision", "list"]
    assert all(call.count("--all") == 1 for call in calls[:2])
    assert "--all" not in calls[2]
    assert all(call[-4:] == ["-g", "synthetic-rg", "-n", "synthetic-app"] for call in calls)
    assert azure.subscription == "synthetic-subscription"


def test_three_inactive_zero_worker_revisions_are_in_prepared_inventory(
    capsule: dict[str, Any],
) -> None:
    # The mock CLI's default really is active-only and therefore empty in this phase.
    assert capsule["test"].app_command(["revision", "list"]) == []
    c.prepare(arguments(capsule))
    proof = c.r.read(capsule["new"] / "prepared.json")["stopped_route_proof"]
    assert proof["revision_names"] == ["old", "historical-1", "historical-2"]
    assert proof["workers"] == 0 and proof["all_revisions_inactive"]
    assert all(call.count("--all") == 1 for call in capsule["enumeration_calls"][1:])


@pytest.mark.parametrize("phase", ["prepare", "apply", "after_promotion"])
def test_hidden_inactive_worker_cannot_bypass_all_revision_guards(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    if phase != "prepare":
        approval = prepared(capsule)
    if phase == "after_promotion":
        original_run = recovery_tests.FakeAzure.run

        def with_hidden_worker(self: Any, arguments: list[str]) -> Any:
            result = original_run(self, arguments)
            self.hidden_worker_revision = "historical-2"
            return result

        monkeypatch.setattr(recovery_tests.FakeAzure, "run", with_hidden_worker)
    else:
        capsule["test"].hidden_worker_revision = "historical-2"
    # An ordinary CLI revision list conceals the problematic inactive worker.
    assert capsule["test"].app_command(["revision", "list"]) == []
    with pytest.raises(c.h.RefusalError, match="workers"):
        if phase == "prepare":
            c.prepare(arguments(capsule))
        else:
            c.apply(argparse.Namespace(artifact_dir=capsule["new"], approval=approval))
    assert not (capsule["original"] / "case-0-consumed.json").exists()
    if phase in {"prepare", "apply"}:
        assert not (capsule["original"] / c.GUARD).exists()
        assert capsule["test"].mutations == capsule["before"]
    else:
        assert capsule["test"].mutations[len(capsule["before"]) :] == ["patch"]
