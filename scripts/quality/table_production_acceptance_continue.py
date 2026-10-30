"""Single-use API2025 continuation of the confirmed rejected, stopped G1 prefix."""

from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import logging
import subprocess
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import table_production_acceptance as h
import table_production_acceptance_recovery as r

from foundry_router.credit import estimate_response_usage_cost

Json = dict[str, Any]
ROOT = Path(__file__).resolve().parents[2]
API_VERSION = "2025-01-01"
REJECTED_API = "2024-03-01"
REJECTED_STATUS = 400
INACTIVE_ROUTE_STATUS = 404
PROBLEM_TYPE = "https://tools.ietf.org/html/rfc9110#section-15.5.1"
PROBLEM_TITLE = "One or more validation errors occurred."
SCALE_ERROR = (
    "Unknown properties cooldownPeriod, pollingInterval in ContainerAppScale are not supported"
)
RECOVERY_SHA = "e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45"
RECOVERY_TEST_SHA = "762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887"
RECOVERY_PREP_SHA = "3704f9491efee425b83f5c28679bdc40afbfdcb23a42dd75a035795849495d19"
VALIDATION_SHA = "ffc9c3e051b9b0c8fe407773899c06ad3d3fdd719defa2d7f1c8f09a7c58948a"
GUARD = "continuation-consumed.json"
CONTINUATION_LOCK = "continuation.lock"
ORIGINAL_FILES = r.BASE_FILES | {
    r.GUARD,
    r.PROGRAM_LOCK,
    "old-drained.json",
    "stop-consumed.json",
    "old-writers-absent.json",
    "update-consumed.json",
}
RECOVERY_FILES = {
    "prepared.json",
    "approval.json",
    "consumed.json",
    "execution.lock",
    "apply-summary.log",
    "cold-warm-allow-consumed.json",
    "cold-old-deny-consumed.json",
    "cold-old-baseline.json",
}


def files(directory: Path, expected: set[str], *, optional: set[str] | None = None) -> Json:
    r.directory(directory)
    entries = {path.name for path in directory.iterdir()}
    h.require(
        expected <= entries <= expected | (optional or set()),
        "Unexpected or started continuation history",
    )
    hashes = {}
    for name in expected:
        r.private_file(directory / name)
        hashes[name] = h.file_hash(directory / name)
    return hashes


