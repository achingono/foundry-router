"""One-case G1 continuation after a reconciled partial finish; never replay prior slots."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import subprocess
import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import table_production_acceptance as h
import table_production_acceptance_continue as c
import table_production_acceptance_finish as f
import table_production_acceptance_recovery as r

from foundry_router.credit import estimate_response_usage_cost

Json = dict[str, Any]
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "g1-ready-finish-resume-v1"
RESUME_GUARD = "ready-finish-resume-consumed.json"
DENY_GUARD = "ready-finish-resume-deny-consumed.json"
RESUME_LOCK = "ready-finish-resume.lock"
TOTAL_SECONDS = 1800
ARTIFACT_SECONDS = 15
DISPATCH_SECONDS = 60
DENY_WRITE_SECONDS = 60
DENY_PUBLIC_SECONDS = 120
DRAIN_SECONDS = 100
POST_DRAIN_SECONDS = 180
RESTART_SECONDS = 180
ACCEPTED_CASE_COUNT = 2
RECONCILED_CASE_INDEX = 2
RESUME_CASE_INDEX = 3


def immutable_manifest(directory: Path, expected: Json) -> None:
    r.directory(directory)
    for name, digest in expected.items():
        path = directory / name
        r.private_file(path)
        h.require(h.file_hash(path) == digest, "Immutable G1 history drift")


def durable_create(budget: r.Budget, path: Path, value: Json) -> None:
    """Bound fsync-backed exclusive records by the active global/phase budget."""
    budget.call(h.create, path, value, limit=ARTIFACT_SECONDS)


def confirm_durable_resume_marker(
    budget: r.Budget, path: Path, finish_link: Json, resume_link: Json
) -> bool:
    """Fsync and verify an ambiguous marker before allowing any cloud mutation."""

    def confirm() -> bool:
        if not path.exists():
            return False
        r.private_file(path)
        value = r.read(path)
        h.require(
            value.get("case_index") == RESUME_CASE_INDEX
            and value.get("finish_link") == finish_link
            and value.get("resume_link") == resume_link,
            "Resume marker content is not owned by this continuation",
        )
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
        with os.fdopen(fd, "r+b") as handle:
            os.fsync(handle.fileno())
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return True

    try:
        return budget.call(confirm, limit=ARTIFACT_SECONDS) is True
    except (OSError, ValueError, KeyError, TypeError, TimeoutError):
        return False


def partial_entries(original: Json, *, resume_consumed: bool = False) -> tuple[set[str], set[str]]:
    original_entries = set(f.ORIGINAL_FILES)
    # The initial apply appended only these receipts before stopping after case 2.
    original_entries.update({f.FINISH_LOCK, f.GUARD, "successor-baseline.json"})
    if resume_consumed:
        original_entries.update({RESUME_LOCK, RESUME_GUARD})
    finish_entries = {
        "prepared.json",
        "approval.json",
        "execution.lock",
        "consumed.json",
        "executor-allow-consumed.json",
        f"case-{RECONCILED_CASE_INDEX}-reconciliation.json",
    }
    for index in range(RESUME_CASE_INDEX):
        original_entries.update(
            {
                f"case-{index}-consumed.json",
                f"case-{index}-observed.json",
                f"case-{index}-observed-http.json",
            }
        )
        finish_entries.add(f"case-{index}-ownership.json")
        if index < ACCEPTED_CASE_COUNT:
            original_entries.add(f"case-{index}-passed.json")
        if original["cases"][index]["stream"]:
            original_entries.add(f"case-{index}-observed-terminal.json")
            finish_entries.add(f"case-{index}-stream-eof.json")
    return original_entries, finish_entries


def prior_history(
    directories: tuple[Path, Path, Path, Path],
    finish_packet: Json,
    *,
    resume_consumed: bool = False,
) -> tuple[Json, Json, Json, Json]:
    """Validate the exact consumed prefix while permitting only its known append-only tail."""
    original_dir, recovery_dir, continuation_dir, finish_dir = directories
    hashes = finish_packet["prior_hashes"]
    h.require(
        set(hashes["original"]) == set(f.ORIGINAL_FILES),
        "Initial finish base-manifest set drift",
    )
    original_entries, finish_entries = partial_entries(
        r.read(original_dir / "prepared.json"), resume_consumed=resume_consumed
    )
    actual_original_entries = {path.name for path in original_dir.iterdir()}
    h.require(
        actual_original_entries == original_entries
        or actual_original_entries == original_entries | {RESUME_LOCK},
        "Original G1 partial history has unknown or started operations",
    )
    h.require(
        {path.name for path in finish_dir.iterdir()} == finish_entries,
        "Finish partial history has unknown or started operations",
    )
    for directory in (original_dir, finish_dir):
        for path in directory.iterdir():
            r.private_file(path)
    immutable_manifest(original_dir, hashes["original"])
    recovery_hashes = c.files(recovery_dir, c.RECOVERY_FILES)
    continuation_hashes = c.files(continuation_dir, f.CONTINUE_FILES)
    h.require(recovery_hashes == hashes["recovery"], "Recovery history binding drift")
    h.require(continuation_hashes == hashes["continuation"], "Continuation history binding drift")
    original = r.read(original_dir / "prepared.json")
    recovery = r.read(recovery_dir / "prepared.json")
    continuation = r.read(continuation_dir / "prepared.json")
    h.validate_packet_budget(original)
    h.approved(original_dir / "prepared.json", original_dir / "approval.json")
    r.approval(recovery_dir / "approval.json", recovery_dir / "prepared.json", recovery)
    c.approval(continuation_dir / "approval.json", continuation_dir / "prepared.json", continuation)
    for group in ("original", "recovery"):
        for name, digest in continuation["prior_hashes"][group].items():
            h.require(hashes[group].get(name) == digest, "Immutable promotion prefix drift")
    ledger = r.read(original_dir / "program-ledger.json")
    h.require(
        ledger["limit_usd"] == 1
        and ledger["attempt_limit"] == h.PROGRAM_ATTEMPTS
        and ledger["phase1_slots"] == original["cases"] == continuation["original_slots"]
        and ledger["phase1_reserved_usd"] == original["phase_reserved_usd"]
        and ledger["packet_sha256"] == hashes["original"]["prepared.json"]
        and ledger["approval_sha256"] == h.digest(r.read(original_dir / "approval.json")),
        "Original program allocation/slot binding drift",
    )
    failed = r.read(continuation_dir / "apply-summary.log")
    h.require(
        failed["status"] == "api_continuation_stopped_unverified"
        and failed["reason"] == "Inactive revision has workers",
        "Expected consumed continuation failure record missing",
    )
    continuation_link = r.read(original_dir / c.GUARD)["continuation_link"]
    h.require(
        continuation_link["packet_sha256"] == hashes["continuation"]["prepared.json"]
        and continuation_link["continuation_id"] == continuation["continuation_id"]
        and Path(continuation_link["continuation_dir"]) == continuation_dir
        and continuation_link["api_version"] == c.API_VERSION
        and continuation_link["approval_sha256"]
        == h.digest(r.read(continuation_dir / "approval.json")),
        "Consumed continuation ownership drift",
    )
    for path in (
        continuation_dir / "consumed.json",
        original_dir / "api-2025-update-consumed.json",
    ):
        h.require(
            r.read(path)["continuation_link"] == continuation_link,
            "Successful API2025 promotion link drift",
        )
    h.require(
        r.read(original_dir / "api-2025-update-consumed.json")["proposal_sha256"]
        == hashes["original"]["update-proposal.json"],
        "API2025 promotion proposal drift",
    )
    finish_packet_path = finish_dir / "prepared.json"
    f.approval(finish_dir / "approval.json", h.file_hash(finish_packet_path), finish_packet)
    finish_guard = r.read(original_dir / f.GUARD)
    finish_approval = r.read(finish_dir / "approval.json")
    finish_link = finish_guard["finish_link"]
    h.require(
        finish_link["packet_sha256"] == h.file_hash(finish_dir / "prepared.json")
        and finish_link["finish_id"] == finish_packet["finish_id"]
        and finish_link["approval_sha256"] == h.digest(finish_approval)
        and finish_packet["ready_sha256"] == f.READY_SHA,
        "Consumed finish ownership/link drift",
    )
    h.require(
        r.read(finish_dir / "consumed.json")["finish_link"] == finish_link
        and r.read(finish_dir / "consumed.json")["deployment_repeated"] is False,
        "Finish consumption journal drift",
    )
    for index in range(ACCEPTED_CASE_COUNT):
        passed = r.read(original_dir / f"case-{index}-passed.json")
        f.verify_case_evidence(
            original_dir,
            finish_dir,
            index,
            passed,
            stream=original["cases"][index]["stream"],
        )
        consumed = r.read(original_dir / f"case-{index}-consumed.json")
        h.require(
            consumed["attempts"] == 1
            and consumed["reserve_usd"] == original["cases"][index]["reserve_usd"],
            "Previously consumed case identity drift",
        )
    case2 = original["cases"][RECONCILED_CASE_INDEX]
    case2_consumed = r.read(original_dir / f"case-{RECONCILED_CASE_INDEX}-consumed.json")
    case2_ownership = r.read(finish_dir / f"case-{RECONCILED_CASE_INDEX}-ownership.json")
    h.require(
        case2_consumed
        == {
            "attempts": 1,
            "reserve_usd": case2["reserve_usd"],
            "finish_link": finish_link,
        }
        and case2_ownership
        == {"original_slot_index": RECONCILED_CASE_INDEX, "finish_link": finish_link}
        and not (original_dir / f"case-{RECONCILED_CASE_INDEX}-passed.json").exists(),
        "Case-2 consumption/ownership must bind its original finish slot until reconciliation",
    )
    h.require(
        not any(
            (original_dir / name).exists()
            for name in (
                f"case-{RESUME_CASE_INDEX}-consumed.json",
                f"case-{RESUME_CASE_INDEX}-observed.json",
                f"case-{RESUME_CASE_INDEX}-observed-http.json",
                f"case-{RESUME_CASE_INDEX}-passed.json",
                "final-deny-consumed.json",
                "restart-consumed.json",
                "restart-passed.json",
                "results.json",
            )
        )
        and not any(
            (finish_dir / name).exists()
            for name in (
                f"case-{RESUME_CASE_INDEX}-ownership.json",
                f"case-{RESUME_CASE_INDEX}-stream-eof.json",
                "final-deny-consumed.json",
                "restart-passed.json",
                "results.json",
            )
        ),
        "Case-3, final DENY, restart, or result was already started",
    )
    h.require(
        Path(recovery["original_dir"]) == original_dir
        and Path(continuation["original_dir"]) == original_dir
        and Path(continuation["recovery_dir"]) == recovery_dir,
        "Original e/a/D directory linkage drift",
    )
    h.unchanged(
        h.accounts(r.read(original_dir / "old-drained.json")["admin"], legacy=True),
        original["original_accounts"],
    )
    return original, recovery, continuation, finish_link


def verify_prior_receipts(
    directories: tuple[Path, Path],
    original: Json,
    finish_link: Json,
    pricing: Any,
    expected_hashes: list[str] | None = None,
) -> tuple[list[str], Json]:
    """Revalidate prior settled cases before binding them into the resumed result."""
    original_dir, finish_dir = directories
    accounts = original["original_accounts"]
    hashes = []
    for index in range(ACCEPTED_CASE_COUNT):
        case = original["cases"][index]
        pass_path = original_dir / f"case-{index}-passed.json"
        consumed = r.read(original_dir / f"case-{index}-consumed.json")
        ownership = r.read(finish_dir / f"case-{index}-ownership.json")
        passed = r.read(pass_path)
        h.require(
            consumed["attempts"] == 1
            and consumed["reserve_usd"] == case["reserve_usd"]
            and ownership["original_slot_index"] == index
            and ownership["finish_link"] == finish_link
            and passed["finish_link"] == finish_link,
            "Prior accepted case ownership/link drift",
        )
        f.verify_case_evidence(
            original_dir,
            finish_dir,
            index,
            passed,
            stream=case["stream"],
        )
        observed = r.read(original_dir / f"case-{index}-observed.json")
        usage = h.response_usage({"status": "completed", "usage": observed["usage"]})
        debit = estimate_response_usage_cost(
            SimpleNamespace(
                body=json.dumps({"usage": usage}).encode(),
                headers={"content-type": "application/json"},
            ),
            case["model"],
            pricing,
        )
        recorded = passed.get("debit_usd")
        if debit is None:
            raise h.RefusalError("Prior pass receipt has no configured-price estimate")
        if not isinstance(recorded, (int, float)) or isinstance(recorded, bool):
            raise h.RefusalError("Prior pass receipt debit is not numeric")
        recorded_value = float(recorded)
        h.require(
            math.isfinite(recorded_value)
            and recorded_value <= case["reserve_usd"]
            and debit <= case["reserve_usd"]
            and abs(recorded_value - debit) <= h.TOLERANCE,
            "Prior pass receipt debit/reserve does not match configured usage pricing",
        )
        next_accounts = passed["accounts"]
        h.verify_debit(accounts, next_accounts, case["group"], debit)
        accounts = next_accounts
        hashes.append(h.file_hash(pass_path))
    if expected_hashes is not None:
        h.require(hashes == expected_hashes, "Approved prior pass receipts changed")
    return hashes, accounts


def reconciliation(
    original_dir: Path,
    finish_dir: Path,
    finish_packet: Json,
    finish_link: Json,
    data: Json,
) -> Json:
    path = finish_dir / f"case-{RECONCILED_CASE_INDEX}-reconciliation.json"
    r.private_file(path)
    original = r.read(original_dir / "prepared.json")
    expected_allow = [
        {
            "name": "g1-executor",
            "ipAddressRange": finish_packet["executor_ip"] + "/32",
            "action": "Allow",
        }
    ]
    h.require(
        data["schema"] == "g1-ready-finish-case-reconciliation-v1"
        and data["finish_id"] == finish_packet["finish_id"]
        and data["finish_packet_sha256"] == h.file_hash(finish_dir / "prepared.json")
        and data["finish_approval_sha256"] == h.file_hash(finish_dir / "approval.json")
        and data["prior_hashes"] == finish_packet["prior_hashes"]
        and data["binding"] == finish_packet["binding"]
        and data["original_consumed_finish_link"] == finish_link
        and data["original_packet_sha256"]
        == finish_packet["prior_hashes"]["original"]["prepared.json"]
        and data["case_index"] == RECONCILED_CASE_INDEX
        and data["original_case"] == original["cases"][RECONCILED_CASE_INDEX]
        and data["no_cloud_mutation"] is True
        and data["case3_unstarted"] is True,
        "Case-2 reconciliation provenance mismatch",
    )
    observed_path = original_dir / f"case-{RECONCILED_CASE_INDEX}-observed.json"
    http_path = original_dir / f"case-{RECONCILED_CASE_INDEX}-observed-http.json"
    h.require(
        h.file_hash(observed_path) == data["observed_sha256"]
        and h.file_hash(http_path) == data["http_sha256"]
        and h.file_hash(original_dir / f"case-{RECONCILED_CASE_INDEX}-consumed.json")
        == data["case_consumed_sha256"]
        and h.file_hash(finish_dir / f"case-{RECONCILED_CASE_INDEX}-ownership.json")
        == data["case_ownership_sha256"],
        "Case-2 dispatch evidence drift",
    )
    observed, http = r.read(observed_path), r.read(http_path)
    h.require(
        http == {"status": h.HTTP_OK}
        and observed["http_status"] == h.HTTP_OK
        and observed["completed"] is True
        and data["http_status"] == h.HTTP_OK
        and data["completed"] is True,
        "Case-2 terminal result not successfully observed",
    )
    case = r.read(original_dir / "prepared.json")["cases"][RECONCILED_CASE_INDEX]
    h.require(case["stream"] is False, "Case-2 stream requires a separate EOF amendment")
    usage = h.response_usage({"status": "completed", "usage": observed["usage"]})
    h.require(data["usage"] == usage, "Case-2 numeric usage reconciliation drift")
    h.require(
        data["before_accounts"] == r.read(original_dir / "case-1-passed.json")["accounts"],
        "Case-2 starting financial map drift",
    )
    h.require(
        type(data["case2_debit_usd"]) in {float, int}
        and data["case2_debit_usd"] >= 0
        and data["case2_debit_usd"] <= case["reserve_usd"]
        and data["case2_reserve_usd"] == case["reserve_usd"]
        and data["settlement_verified"] is True
        and data["zero_reservations"] is True,
        "Case-2 reconciliation exceeds original reserve or lacks settlement",
    )
    h.verify_debit(
        data["before_accounts"],
        data["after_accounts"],
        case["group"],
        data["case2_debit_usd"],
    )
    h.unchanged(
        h.accounts(data["snapshot"]["admin"]),
        data["after_accounts"],
    )
    h.require(
        data["snapshot"].get("ready") is True
        and h.process_identity(data["snapshot"])
        == h.process_identity(r.read(finish_dir / "prepared.json")["baseline"]),
        "Case-2 reconciliation snapshot process/readiness drift",
    )
    previous_pass_hashes = [
        h.file_hash(original_dir / f"case-{index}-passed.json")
        for index in range(ACCEPTED_CASE_COUNT)
    ]
    h.require(
        data["current_allow_sha256"] == h.digest(expected_allow)
        and data["executor_ip_sha256"] == h.digest(finish_packet["executor_ip"])
        and (
            "previous_pass_hashes" not in data
            or data["previous_pass_hashes"] == previous_pass_hashes
        ),
        "Case-2 reconciliation ownership/fence/prior-result binding drift",
    )
    return data


def verify_case2_price(reconciled: Json, original_dir: Path, original: Json, pricing: Any) -> None:
    case = original["cases"][RECONCILED_CASE_INDEX]
    observed = r.read(original_dir / f"case-{RECONCILED_CASE_INDEX}-observed.json")
    usage = h.response_usage({"status": "completed", "usage": observed["usage"]})
    debit = estimate_response_usage_cost(
        SimpleNamespace(
            body=json.dumps({"usage": usage}).encode(),
            headers={"content-type": "application/json"},
        ),
        case["model"],
        pricing,
    )
    h.require(
        debit is not None
        and debit <= case["reserve_usd"]
        and abs(debit - reconciled["case2_debit_usd"]) <= h.TOLERANCE,
        "Case-2 reconciliation no longer matches configured pricing/reserve",
    )


def release_binding(original: Json, recovery: Json, continuation: Json) -> Json:
    return {
        "finish": f.binding(original, recovery, continuation),
        "resume_sha256": h.file_hash(Path(__file__)),
        "tests_sha256": h.file_hash(ROOT / "tests/unit/test_table_production_acceptance_resume.py"),
    }


def continuation_budget() -> r.Budget:
    budget = r.Budget()
    budget.end = min(budget.end, time.monotonic() + TOTAL_SECONDS)
    return budget


def topology_receipt(inventory: list[Json]) -> list[Json]:
    """Persist revision activity and worker names without raw template/config data."""
    return [
        {
            "name": item["name"],
            "active": item["active"],
            "worker_names": [worker["name"] for worker in item["workers"]],
        }
        for item in inventory
    ]


def locks(
    stack: ExitStack,
    directories: tuple[Path, Path, Path, Path],
    resume_dir: Path | None = None,
) -> None:
    original_dir, recovery_dir, continuation_dir, finish_dir = directories
    for path in (
        original_dir / "execution.lock",
        original_dir / r.PROGRAM_LOCK,
        original_dir / c.CONTINUATION_LOCK,
        recovery_dir / "execution.lock",
        continuation_dir / "execution.lock",
    ):
        stack.enter_context(r.lock(path, existing=True))
    stack.enter_context(r.lock(original_dir / f.FINISH_LOCK, existing=True))
    stack.enter_context(r.lock(finish_dir / "execution.lock", existing=True))
    if resume_dir is not None:
        stack.enter_context(r.lock(original_dir / RESUME_LOCK))


def prepare(args: argparse.Namespace) -> None:
    r.directory(args.artifact_dir)
    h.require(not any(args.artifact_dir.iterdir()), "Fresh resume directory required")
    finish_dir = args.finish_dir
    r.directory(finish_dir)
    finish_packet = r.read(finish_dir / "prepared.json")
    h.require(finish_packet["schema"] == "g1-ready-finish-v1", "Initial finish packet schema")
    budget = continuation_budget()
    with ExitStack() as stack:
        locks(
            stack,
            (args.original_dir, args.recovery_dir, args.continuation_dir, finish_dir),
        )
        original, recovery, continuation, finish_link = prior_history(
            (args.original_dir, args.recovery_dir, args.continuation_dir, finish_dir), finish_packet
        )
        rec = reconciliation(
            args.original_dir,
            finish_dir,
            finish_packet,
            finish_link,
            r.read(finish_dir / f"case-{RECONCILED_CASE_INDEX}-reconciliation.json"),
        )
        h.require(
            str(args.executor_ip) == finish_packet["executor_ip"],
            "Existing executor-only ingress address changed",
        )
        release = release_binding(original, recovery, continuation)
        ready_path = Path(finish_packet["ready_path"])
        ready = f.evidence(ready_path, original, finish_packet["prior_hashes"])
        f.production(budget, original)
        allow = [
            {
                "name": "g1-executor",
                "ipAddressRange": str(args.executor_ip) + "/32",
                "action": "Allow",
            }
        ]
        _azure, app, values, snapshot, details = f.current(budget, original, ready, allow=allow)
        settings = h.settings_from(values)
        verify_case2_price(rec, args.original_dir, original, settings.pricing)
        prior_case_hashes, prior_case_accounts = verify_prior_receipts(
            (args.original_dir, finish_dir),
            original,
            finish_link,
            settings.pricing,
        )
        h.unchanged(prior_case_accounts, rec["before_accounts"])
        f.verify_revision_binding(
            details["inventory"], finish_packet["inventory"], snapshot["revision"]
        )
        h.require(
            h.process_identity(snapshot) == h.process_identity(rec["snapshot"])
            and snapshot["generation"] == rec["snapshot"]["generation"]
            and snapshot["revision"] == finish_packet["baseline"]["revision"],
            "Reconciled case-2 process/revision changed",
        )
        current_accounts = h.accounts(snapshot["admin"])
        h.unchanged(current_accounts, rec["after_accounts"])
        h.require(
            app["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] == allow,
            "Existing executor-only Allow drift",
        )
        r.public_wait(budget, original["origin"], h.HTTP_OK)
        packet = {
            "schema": SCHEMA,
            "resume_id": uuid.uuid4().hex,
            "original_dir": str(args.original_dir),
            "recovery_dir": str(args.recovery_dir),
            "continuation_dir": str(args.continuation_dir),
            "finish_dir": str(finish_dir),
            "deny_target": {
                "subscription": original["subscription"],
                "resource_group": original["test_rg"],
                "app": original["test_app"],
                "app_id": original["test_projection"]["id"],
                "origin": original["origin"],
            },
            "finish_packet_sha256": h.file_hash(finish_dir / "prepared.json"),
            "finish_approval_sha256": h.file_hash(finish_dir / "approval.json"),
            "reconciliation_path": str(
                finish_dir / f"case-{RECONCILED_CASE_INDEX}-reconciliation.json"
            ),
            "reconciliation_sha256": h.file_hash(
                finish_dir / f"case-{RECONCILED_CASE_INDEX}-reconciliation.json"
            ),
            "prior_hashes": finish_packet["prior_hashes"],
            "finish_link": finish_link,
            "finish_guard_sha256": h.file_hash(args.original_dir / f.GUARD),
            "binding": release,
            "ready_path": str(ready_path),
            "ready_sha256": f.READY_SHA,
            "baseline": snapshot,
            "current_projection": r.shape(h.projection(app)),
            "inventory": details["inventory"],
            "pins": details["pins"],
            "prior_case_hashes": prior_case_hashes,
            "executor_ip": str(args.executor_ip),
            "original_case3": original["cases"][RESUME_CASE_INDEX],
            "original_case3_index": RESUME_CASE_INDEX,
            "original_case3_reserve_usd": original["cases"][RESUME_CASE_INDEX]["reserve_usd"],
            "case2_after_accounts_sha256": h.digest(rec["after_accounts"]),
            "program_limit_usd": 1,
            "program_attempt_limit": h.PROGRAM_ATTEMPTS,
            "original_phase_reserved_usd": original["phase_reserved_usd"],
            "ingress_allow_already_consumed": True,
            "remaining_ingress_mutations": 1,
            "remaining_paid_dispatches": 1,
            "restart_count_remaining": 1,
        }
        durable_create(budget, args.artifact_dir / "prepared.json", packet)
    print(
        json.dumps(
            {
                "status": "g1_resume_prepared_not_approved",
                "packet_sha256": h.file_hash(args.artifact_dir / "prepared.json"),
            }
        )
    )


def approval(path: Path, prepared_sha256: str, packet: Json) -> Json:
    data = r.read(path)
    keys = {
        "verdict",
        "packet_sha256",
        "independent_reviewer",
        "finish_packet_sha256",
        "reconciliation_sha256",
        "deny_target_sha256",
        "prior_hashes_sha256",
        "resume_id",
        "revision",
        "generation_sha256",
        "case2_reconciliation_verified",
        "case3_unused_verified",
        "original_budget_verified",
        "no_new_allow_or_budget",
        "deny_after_every_post_consume_outcome",
        "ambiguous_deny_no_retry",
        "pre_boundary_lock_failure_nonmutating",
        "previous_executors_exited",
        "production_writer_paused",
        "staged_executor_allow_min1_accepted",
        "one_restart_only",
    }
    h.require(
        set(data) == keys
        and data["verdict"] == "approved"
        and bool(data["independent_reviewer"])
        and data["packet_sha256"] == prepared_sha256
        and data["finish_packet_sha256"] == packet["finish_packet_sha256"]
        and data["reconciliation_sha256"] == packet["reconciliation_sha256"]
        and data["deny_target_sha256"] == h.digest(packet["deny_target"])
        and data["prior_hashes_sha256"] == h.digest(packet["prior_hashes"])
        and data["resume_id"] == packet["resume_id"]
        and data["revision"] == packet["baseline"]["revision"]
        and data["generation_sha256"] == h.digest(packet["baseline"]["generation"]),
        "Fresh exact continuation approval required",
    )
    target = packet.get("deny_target")
    h.require(
        isinstance(target, dict)
        and set(target) == {"subscription", "resource_group", "app", "app_id", "origin"}
        and all(isinstance(value, str) and value for value in target.values()),
        "Pinned final-DENY target required",
    )
    for key in (
        "case2_reconciliation_verified",
        "case3_unused_verified",
        "original_budget_verified",
        "no_new_allow_or_budget",
        "deny_after_every_post_consume_outcome",
        "ambiguous_deny_no_retry",
        "pre_boundary_lock_failure_nonmutating",
        "previous_executors_exited",
        "production_writer_paused",
        "staged_executor_allow_min1_accepted",
        "one_restart_only",
    ):
        h.require(data[key] is True, "Continuation scope/ownership not approved")
    return data


def apply(args: argparse.Namespace) -> None:  # noqa: PLR0915 -- one immutable original slot only
    r.directory(args.artifact_dir)
    prepared_path = args.artifact_dir / "prepared.json"
    budget = continuation_budget()
    with ExitStack() as stack:
        # Lock the fresh identity before reading its approval-bound bytes.
        stack.enter_context(r.lock(args.artifact_dir / "execution.lock"))
        r.private_file(prepared_path)
        h.require(
            {path.name for path in args.artifact_dir.iterdir()}
            == {"prepared.json", "approval.json", "execution.lock"},
            "Resume identity contains unexpected/started files",
        )
        raw = prepared_path.read_bytes()
        h.require(len(raw) <= h.MAX_BYTES, "Artifact capacity exceeded")
        value = json.loads(raw)
        h.require(isinstance(value, dict), "Object continuation packet required")
        packet = dict(value)
        packet_sha256 = hashlib.sha256(raw).hexdigest()
        h.require(packet.get("schema") == SCHEMA, "Continuation packet schema mismatch")
        verdict = approval(args.approval, packet_sha256, packet)
        original_dir = Path(packet["original_dir"])
        recovery_dir = Path(packet["recovery_dir"])
        continuation_dir = Path(packet["continuation_dir"])
        finish_dir = Path(packet["finish_dir"])
        locks(
            stack,
            (original_dir, recovery_dir, continuation_dir, finish_dir),
            args.artifact_dir,
        )
        h.require(
            h.file_hash(prepared_path) == packet_sha256,
            "Prepared resume packet changed after approval",
        )
        h.require(
            not (original_dir / RESUME_GUARD).exists() and not (original_dir / DENY_GUARD).exists(),
            "G1 resume already consumed; fresh directories cannot replay",
        )
        deny_target = packet["deny_target"]
        resume_link = {
            "resume_id": packet["resume_id"],
            "packet_sha256": packet_sha256,
            "resume_dir": str(args.artifact_dir),
            "approval_sha256": h.digest(verdict),
            "finish_packet_sha256": packet["finish_packet_sha256"],
            "reconciliation_sha256": packet["reconciliation_sha256"],
            "finish_link": packet["finish_link"],
            "binding": packet["binding"],
            "ready_sha256": packet["ready_sha256"],
        }
        deny_observed = False
        resume_marker_path = original_dir / RESUME_GUARD
        resume_marker_durable = False

        def deny_once() -> None:
            nonlocal deny_observed
            h.require(
                resume_marker_durable,
                "Global resume marker is not durable; DENY mutation is not authorized",
            )
            resume_guard_path = original_dir / RESUME_GUARD
            h.require(
                resume_guard_path.is_file() and not resume_guard_path.is_symlink(),
                "Resume consumption marker is not durable; DENY mutation is not authorized",
            )
            resume_guard = r.read(resume_guard_path)
            h.require(
                resume_guard["resume_link"] == resume_link
                and resume_guard["finish_link"] == packet["finish_link"],
                "Different continuation owns the durable resume marker",
            )
            h.require(
                not (original_dir / DENY_GUARD).exists(),
                "Resume DENY already consumed; ambiguous outcome is not retried",
            )
            journal_error: Exception | None = None
            try:
                durable_create(
                    budget,
                    original_dir / DENY_GUARD,
                    {"policy_sha256": h.digest(h.DENY), "resume_link": resume_link},
                )
            except FileExistsError:
                # Another actor may already have consumed this DENY; never issue a second one.
                raise
            except (OSError, TimeoutError, h.RefusalError) as error:
                # The global resume marker already fences replay, so attempt the one DENY
                # even if its secondary audit record failed before/after becoming visible.
                journal_error = error
            azure = c.AllRevisionsAzure(
                deny_target["subscription"],
                deny_target["resource_group"],
                deny_target["app"],
                budget,
            )
            budget.call(
                azure.ingress,
                deny_target["app_id"],
                h.DENY,
                limit=DENY_WRITE_SECONDS,
            )
            r.public_wait(budget, deny_target["origin"], h.HTTP_DENIED)
            deny_observed = True
            if journal_error is not None:
                raise h.RefusalError(
                    "DENY was observed but its journal write failed; no retry or restart"
                ) from journal_error

        paid_complete = False
        after: Json | None = None
        last_accounts: Json | None = None
        try:
            # This durable marker precedes every execution-time history/live-state check.
            durable_create(
                budget,
                resume_marker_path,
                {
                    "case_index": RESUME_CASE_INDEX,
                    "finish_link": packet["finish_link"],
                    "resume_link": resume_link,
                },
            )
            resume_marker_durable = True
            finish_packet = r.read(finish_dir / "prepared.json")
            h.require(
                packet["prior_hashes"] == finish_packet["prior_hashes"],
                "Continuation base hash manifest drift",
            )
            original, recovery, continuation, finish_link = prior_history(
                (original_dir, recovery_dir, continuation_dir, finish_dir),
                finish_packet,
                resume_consumed=True,
            )
            reconciliation_data = reconciliation(
                original_dir,
                finish_dir,
                finish_packet,
                finish_link,
                r.read(Path(packet["reconciliation_path"])),
            )
            h.require(
                finish_link == packet["finish_link"]
                and h.file_hash(original_dir / f.GUARD) == packet["finish_guard_sha256"]
                and h.file_hash(Path(packet["reconciliation_path"]))
                == packet["reconciliation_sha256"]
                and release_binding(original, recovery, continuation) == packet["binding"]
                and deny_target
                == {
                    "subscription": original["subscription"],
                    "resource_group": original["test_rg"],
                    "app": original["test_app"],
                    "app_id": original["test_projection"]["id"],
                    "origin": original["origin"],
                },
                "Continuation source/history/reconciliation/deny-target binding drift",
            )
            reserve_tail = (
                ARTIFACT_SECONDS
                + DENY_WRITE_SECONDS
                + DENY_PUBLIC_SECONDS
                + DRAIN_SECONDS
                + POST_DRAIN_SECONDS
                + RESTART_SECONDS
                + r.CLEANUP_SECONDS
            )
            work_seconds = max(0.0, budget.end - time.monotonic() - reserve_tail)
            with f.bounded_phase(budget, work_seconds):
                h.require(
                    h.file_hash(prepared_path) == packet_sha256,
                    "Continuation packet changed after approval",
                )
                h.require(
                    release_binding(original, recovery, continuation) == packet["binding"],
                    "Continuation code/dependency binding drift",
                )
                ready = f.evidence(Path(packet["ready_path"]), original, packet["prior_hashes"])
                f.production(budget, original)
                allow = [
                    {
                        "name": "g1-executor",
                        "ipAddressRange": packet["executor_ip"] + "/32",
                        "action": "Allow",
                    }
                ]
                azure, app, values, baseline, details = f.current(
                    budget, original, ready, allow=allow
                )
                f.verify_revision_binding(
                    details["inventory"], packet["inventory"], baseline["revision"]
                )
                h.require(
                    h.process_identity(baseline) == h.process_identity(packet["baseline"])
                    and baseline["generation"] == packet["baseline"]["generation"]
                    and baseline["revision"] == packet["baseline"]["revision"],
                    "Approved resume worker/process/generation changed",
                )
                last_accounts = h.accounts(baseline["admin"])
                h.unchanged(last_accounts, reconciliation_data["after_accounts"])
                settings = h.settings_from(values)
                _prior_case_hashes, prior_case_accounts = verify_prior_receipts(
                    (original_dir, finish_dir),
                    original,
                    finish_link,
                    settings.pricing,
                    expected_hashes=packet["prior_case_hashes"],
                )
                h.unchanged(prior_case_accounts, reconciliation_data["before_accounts"])
                verify_case2_price(reconciliation_data, original_dir, original, settings.pricing)
                h.require(
                    app["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"]
                    == allow,
                    "Existing executor-only Allow drift",
                )
                r.public_wait(budget, original["origin"], h.HTTP_OK)
                case2_proof = {
                    "observation_sha256": reconciliation_data["observed_sha256"],
                    "http_sha256": reconciliation_data["http_sha256"],
                }
                durable_create(
                    budget,
                    original_dir / f"case-{RECONCILED_CASE_INDEX}-passed.json",
                    {
                        "debit_usd": reconciliation_data["case2_debit_usd"],
                        "accounts": reconciliation_data["after_accounts"],
                        "evidence": case2_proof,
                        "reconciliation_sha256": packet["reconciliation_sha256"],
                        "reconciled_after_stopped_apply": True,
                        "finish_link": finish_link,
                        "resume_link": resume_link,
                    },
                )
                f.verify_case_evidence(
                    original_dir,
                    finish_dir,
                    2,
                    r.read(original_dir / f"case-{RECONCILED_CASE_INDEX}-passed.json"),
                    stream=False,
                )
                case = original["cases"][RESUME_CASE_INDEX]
                h.require(
                    case == packet["original_case3"]
                    and case["reserve_usd"] == packet["original_case3_reserve_usd"],
                    "Original case-3 slot identity/reserve drift",
                )
                durable_create(
                    budget,
                    original_dir / f"case-{RESUME_CASE_INDEX}-consumed.json",
                    {
                        "reserve_usd": case["reserve_usd"],
                        "attempts": 1,
                        "resume_link": resume_link,
                    },
                )
                durable_create(
                    budget,
                    args.artifact_dir / f"case-{RESUME_CASE_INDEX}-ownership.json",
                    {"original_slot_index": RESUME_CASE_INDEX, "resume_link": resume_link},
                )
                # Wait for any already-approved readiness propagation before the final snapshot.
                # No control-plane wait is allowed between the snapshot and the paid dispatch.
                r.public_wait(budget, original["origin"], h.HTTP_OK)
                pre_dispatch_data = f.current(budget, original, ready, allow=allow)
                (
                    _azure,
                    pre_dispatch_app,
                    pre_dispatch_values,
                    pre_dispatch,
                    pre_dispatch_details,
                ) = pre_dispatch_data
                f.verify_revision_binding(
                    pre_dispatch_details["inventory"],
                    packet["inventory"],
                    pre_dispatch["revision"],
                )
                h.require(
                    h.process_identity(pre_dispatch) == h.process_identity(baseline)
                    and pre_dispatch["generation"] == baseline["generation"],
                    "Case-3 pre-dispatch worker/process/generation changed",
                )
                h.unchanged(last_accounts, h.accounts(pre_dispatch["admin"]))
                h.require(
                    pre_dispatch_app["properties"]["configuration"]["ingress"][
                        "ipSecurityRestrictions"
                    ]
                    == allow,
                    "Case-3 pre-dispatch executor fence drift",
                )
                pre_dispatch_settings = h.settings_from(pre_dispatch_values)
                observed = budget.call(
                    h.dispatch,
                    original["origin"],
                    h.credential(pre_dispatch_values, "FOUNDRY_CLIENT_API_KEYS_JSON"),
                    case,
                    original_dir / f"case-{RESUME_CASE_INDEX}-observed.json",
                    limit=DISPATCH_SECONDS,
                )
                if case["stream"]:
                    durable_create(
                        budget,
                        args.artifact_dir / f"case-{RESUME_CASE_INDEX}-stream-eof.json",
                        {"completed": True, "clean_eof": True, "resume_link": resume_link},
                    )
                proof = f.case_evidence(
                    original_dir,
                    args.artifact_dir,
                    RESUME_CASE_INDEX,
                    stream=case["stream"],
                )
                h.require(
                    observed["http_status"] == h.HTTP_OK and observed["completed"] is True,
                    "Resume case-3 terminal response invalid",
                )
                usage = h.response_usage({"status": "completed", "usage": observed["usage"]})
                debit = estimate_response_usage_cost(
                    SimpleNamespace(
                        body=json.dumps({"usage": usage}).encode(),
                        headers={"content-type": "application/json"},
                    ),
                    case["model"],
                    pre_dispatch_settings.pricing,
                )
                h.require(
                    debit is not None and debit <= case["reserve_usd"],
                    "Resume case-3 cost exceeds its original reserve",
                )
                assert debit is not None
                _azure, _app, _values, after, after_details = f.current(
                    budget, original, ready, allow=allow
                )
                f.verify_revision_binding(
                    after_details["inventory"], packet["inventory"], after["revision"]
                )
                h.require(
                    h.process_identity(after) == h.process_identity(baseline),
                    "Resume paid worker changed",
                )
                next_accounts = h.accounts(after["admin"])
                h.verify_debit(last_accounts, next_accounts, case["group"], debit)
                last_accounts = next_accounts
                durable_create(
                    budget,
                    original_dir / f"case-{RESUME_CASE_INDEX}-passed.json",
                    {
                        "debit_usd": debit,
                        "accounts": last_accounts,
                        "evidence": proof,
                        "finish_link": finish_link,
                        "resume_link": resume_link,
                    },
                )
                f.verify_case_evidence(
                    original_dir,
                    args.artifact_dir,
                    RESUME_CASE_INDEX,
                    r.read(original_dir / f"case-{RESUME_CASE_INDEX}-passed.json"),
                    stream=case["stream"],
                )
                paid_complete = True
        finally:
            if not resume_marker_durable:
                resume_marker_durable = confirm_durable_resume_marker(
                    budget, resume_marker_path, packet["finish_link"], resume_link
                )
            if resume_marker_durable:
                deny_once()

        h.require(
            paid_complete and deny_observed and after is not None and last_accounts is not None,
            "Resume did not complete case-3 settlement before DENY",
        )
        assert after is not None and last_accounts is not None
        budget.pause(DRAIN_SECONDS)
        with f.bounded_phase(budget, POST_DRAIN_SECONDS):
            _azure, final_app, _values, final, final_details = f.current(budget, original, ready)
            f.verify_revision_binding(
                final_details["inventory"], packet["inventory"], final["revision"]
            )
            h.require(
                h.process_identity(final) == h.process_identity(after)
                and final["request_counters"] == after["request_counters"],
                "Resume final quiet drain/process/request counter drift",
            )
            h.unchanged(h.accounts(final["admin"]), last_accounts)
            durable_create(
                budget,
                original_dir / "restart-consumed.json",
                {"snapshot": final, "finish_link": finish_link, "resume_link": resume_link},
            )
        with f.bounded_phase(budget, RESTART_SECONDS):
            budget.call(
                azure.app_command,
                ["revision", "restart", "--revision", final["revision"]],
                limit=RESTART_SECONDS,
            )
            f.restart_wait(
                budget,
                azure,
                (
                    final_app["properties"]["template"],
                    f.revision_template(final_details["inventory"], final["revision"]),
                ),
                final,
                original["image"],
            )
            _azure, _app, _values, restarted, restarted_details = f.current(budget, original, ready)
            f.verify_revision_binding(
                restarted_details["inventory"], packet["inventory"], restarted["revision"]
            )
            h.require(
                h.process_identity(restarted) != h.process_identity(final),
                "Resume restart did not replace the current process",
            )
            h.unchanged(h.accounts(restarted["admin"]), last_accounts)
            topology = f.topology(
                restarted_details["inventory"],
                restarted["revision"],
                original["image"],
                f.revision_template(packet["inventory"], restarted["revision"]),
            )
            h.require(len(topology) == 1, "Restarted current revision worker topology invalid")
            topology_evidence = topology_receipt(restarted_details["inventory"])
            r.public_wait(budget, original["origin"], h.HTTP_DENIED)
            durable_create(
                budget,
                original_dir / "restart-passed.json",
                {
                    **restarted,
                    "revision_topology": topology_evidence,
                    "finish_link": finish_link,
                    "resume_link": resume_link,
                },
            )
            result = {
                "schema": "g1-fence-recovery-result-v1",
                "g1_four_calls_and_restart": "passed",
                "original_apply_completed": False,
                "ingress": "fenced",
                "min_replicas": 1,
                "original_min": original["original_min"],
                "restoration": "Separate reviewed cleanup required",
                "case_hashes": [
                    h.file_hash(original_dir / f"case-{index}-passed.json")
                    for index in range(h.PHASE_ATTEMPTS)
                ],
                "restart_sha256": h.file_hash(original_dir / "restart-passed.json"),
                "revision_topology": topology_evidence,
                "prior_hashes": packet["prior_hashes"],
                "binding": packet["binding"]["finish"],
                "resume_binding": packet["binding"],
                "ready_sha256": f.READY_SHA,
                "recovery_link": r.read(original_dir / r.GUARD)["recovery_link"],
                "continuation_link": r.read(original_dir / c.GUARD)["continuation_link"],
                "finish_link": finish_link,
                "resume_link": resume_link,
                "case2_reconciliation_sha256": packet["reconciliation_sha256"],
            }
            durable_create(
                budget,
                original_dir / "results.json",
                {**result, "finish_link": finish_link, "resume_link": resume_link},
            )
            durable_create(
                budget,
                args.artifact_dir / "results.json",
                {
                    **result,
                    "original_result_sha256": h.file_hash(original_dir / "results.json"),
                    "finish_link": finish_link,
                    "resume_link": resume_link,
                },
            )
    print(json.dumps({"status": "g1_resume_four_cases_restart_passed_fenced_cleanup_pending"}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="phase", required=True)
    prep = sub.add_parser("prepare")
    for name in ("original-dir", "recovery-dir", "continuation-dir", "finish-dir", "artifact-dir"):
        prep.add_argument("--" + name, type=Path, required=True)
    prep.add_argument("--executor-ip", required=True)
    run = sub.add_parser("apply")
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
        TimeoutError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "g1_resume_stopped_unverified",
                    "exception_type": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, h.RefusalError)
                    else "Details withheld",
                    "recovery": (
                        "Keep the consumed case and liability; no replay, refund, or restart"
                    ),
                }
            )
        )
        return 2
    finally:
        logging.disable(prior)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