def history(original_dir: Path, recovery_dir: Path) -> tuple[Json, Json, Json]:
    h.require(not (original_dir / GUARD).exists(), "API continuation already consumed")
    original_hashes = files(original_dir, ORIGINAL_FILES, optional={CONTINUATION_LOCK})
    recovery_hashes = files(recovery_dir, RECOVERY_FILES)
    h.require(
        original_hashes["prepared.json"] == r.ORIGINAL_PACKET_SHA
        and recovery_hashes["prepared.json"] == RECOVERY_PREP_SHA,
        "Exact e/a failed prefix required",
    )
    original = r.read(original_dir / "prepared.json")
    recovery = r.read(recovery_dir / "prepared.json")
    h.validate_packet_budget(original)
    h.approved(original_dir / "prepared.json", original_dir / "approval.json")
    h.require(
        Path(recovery["original_dir"]) == original_dir, "Recovery original-directory mismatch"
    )
    r.approval(recovery_dir / "approval.json", recovery_dir / "prepared.json", recovery)
    for name, expected in recovery["original_hashes"].items():
        h.require(original_hashes[name] == expected, "Immutable original history drift")
    h.require(
        r.read(original_dir / "consumed.json")["packet_sha256"] == original_hashes["prepared.json"],
        "Original consumption mismatch",
    )
    ledger = r.read(original_dir / "program-ledger.json")
    h.require(
        Path(original["program_ledger"]) == original_dir / "program-ledger.json"
        and ledger["limit_usd"] == 1
        and ledger["attempt_limit"] == h.PROGRAM_ATTEMPTS
        and ledger["packet_sha256"] == original_hashes["prepared.json"]
        and ledger["phase1_slots"] == original["cases"]
        and ledger["phase1_reserved_usd"] == original["phase_reserved_usd"]
        and ledger["approval_sha256"] == h.digest(r.read(original_dir / "approval.json")),
        "Original budget or slot identities changed",
    )
    h.require(
        recovery["original_slots"] == original["cases"], "Recovery original slot binding drift"
    )
    failed_e = r.read(original_dir / "apply-summary.log")
    failed_a = r.read(recovery_dir / "apply-summary.log")
    h.require(
        failed_e.get("status") == failed_a.get("status") == "stopped_unverified"
        or (
            failed_e.get("status") == "stopped_unverified"
            and failed_a.get("status") == "recovery_stopped_unverified"
        ),
        "Failed execution summaries required",
    )
    h.require(
        failed_e.get("reason") == "Fence denial unproved"
        and failed_a.get("reason") == "Azure command unsuccessful; raw output withheld",
        "Exact failed e/a stages required",
    )
    link = r.read(original_dir / r.GUARD)["recovery_link"]
    h.require(
        link["packet_sha256"] == recovery_hashes["prepared.json"]
        and Path(link["recovery_dir"]) == recovery_dir
        and link["recovery_id"] == recovery["recovery_id"]
        and link["approval_sha256"] == h.digest(r.read(recovery_dir / "approval.json")),
        "Recovery ownership link mismatch",
    )
    for name in (
        r.GUARD,
        "old-drained.json",
        "stop-consumed.json",
        "old-writers-absent.json",
        "update-consumed.json",
    ):
        h.require(
            r.read(original_dir / name)["recovery_link"] == link,
            "Stopped-stage recovery link drift",
        )
    for name in (
        "consumed.json",
        "cold-warm-allow-consumed.json",
        "cold-old-deny-consumed.json",
        "cold-old-baseline.json",
    ):
        h.require(
            r.read(recovery_dir / name)["recovery_link"] == link, "Cold-stage recovery link drift"
        )
    drained = r.read(original_dir / "old-drained.json")
    cold = r.read(recovery_dir / "cold-old-baseline.json")
    h.require(
        cold["current_image_restart_acceptance"] is False, "Old warming is not G1 persistence"
    )
    h.require(
        h.process_identity(cold["snapshot"]) == h.process_identity(drained)
        and r.read(original_dir / "stop-consumed.json")["revision"] == drained["revision"],
        "Stopped original worker mismatch",
    )
    h.require(
        r.read(original_dir / "old-writers-absent.json")["verified"] is True,
        "Old-writer absence evidence required",
    )
    h.unchanged(h.accounts(drained["admin"], legacy=True), original["original_accounts"])
    h.unchanged(h.accounts(cold["snapshot"]["admin"], legacy=True), original["original_accounts"])
    h.require(
        cold["snapshot"]["request_counters"] == drained["request_counters"],
        "Old-drain request drift",
    )
    proposal = r.read(original_dir / "update-proposal.json")
    binding = r.read(original_dir / "update-proposal-binding.json")
    h.require(
        binding["file_sha256"] == original_hashes["update-proposal.json"]
        and binding["body_sha256"] == h.digest(proposal) == original["template_proposal_sha256"]
        and r.read(original_dir / "update-consumed.json")["proposal_sha256"]
        == binding["file_sha256"],
        "Original rejected proposal drift",
    )
    return original, recovery, {"original": original_hashes, "recovery": recovery_hashes}


def release(original: Json, recovery: Json) -> Json:
    h.require(
        h.file_hash(Path(r.__file__)) == RECOVERY_SHA
        and h.file_hash(ROOT / "tests/unit/test_table_production_acceptance_recovery.py")
        == RECOVERY_TEST_SHA,
        "Frozen recovery dependency drift",
    )
    binding = r.release_binding(original)
    h.require(binding == recovery["binding"], "Frozen runtime/image/recovery binding drift")
    return {
        "dependencies": binding,
        "runner_sha256": h.file_hash(Path(__file__)),
        "tests_sha256": h.file_hash(
            ROOT / "tests/unit/test_table_production_acceptance_continue.py"
        ),
    }


def inactive_revisions(azure: r.Azure) -> list[str]:
    revisions = azure.app_command(["revision", "list"])
    h.require(
        all(revision["properties"].get("active") is False for revision in revisions),
        "Stopped prefix has active or unknown revisions",
    )
    for revision in revisions:
        h.require(
            not azure.app_command(["replica", "list", "--revision", revision["name"]]),
            "Stopped prefix has workers; no warming or second stop authorized",
        )
    return [revision["name"] for revision in revisions]


def stopped(budget: r.Budget, original: Json) -> tuple[r.Azure, Json, dict[str, str], Json, Json]:
    azure, app, values, pins = r.discovery(budget, original)
    names = budget.call(inactive_revisions, azure, limit=r.WORKER_SECONDS)
    h.require(
        app["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] == h.DENY,
        "Stopped prefix lacks bound DENY policy",
    )
    status, _body = budget.call(
        h.get_public, original["origin"], "/health/ready", limit=r.PUBLIC_SECONDS
    )
    h.require(
        status in {h.HTTP_DENIED, INACTIVE_ROUTE_STATUS},
        "Stopped route must be denied or absent, never live",
    )
    proof = {
        "http_status": status,
        "classification": "inactive_route_absent"
        if status == INACTIVE_ROUTE_STATUS
        else "inactive_route_denied",
        "all_revisions_inactive": True,
        "workers": 0,
        "deny_bound": True,
        "revision_names": names,
    }
    return azure, app, values, pins, proof


def evidence(  # noqa: PLR0913, PLR0917 -- two capsules, validation and live resource boundary
    rejection_path: Path,
    validation_dir: Path,
    original_dir: Path,
    recovery_dir: Path,
    original: Json,
    app: Json,
) -> Json:
    rejection = r.read(rejection_path)
    h.require(
        rejection["schema"] == "g1-api-rejection-v1"
        and rejection["api_version"] == REJECTED_API
        and rejection["http_status"] == REJECTED_STATUS
        and rejection["status"] == "Failed"
        and rejection["error_code"] is None
        and rejection["problem_type"] == PROBLEM_TYPE
        and rejection["problem_title"] == PROBLEM_TITLE
        and rejection["validation_errors"] == [SCALE_ERROR]
        and set(rejection["unknown_fields"]) == {"cooldownPeriod", "pollingInterval"}
        and rejection["no_commit_confirmed"] is True
        and bool(rejection["correlation_id"])
        and bool(rejection["event_id"])
        and rejection["operation"].casefold() == "microsoft.app/containerapps/write"
        and rejection["resource_id"].casefold() == app["id"].casefold(),
        "Correlated schema400/no-commit evidence required",
    )
    h.require(
        rejection["recovery_prepared_sha256"] == h.file_hash(recovery_dir / "prepared.json")
        and rejection["update_consumed_sha256"]
        == h.file_hash(original_dir / "update-consumed.json")
        and rejection["proposal_sha256"] == h.file_hash(original_dir / "update-proposal.json"),
        "Rejected operation provenance mismatch",
    )
    h.require(
        rejection["current_template_sha256"]
        == rejection["expected_template_sha256"]
        == h.digest(app["properties"]["template"]),
        "Rejected write changed or mismatched old template",
    )
    template_path = validation_dir / "template.json"
    r.private_file(template_path)
    h.require(h.file_hash(template_path) == VALIDATION_SHA, "Exact validated ARM envelope required")
    template = r.read(template_path)
    h.require(
        set(template) == {"$schema", "contentVersion", "resources"}
        and len(template["resources"]) == 1,
        "Single literal validation resource required",
    )
    resource = template["resources"][0]
    h.require(
        resource["type"].casefold() == "microsoft.app/containerapps"
        and resource["apiVersion"] == API_VERSION
        and resource["name"] == app["name"]
        and resource["identity"] == app.get("identity")
        and resource["location"] == app.get("location"),
        "Validation resource or API mismatch",
    )
    properties = resource["properties"]
    allowed = {
        "configuration",
        "template",
        "environmentId",
        "managedEnvironmentId",
        "workloadProfileName",
    }
    h.require(
        set(properties) <= allowed and {"configuration", "template"} <= set(properties),
        "Validation envelope scope drift",
    )
    proposal = r.read(original_dir / "update-proposal.json")
    for key, value in properties.items():
        expected = (
            proposal["properties"]["template"] if key == "template" else app["properties"].get(key)
        )
        if key == "configuration":
            expected = copy.deepcopy(expected)
            for readonly in ("fqdn", "targetPortHttpScheme"):
                expected["ingress"].pop(readonly, None)
        h.require(
            value == expected,
            "Validated envelope differs from bound configuration/proposal",
        )
    h.verify_template_proposal(app, proposal, original["image"])
    validation_path = validation_dir / "evidence.json"
    proof = r.read(validation_path)
    h.require(
        proof["schema"] == "g1-api-validation-v1"
        and proof["api_version"] == API_VERSION
        and API_VERSION in proof["supported_api_versions"]
        and proof["validation_status"] == proof["what_if_status"] == "Succeeded"
        and proof["template_sha256"] == VALIDATION_SHA
        and proof["proposal_sha256"] == h.file_hash(original_dir / "update-proposal.json")
        and bool(proof["validation_id"])
        and bool(proof["what_if_id"])
        and proof["validation_id_kind"] == "response_id"
        and proof["what_if_id_kind"] == "request_target",
        "Successful supported API validation/what-if evidence required",
    )
    validation_result_path = validation_dir / "validation-result.json"
    what_if_result_path = validation_dir / "what-if-result.json"
    validation_result = r.read(validation_result_path)
    what_if_result = r.read(what_if_result_path)
    h.require(
        proof["validation_result_sha256"] == h.file_hash(validation_result_path)
        and proof["what_if_result_sha256"] == h.file_hash(what_if_result_path),
        "Read-only validation response capture hash mismatch",
    )
    h.require(
        validation_result["id"] == proof["validation_id"]
        and validation_result["id_kind"] == proof["validation_id_kind"]
        and validation_result["provisioning_state"] == proof["validation_status"]
        and "id" in validation_result["response_keys"]
        and what_if_result["id"] == proof["what_if_id"]
        and what_if_result["id_kind"] == proof["what_if_id_kind"]
        and what_if_result["status"] == proof["what_if_status"]
        and "id" not in what_if_result["response_keys"]
        and what_if_result["changes"] == proof["changes"],
        "Validation reference kind, outcome or response provenance mismatch",
    )
    changes = proof["changes"]
    modified = [change for change in changes if change["change_type"] == "Modify"]
    h.require(
        len(modified) == 1
        and modified[0]["resource_id"].casefold() == app["id"].casefold()
        and all(change["change_type"] in {"Modify", "Ignore"} for change in changes),
        "What-if must modify only the bound app",
    )
    return {
        "rejection_path": str(rejection_path),
        "rejection_sha256": h.file_hash(rejection_path),
        "validation_dir": str(validation_dir),
        "template_sha256": VALIDATION_SHA,
        "validation_evidence_sha256": h.file_hash(validation_path),
        "correlation_id": rejection["correlation_id"],
        "event_id": rejection["event_id"],
        "problem_type": rejection["problem_type"],
        "problem_title": rejection["problem_title"],
        "validation_errors": rejection["validation_errors"],
        "rejection_classification": "schema_validation_problem_details",
        "http_status": 400,
        "error_code": rejection["error_code"],
        "old_template_sha256": rejection["current_template_sha256"],
        "validation_id": proof["validation_id"],
        "validation_id_kind": proof["validation_id_kind"],
        "what_if_id": proof["what_if_id"],
        "what_if_id_kind": proof["what_if_id_kind"],
        "validation_result_sha256": proof["validation_result_sha256"],
        "what_if_result_sha256": proof["what_if_result_sha256"],
        "api_version": API_VERSION,
    }


def prepare(args: argparse.Namespace) -> None:
    r.directory(args.artifact_dir)
    h.require(not any(args.artifact_dir.iterdir()), "Fresh API-continuation directory required")
    budget = r.Budget()
    with ExitStack() as locks:
        locks.enter_context(r.lock(args.original_dir / "execution.lock", existing=True))
        locks.enter_context(r.lock(args.original_dir / r.PROGRAM_LOCK, existing=True))
        locks.enter_context(r.lock(args.recovery_dir / "execution.lock", existing=True))
        original, recovery, hashes = history(args.original_dir, args.recovery_dir)
        binding = release(original, recovery)
        _azure, app, _values, _pins, stopped_proof = stopped(budget, original)
        proof = evidence(
            args.rejection_evidence,
            args.validation_dir,
            args.original_dir,
            args.recovery_dir,
            original,
            app,
        )
        h.create(
            args.artifact_dir / "prepared.json",
            {
                "schema": "g1-api-continuation-v1",
                "continuation_id": uuid.uuid4().hex,
                "original_dir": str(args.original_dir),
                "recovery_dir": str(args.recovery_dir),
                "prior_hashes": hashes,
                "binding": binding,
                "api_version": API_VERSION,
                "evidence": proof,
                "current_projection": r.shape(h.projection(app)),
                "stopped_route_proof": stopped_proof,
                "executor_ip": str(ipaddress.IPv4Address(args.executor_ip)),
                "original_slots": original["cases"],
                "expected_accounts": h.accounts(
                    r.read(args.original_dir / "old-drained.json")["admin"], legacy=True
                ),
                "financial_baseline_deferred_until_successor": True,
            },
        )
    print(
        json.dumps(
            {
                "status": "api_continuation_prepared_not_approved",
                "packet_sha256": h.file_hash(args.artifact_dir / "prepared.json"),
                "api_version": API_VERSION,
            }
        )
    )


def approval(path: Path, prepared_path: Path, packet: Json) -> Json:
    value = r.read(path)
    keys = {
        "verdict",
        "packet_sha256",
        "independent_reviewer",
        "api_version",
        "prior_hashes_sha256",
        "old_drained_sha256",
        "rejection_evidence_sha256",
        "validation_template_sha256",
        "continuation_accepted",
        "unused_slots_verified",
        "stopped_old_writer_verified",
        "previous_executors_exited",
        "production_writer_paused",
        "staged_fenced_completion_accepted",
    }
    h.require(
        set(value) == keys
        and value["verdict"] == "approved"
        and bool(value["independent_reviewer"])
        and value["packet_sha256"] == h.file_hash(prepared_path)
        and value["api_version"] == packet["api_version"] == API_VERSION
        and value["prior_hashes_sha256"] == h.digest(packet["prior_hashes"])
        and value["old_drained_sha256"] == packet["prior_hashes"]["original"]["old-drained.json"]
        and value["rejection_evidence_sha256"] == packet["evidence"]["rejection_sha256"]
        and value["validation_template_sha256"] == packet["evidence"]["template_sha256"],
        "Fresh exact API2025 continuation approval required",
    )
    for key in (
        "continuation_accepted",
        "unused_slots_verified",
        "stopped_old_writer_verified",
        "previous_executors_exited",
        "production_writer_paused",
        "staged_fenced_completion_accepted",
    ):
        h.require(value[key] is True, "Continuation ownership or staged disposition not approved")
    return value


def apply(args: argparse.Namespace) -> None:  # noqa: PLR0915 -- single-use versioned continuation
    r.directory(args.artifact_dir)
    prepared_path = args.artifact_dir / "prepared.json"
    packet = r.read(prepared_path)
    h.require(packet["schema"] == "g1-api-continuation-v1", "Continuation schema mismatch")
    verdict = approval(args.approval, prepared_path, packet)
    original_dir, recovery_dir = Path(packet["original_dir"]), Path(packet["recovery_dir"])
    budget = r.Budget()
    with ExitStack() as locks:
        for path in (
            original_dir / "execution.lock",
            original_dir / r.PROGRAM_LOCK,
            recovery_dir / "execution.lock",
        ):
            locks.enter_context(r.lock(path, existing=True))
        locks.enter_context(r.lock(original_dir / CONTINUATION_LOCK))
        locks.enter_context(r.lock(args.artifact_dir / "execution.lock"))
        original, recovery, hashes = history(original_dir, recovery_dir)
        h.require(
            hashes == packet["prior_hashes"] and release(original, recovery) == packet["binding"],
            "Continuation history or executable drift",
        )
        h.require(packet["original_slots"] == original["cases"], "Continuation original slot drift")
        azure, app, values, pins, stopped_proof = stopped(budget, original)
        h.require(
            r.shape(h.projection(app)) == packet["current_projection"],
            "Prepared stopped configuration drift",
        )
        proof = evidence(
            Path(packet["evidence"]["rejection_path"]),
            Path(packet["evidence"]["validation_dir"]),
            original_dir,
            recovery_dir,
            original,
            app,
        )
        h.require(proof == packet["evidence"], "API validation/rejection evidence drift")
        expected_accounts = h.accounts(
            r.read(original_dir / "old-drained.json")["admin"], legacy=True
        )
        h.unchanged(expected_accounts, packet["expected_accounts"])
        link = {
            "continuation_id": packet["continuation_id"],
            "packet_sha256": h.file_hash(prepared_path),
            "approval_sha256": h.digest(verdict),
            "continuation_dir": str(args.artifact_dir),
            "prior_hashes_sha256": h.digest(hashes),
            "original_prepared_sha256": hashes["original"]["prepared.json"],
            "original_ledger_sha256": hashes["original"]["program-ledger.json"],
            "recovery_prepared_sha256": hashes["recovery"]["prepared.json"],
            "recovery_failed_sha256": hashes["recovery"]["apply-summary.log"],
            "api_version": API_VERSION,
            "rejection_evidence_sha256": proof["rejection_sha256"],
            "validation_template_sha256": VALIDATION_SHA,
        }

        def record(name: str, data: Json, *, old: bool = False) -> None:
            budget.call(
                h.create,
                (original_dir if old else args.artifact_dir) / name,
                {**data, "continuation_link": link},
                limit=15,
            )

        def immutable() -> None:
            r.immutable(original_dir, hashes["original"])
            r.immutable(recovery_dir, hashes["recovery"])

        record(GUARD, {"original_slot_indices": list(range(h.PHASE_ATTEMPTS))}, old=True)
        record(
            "consumed.json",
            {"confirmed_rejected_api": REJECTED_API, "stopped_route_proof": stopped_proof},
        )
        record(
            "api-2025-update-consumed.json",
            {
                "proposal_sha256": hashes["original"]["update-proposal.json"],
                "confirmed_previous_http_status": 400,
            },
            old=True,
        )
        immutable()
        budget.call(
            azure.run,
            [
                "rest",
                "--method",
                "patch",
                "--url",
                app["id"] + "?api-version=" + API_VERSION,
                "--body",
                "@" + str(original_dir / "update-proposal.json"),
            ],
        )
        r.workers(budget, azure)
        successor = azure.show()
        h.verify_successor(app, successor, original["image"])
        current_values, current_pins = budget.call(h.resolve, azure, successor)
        h.require(
            current_values == {**values, "FOUNDRY_RETRY_ATTEMPTS": "0"} and current_pins == pins,
            "API2025 successor settings drift",
        )
        h.validate_modes(successor, h.settings_from(current_values))
        current = r.snapshot(budget, azure, current_values)
        last = h.accounts(current["admin"])
        h.unchanged(last, expected_accounts)
        h.require(
            current["admin"]["config"]["retry_attempts"] == 0
            and current["server_command_sha256"]
            == r.read(original_dir / "old-drained.json")["server_command_sha256"],
            "Current retry/worker launch mismatch",
        )
        record("successor-baseline.json", current, old=True)
        # Inactive-route404 is never a live fence proof.
        r.public_wait(budget, original["origin"], h.HTTP_DENIED)

        def ingress(stage: str, policy: list[Json], status: int) -> None:
            record(stage + "-consumed.json", {"policy_sha256": h.digest(policy)})
            budget.call(azure.ingress, app["id"], policy)
            r.public_wait(budget, original["origin"], status)

        allow = [
            {
                "name": "g1-executor",
                "ipAddressRange": str(ipaddress.IPv4Address(packet["executor_ip"])) + "/32",
                "action": "Allow",
            }
        ]
        ingress("executor-allow", allow, h.HTTP_OK)
        settings = h.settings_from(current_values)
        for index, case in enumerate(original["cases"]):
            immutable()
            before = r.snapshot(budget, azure, current_values)
            h.require(
                h.process_identity(before) == h.process_identity(current),
                "Continuation paid worker changed",
            )
            h.unchanged(last, h.accounts(before["admin"]))
            record(
                f"case-{index}-consumed.json",
                {"reserve_usd": case["reserve_usd"], "attempts": 1},
                old=True,
            )
            record(f"case-{index}-ownership.json", {"original_slot_index": index})
            observed = budget.call(
                h.dispatch,
                original["origin"],
                h.credential(current_values, "FOUNDRY_CLIENT_API_KEYS_JSON"),
                case,
                original_dir / f"case-{index}-observed.json",
            )
            h.require(
                observed["http_status"] == h.HTTP_OK and observed["completed"] is True,
                "Continuation terminal observation invalid",
            )
            usage = h.response_usage({"status": "completed", "usage": observed["usage"]})
            debit = estimate_response_usage_cost(
                SimpleNamespace(
                    body=json.dumps({"usage": usage}).encode(),
                    headers={"content-type": "application/json"},
                ),
                case["model"],
                settings.pricing,
            )
            h.require(
                debit is not None and debit <= case["reserve_usd"],
                "Continuation original slot charge exceeded",
            )
            assert debit is not None
            after = r.snapshot(budget, azure, current_values)
            h.require(
                h.process_identity(after) == h.process_identity(current),
                "Continuation settlement worker changed",
            )
            next_accounts = h.accounts(after["admin"])
            h.verify_debit(last, next_accounts, case["group"], debit)
            last = next_accounts
            record(f"case-{index}-passed.json", {"debit_usd": debit, "accounts": last}, old=True)
        ingress("final-deny", h.DENY, h.HTTP_DENIED)
        budget.pause(r.DRAIN_SECONDS)
        final = r.snapshot(budget, azure, current_values)
        h.require(
            h.process_identity(final) == h.process_identity(current)
            and final["request_counters"] == after["request_counters"],
            "Continuation final drain process/request drift",
        )
        h.unchanged(h.accounts(final["admin"]), last)
        record("restart-consumed.json", final, old=True)
        budget.call(azure.app_command, ["revision", "restart", "--revision", final["revision"]])
        r.workers(budget, azure, replacement=final)
        restarted = r.snapshot(budget, azure, current_values)
        h.verify_successor(app, azure.show(), original["image"])
        h.require(
            restarted["revision"] == final["revision"]
            and h.process_identity(restarted) != h.process_identity(final),
            "No actual same-revision continuation restart",
        )
        h.unchanged(h.accounts(restarted["admin"]), last)
        r.public_wait(budget, original["origin"], h.HTTP_DENIED)
        record("restart-passed.json", restarted, old=True)
        immutable()
        result = {
            "schema": "g1-fence-recovery-result-v1",
            "g1_four_calls_and_restart": "passed",
            "original_apply_completed": False,
            "ingress": "fenced",
            "min_replicas": 1,
            "original_min": original["original_min"],
            "restoration": "Separate reviewed cleanup required",
            "api_version": API_VERSION,
            "case_hashes": [
                h.file_hash(original_dir / f"case-{index}-passed.json")
                for index in range(h.PHASE_ATTEMPTS)
            ],
            "restart_sha256": h.file_hash(original_dir / "restart-passed.json"),
            "recovery_link": r.read(original_dir / r.GUARD)["recovery_link"],
            "prior_hashes": hashes,
            "binding": packet["binding"],
            "api_evidence": proof,
        }
        record("results.json", result, old=True)
        record(
            "results.json",
            {**result, "original_result_sha256": h.file_hash(original_dir / "results.json")},
        )
    print(json.dumps({"status": "api2025_g1_passed_fenced_restoration_pending"}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="phase", required=True)
    prep = subs.add_parser("prepare")
    for name in (
        "original-dir",
        "recovery-dir",
        "validation-dir",
        "artifact-dir",
        "rejection-evidence",
    ):
        prep.add_argument("--" + name, type=Path, required=True)
    prep.add_argument("--executor-ip", required=True)
    run = subs.add_parser("apply")
    run.add_argument("--artifact-dir", type=Path, required=True)
    run.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args()
    prior = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        (prepare if args.phase == "prepare" else apply)(args)
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        httpx.HTTPError,
        subprocess.SubprocessError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "api_continuation_stopped_unverified",
                    "exception_type": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, h.RefusalError)
                    else "Details withheld",
                    "recovery": "Keep fence/history/uncertainty; no retry, refund or rollback",
                }
            )
        )
        return 2
    finally:
        logging.disable(prior)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
