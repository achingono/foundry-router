"""Mocked single-slot G1 continuation; no Azure/provider request or mutation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/quality"))
sys.path.insert(0, str(ROOT / "tests/unit"))

FINISH_SPEC = importlib.util.spec_from_file_location(
    "resume_fixture_finish_tests", ROOT / "tests/unit/test_table_production_acceptance_finish.py"
)
assert FINISH_SPEC and FINISH_SPEC.loader
finish_tests = importlib.util.module_from_spec(FINISH_SPEC)
FINISH_SPEC.loader.exec_module(finish_tests)
finish = finish_tests.f
sys.modules["table_production_acceptance_finish"] = finish

RESUME_SPEC = importlib.util.spec_from_file_location(
    "table_production_acceptance_resume",
    ROOT / "scripts/quality/table_production_acceptance_resume.py",
)
assert RESUME_SPEC and RESUME_SPEC.loader
resume = importlib.util.module_from_spec(RESUME_SPEC)
RESUME_SPEC.loader.exec_module(resume)
REAL_BUDGET = resume.r.Budget


def _reconciliation(data: dict[str, Any]) -> None:
    h, r = finish.h, finish.r
    original_dir, finish_dir = data["original"], data["own"]
    original = r.read(original_dir / "prepared.json")
    finish_packet = r.read(finish_dir / "prepared.json")
    case = original["cases"][resume.RECONCILED_CASE_INDEX]
    assert case["stream"] is False
    observed_path = original_dir / f"case-{resume.RECONCILED_CASE_INDEX}-observed.json"
    http_path = original_dir / f"case-{resume.RECONCILED_CASE_INDEX}-observed-http.json"
    observed, http = r.read(observed_path), r.read(http_path)
    usage = h.response_usage({"status": "completed", "usage": observed["usage"]})
    settings = h.settings_from(data["test"].env)
    debit = finish.estimate_response_usage_cost(
        SimpleNamespace(
            body=json.dumps({"usage": usage}).encode(),
            headers={"content-type": "application/json"},
        ),
        case["model"],
        settings.pricing,
    )
    assert debit is not None and debit <= case["reserve_usd"]
    before = r.read(original_dir / "case-1-passed.json")["accounts"]
    snapshot = data["test"].snapshot()
    after = h.accounts(snapshot["admin"])
    h.verify_debit(before, after, case["group"], debit)
    ready = r.read(data["ready"] / "ready.json")
    allow = [
        {
            "name": "g1-executor",
            "ipAddressRange": finish_packet["executor_ip"] + "/32",
            "action": "Allow",
        }
    ]
    reconciliation = {
        "schema": "g1-ready-finish-case-reconciliation-v1",
        "captured_at_utc": "synthetic",
        "finish_id": finish_packet["finish_id"],
        "finish_packet_sha256": h.file_hash(finish_dir / "prepared.json"),
        "finish_approval_sha256": h.file_hash(finish_dir / "approval.json"),
        "original_packet_sha256": finish_packet["prior_hashes"]["original"]["prepared.json"],
        "original_consumed_finish_link": r.read(original_dir / finish.GUARD)["finish_link"],
        "prior_hashes": finish_packet["prior_hashes"],
        "binding": finish_packet["binding"],
        "case_index": resume.RECONCILED_CASE_INDEX,
        "original_case": case,
        "http_status": http["status"],
        "completed": observed["completed"],
        "usage": usage,
        "observed_sha256": h.file_hash(observed_path),
        "http_sha256": h.file_hash(http_path),
        "case_consumed_sha256": h.file_hash(
            original_dir / f"case-{resume.RECONCILED_CASE_INDEX}-consumed.json"
        ),
        "case_ownership_sha256": h.file_hash(
            finish_dir / f"case-{resume.RECONCILED_CASE_INDEX}-ownership.json"
        ),
        "case2_debit_usd": debit,
        "case2_reserve_usd": case["reserve_usd"],
        "before_accounts": before,
        "after_accounts": after,
        "settlement_verified": True,
        "zero_reservations": True,
        "snapshot": snapshot,
        "revision_inventory": finish_packet["inventory"],
        "executor_ip_sha256": h.digest(finish_packet["executor_ip"]),
        "current_allow_sha256": h.digest(allow),
        "case3_unstarted": True,
        "no_case2_pass_record_before_reconciliation": True,
        "no_cloud_mutation": True,
    }
    h.create(finish_dir / "case-2-reconciliation.json", reconciliation)
    assert ready["snapshot"]["revision"] == snapshot["revision"]


@pytest.fixture
def partial_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    data = finish_tests.capsule.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(resume, "f", finish)
    monkeypatch.setattr(resume, "c", finish.c)
    monkeypatch.setattr(resume, "r", finish.r)
    monkeypatch.setattr(resume, "h", finish.h)
    finish_tests.approved(data)

    original_snapshot = finish.r.snapshot
    calls = 0

    def fail_post_case2_snapshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 7:
            raise finish.h.RefusalError("No unique structured snapshot; console withheld")
        return original_snapshot(*args, **kwargs)

    monkeypatch.setattr(finish.r, "snapshot", fail_post_case2_snapshot)
    with pytest.raises(finish.h.RefusalError, match="No unique structured snapshot"):
        finish.apply(
            argparse.Namespace(artifact_dir=data["own"], approval=data["own"] / "approval.json")
        )
    assert calls == 7
    monkeypatch.setattr(finish.r, "snapshot", original_snapshot)
    _reconciliation(data)
    resume_dir = tmp_path / "resume"
    resume_dir.mkdir(mode=0o700)
    data["resume"] = resume_dir
    return data


def resume_args(data: dict[str, Any]) -> argparse.Namespace:
    packet = finish.r.read(data["own"] / "prepared.json")
    return argparse.Namespace(
        original_dir=data["original"],
        recovery_dir=data["recovery"],
        continuation_dir=data["continuation"],
        finish_dir=data["own"],
        artifact_dir=data["resume"],
        executor_ip=packet["executor_ip"],
    )


def approve_resume(data: dict[str, Any]) -> Path:
    resume.prepare(resume_args(data))
    packet_path = data["resume"] / "prepared.json"
    packet = finish.r.read(packet_path)
    value = {
        "verdict": "approved",
        "packet_sha256": finish.h.file_hash(packet_path),
        "independent_reviewer": "synthetic-independent-review",
        "finish_packet_sha256": packet["finish_packet_sha256"],
        "reconciliation_sha256": packet["reconciliation_sha256"],
        "deny_target_sha256": finish.h.digest(packet["deny_target"]),
        "prior_hashes_sha256": finish.h.digest(packet["prior_hashes"]),
        "resume_id": packet["resume_id"],
        "revision": packet["baseline"]["revision"],
        "generation_sha256": finish.h.digest(packet["baseline"]["generation"]),
        "case2_reconciliation_verified": True,
        "case3_unused_verified": True,
        "original_budget_verified": True,
        "no_new_allow_or_budget": True,
        "deny_after_every_post_consume_outcome": True,
        "ambiguous_deny_no_retry": True,
        "pre_boundary_lock_failure_nonmutating": True,
        "previous_executors_exited": True,
        "production_writer_paused": True,
        "staged_executor_allow_min1_accepted": True,
        "one_restart_only": True,
    }
    approval_path = data["resume"] / "approval.json"
    finish.h.create(approval_path, value)
    return approval_path


def test_resume_uses_only_case3_then_denies_and_restarts_once(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    original_expected, finish_expected = resume.partial_entries(
        finish.r.read(partial_run["original"] / "prepared.json")
    )
    assert {path.name for path in partial_run["original"].iterdir()} == original_expected
    assert {path.name for path in partial_run["own"].iterdir()} == finish_expected
    before = partial_run["test"].mutations.copy()
    resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations[len(before) :] == ["case-3", "deny", "restart"]
    original = partial_run["original"]
    assert (original / "case-2-passed.json").exists()
    assert (original / "case-3-passed.json").exists()
    assert (original / resume.RESUME_GUARD).exists()
    assert (original / resume.DENY_GUARD).exists()
    assert (original / "restart-passed.json").exists()
    result = finish.r.read(original / "results.json")
    assert result["g1_four_calls_and_restart"] == "passed"
    assert result["case2_reconciliation_sha256"] == finish.h.file_hash(
        partial_run["own"] / "case-2-reconciliation.json"
    )
    assert result["case_hashes"] == [
        finish.h.file_hash(original / f"case-{index}-passed.json") for index in range(4)
    ]
    assert result["restart_sha256"] == finish.h.file_hash(original / "restart-passed.json")
    assert result["resume_binding"]["resume_sha256"] == resume.h.file_hash(Path(resume.__file__))
    restart = finish.r.read(original / "restart-passed.json")
    assert result["revision_topology"] == restart["revision_topology"]
    active_revisions = [
        revision for revision in result["revision_topology"] if revision["active"] is True
    ]
    assert len(active_revisions) == 1
    assert len(active_revisions[0]["worker_names"]) == 1
    assert all(
        revision["active"] is False and not revision["worker_names"]
        for revision in result["revision_topology"]
        if revision is not active_revisions[0]
    )
    own_result = finish.r.read(partial_run["resume"] / "results.json")
    assert own_result["original_result_sha256"] == finish.h.file_hash(original / "results.json")


def test_prepare_rejects_case2_ownership_contents_even_if_reconciliation_hash_is_updated(
    partial_run: dict[str, Any],
) -> None:
    owner_path = partial_run["own"] / "case-2-ownership.json"
    owner = finish.r.read(owner_path)
    owner["original_slot_index"] = 1
    owner_path.write_text(json.dumps(owner))
    reconciliation_path = partial_run["own"] / "case-2-reconciliation.json"
    reconciliation = finish.r.read(reconciliation_path)
    reconciliation["case_ownership_sha256"] = finish.h.file_hash(owner_path)
    reconciliation_path.write_text(json.dumps(reconciliation))
    before = partial_run["test"].mutations.copy()

    with pytest.raises(finish.h.RefusalError, match="Case-2 consumption/ownership"):
        resume.prepare(resume_args(partial_run))

    assert partial_run["test"].mutations == before


def test_apply_rejects_rebound_case2_ownership_after_global_marker_and_denies_once(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    owner_path = partial_run["own"] / "case-2-ownership.json"
    owner = finish.r.read(owner_path)
    owner["original_slot_index"] = 1
    owner_path.write_text(json.dumps(owner))
    reconciliation_path = partial_run["own"] / "case-2-reconciliation.json"
    reconciliation = finish.r.read(reconciliation_path)
    reconciliation["case_ownership_sha256"] = finish.h.file_hash(owner_path)
    reconciliation_path.write_text(json.dumps(reconciliation))
    packet_path = partial_run["resume"] / "prepared.json"
    packet = finish.r.read(packet_path)
    packet["reconciliation_sha256"] = finish.h.file_hash(reconciliation_path)
    packet_path.write_text(json.dumps(packet))
    approval = finish.r.read(approval_path)
    approval["reconciliation_sha256"] = packet["reconciliation_sha256"]
    approval["packet_sha256"] = finish.h.file_hash(packet_path)
    approval_path.write_text(json.dumps(approval))
    before = partial_run["test"].mutations.copy()

    with pytest.raises(finish.h.RefusalError, match="Case-2 consumption/ownership"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))

    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / resume.RESUME_GUARD).exists()
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "case-3-consumed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_prepare_rejects_reconciliation_finish_link_drift(partial_run: dict[str, Any]) -> None:
    reconciliation_path = partial_run["own"] / "case-2-reconciliation.json"
    reconciliation = finish.r.read(reconciliation_path)
    reconciliation["original_consumed_finish_link"] = {"finish_id": "different"}
    reconciliation_path.write_text(json.dumps(reconciliation))
    before = partial_run["test"].mutations.copy()

    with pytest.raises(finish.h.RefusalError, match="Case-2 reconciliation provenance"):
        resume.prepare(resume_args(partial_run))
    assert partial_run["test"].mutations == before


def test_reconciliation_accepts_v1_without_prior_pass_hash_field(
    partial_run: dict[str, Any],
) -> None:
    original_dir, finish_dir = partial_run["original"], partial_run["own"]
    finish_packet = finish.r.read(finish_dir / "prepared.json")
    finish_link = finish.r.read(original_dir / finish.GUARD)["finish_link"]
    data = finish.r.read(finish_dir / "case-2-reconciliation.json")

    assert "previous_pass_hashes" not in data
    assert (
        resume.reconciliation(
            original_dir,
            finish_dir,
            finish_packet,
            finish_link,
            data,
        )
        == data
    )


def test_reconciliation_rejects_mismatched_optional_prior_pass_hashes(
    partial_run: dict[str, Any],
) -> None:
    original_dir, finish_dir = partial_run["original"], partial_run["own"]
    finish_packet = finish.r.read(finish_dir / "prepared.json")
    finish_link = finish.r.read(original_dir / finish.GUARD)["finish_link"]
    data = finish.r.read(finish_dir / "case-2-reconciliation.json")
    data["previous_pass_hashes"] = ["0" * 64, "0" * 64]

    with pytest.raises(finish.h.RefusalError, match="prior-result binding drift"):
        resume.reconciliation(
            original_dir,
            finish_dir,
            finish_packet,
            finish_link,
            data,
        )


def test_pre_dispatch_drift_attempts_one_deny_without_case3_or_restart(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    partial_run["test"].env["FOUNDRY_RETRY_ATTEMPTS"] = "1"
    with pytest.raises(finish.h.RefusalError):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / resume.RESUME_GUARD).exists()
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "case-3-consumed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_prior_case_financial_receipt_drift_after_approval_denies_before_case3(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    pass_path = partial_run["original"] / "case-1-passed.json"
    passed = finish.r.read(pass_path)
    passed["debit_usd"] += 0.01
    pass_path.write_text(json.dumps(passed))
    with pytest.raises(finish.h.RefusalError):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / resume.RESUME_GUARD).exists()
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "case-3-consumed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_prior_pass_financial_receipt_change_after_prepare_denies_before_case3(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    pass_path = partial_run["original"] / "case-1-passed.json"
    passed = finish.r.read(pass_path)
    passed["debit_usd"] += 0.01
    pass_path.write_text(json.dumps(passed))
    with pytest.raises(finish.h.RefusalError):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / resume.RESUME_GUARD).exists()
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "case-3-consumed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_financial_drift_after_case3_consumption_denies_before_dispatch(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    test = partial_run["test"]
    before = test.mutations.copy()
    original_write = resume.durable_create

    def mutate_after_slot_owner(budget: Any, path: Path, value: dict[str, Any]) -> None:
        original_write(budget, path, value)
        if path.name == f"case-{resume.RESUME_CASE_INDEX}-ownership.json":
            test.balances["two"]["estimated_remaining_usd"] += 0.01

    monkeypatch.setattr(resume, "durable_create", mutate_after_slot_owner)
    with pytest.raises(finish.h.RefusalError, match="Persisted account state changed"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert test.mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / f"case-{resume.RESUME_CASE_INDEX}-consumed.json").exists()
    assert not (partial_run["original"] / f"case-{resume.RESUME_CASE_INDEX}-observed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_state_drift_during_readiness_wait_is_caught_by_final_snapshot(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    test = partial_run["test"]
    before = test.mutations.copy()
    original_wait = resume.r.public_wait

    def drift_after_ready_wait(budget: Any, origin: str, expected: int) -> None:
        original_wait(budget, origin, expected)
        if expected == resume.h.HTTP_OK:
            test.balances["two"]["estimated_remaining_usd"] += 0.01

    monkeypatch.setattr(resume.r, "public_wait", drift_after_ready_wait)
    with pytest.raises(finish.h.RefusalError, match="Persisted account state changed"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert test.mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / "case-3-consumed.json").exists()
    assert not (partial_run["original"] / "case-3-observed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_post_marker_case_history_refusal_attempts_deny_once(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    finish.h.create(partial_run["original"] / "case-3-consumed.json", {"stale": True})
    with pytest.raises(finish.h.RefusalError, match="unknown or started operations"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / resume.RESUME_GUARD).exists()
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_resume_marker_write_failure_after_visibility_still_denies(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    original_create = resume.h.create
    guard = partial_run["original"] / resume.RESUME_GUARD

    def create_then_fail(path: Path, value: dict[str, Any]) -> None:
        original_create(path, value)
        if path == guard:
            raise OSError("synthetic post-fsync interruption")

    monkeypatch.setattr(resume.h, "create", create_then_fail)
    with pytest.raises(OSError, match="post-fsync interruption"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert guard.exists()
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert not (partial_run["original"] / "case-3-consumed.json").exists()


def test_resume_marker_failure_before_visibility_does_not_mutate_ingress(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    resume_guard = partial_run["original"] / resume.RESUME_GUARD
    original_create = resume.h.create

    def fail_global_marker_before_write(path: Path, value: dict[str, Any]) -> None:
        if path == resume_guard:
            raise OSError("synthetic global marker pre-write failure")
        original_create(path, value)

    monkeypatch.setattr(resume.h, "create", fail_global_marker_before_write)
    with pytest.raises(OSError, match="global marker pre-write failure"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations == before
    assert not resume_guard.exists()
    assert not (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "case-3-consumed.json").exists()


def test_marker_durability_confirmation_timeout_performs_no_cloud_mutation(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    monkeypatch.setattr(resume.r, "Budget", REAL_BUDGET)
    before = partial_run["test"].mutations.copy()
    original_create = resume.h.create
    guard = partial_run["original"] / resume.RESUME_GUARD

    def visible_marker_then_lost_ack(path: Path, value: dict[str, Any]) -> None:
        original_create(path, value)
        if path == guard:
            monkeypatch.setattr(resume.os, "fsync", lambda _fd: time.sleep(12))
            raise OSError("synthetic lost marker acknowledgement")

    monkeypatch.setattr(resume.h, "create", visible_marker_then_lost_ack)
    with pytest.raises(OSError, match="lost marker acknowledgement"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert guard.exists()
    assert partial_run["test"].mutations == before
    assert not (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "case-3-consumed.json").exists()


def test_deny_marker_write_failure_still_attempts_deny_once_and_stops(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    original_create = resume.h.create
    deny_marker = partial_run["original"] / resume.DENY_GUARD

    def create_deny_marker_then_fail(path: Path, value: dict[str, Any]) -> None:
        original_create(path, value)
        if path == deny_marker:
            raise OSError("synthetic deny-journal fsync failure")

    monkeypatch.setattr(resume.h, "create", create_deny_marker_then_fail)
    with pytest.raises(finish.h.RefusalError, match="journal write failed"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert deny_marker.exists()
    assert partial_run["test"].mutations[len(before) :] == ["case-3", "deny"]
    assert (
        partial_run["test"].deployment["properties"]["configuration"]["ingress"][
            "ipSecurityRestrictions"
        ]
        == finish.h.DENY
    )
    assert not (partial_run["original"] / "restart-consumed.json").exists()
    assert not (partial_run["original"] / "results.json").exists()


def test_deny_journal_write_failure_before_visibility_still_denies_once(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    deny_marker = partial_run["original"] / resume.DENY_GUARD
    original_create = resume.h.create

    def fail_before_deny_journal(path: Path, value: dict[str, Any]) -> None:
        if path == deny_marker:
            raise OSError("synthetic pre-write journal failure")
        original_create(path, value)

    monkeypatch.setattr(resume.h, "create", fail_before_deny_journal)
    with pytest.raises(finish.h.RefusalError, match="journal write failed"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert not deny_marker.exists()
    assert partial_run["test"].mutations[len(before) :] == ["case-3", "deny"]
    assert (
        partial_run["test"].deployment["properties"]["configuration"]["ingress"][
            "ipSecurityRestrictions"
        ]
        == finish.h.DENY
    )
    assert not (partial_run["original"] / "restart-consumed.json").exists()


def test_preexisting_deny_journal_race_suppresses_second_patch(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    deny_marker = partial_run["original"] / resume.DENY_GUARD
    original_create = resume.h.create

    def race_deny_journal(path: Path, value: dict[str, Any]) -> None:
        if path == deny_marker:
            original_create(path, {"competing_attempt": True})
            raise FileExistsError("synthetic concurrent DENY marker")
        original_create(path, value)

    monkeypatch.setattr(resume.h, "create", race_deny_journal)
    with pytest.raises(FileExistsError):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert deny_marker.exists()
    assert partial_run["test"].mutations[len(before) :] == ["case-3"]
    assert not (partial_run["original"] / "restart-consumed.json").exists()


def test_dispatch_failure_retains_case3_liability_denies_without_retry(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    calls = 0

    def unknown_dispatch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("synthetic unknown dispatch")

    monkeypatch.setattr(resume.h, "dispatch", unknown_dispatch)
    with pytest.raises(httpx.ReadTimeout):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert calls == 1
    assert partial_run["test"].mutations[len(before) :] == ["deny"]
    assert (partial_run["original"] / "case-3-consumed.json").exists()
    assert not (partial_run["original"] / "case-3-passed.json").exists()
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_post_drain_snapshot_has_reserved_deadline_and_blocks_restart(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    original_current = resume.f.current
    calls = 0

    def fail_slow_final_snapshot(budget: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 4:
            assert 0 < budget.end - resume.time.monotonic() <= resume.POST_DRAIN_SECONDS
            raise TimeoutError("synthetic post-drain snapshot deadline")
        return original_current(budget, *args, **kwargs)

    monkeypatch.setattr(resume.f, "current", fail_slow_final_snapshot)
    with pytest.raises(TimeoutError, match="post-drain snapshot deadline"):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert calls == 4
    assert partial_run["test"].mutations[len(before) :] == ["case-3", "deny"]
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    assert not (partial_run["original"] / "restart-consumed.json").exists()


def test_ambiguous_deny_is_never_retried_and_new_directory_cannot_replay(
    partial_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval_path = approve_resume(partial_run)
    test = partial_run["test"]
    original_ingress = test.ingress
    before = test.mutations.copy()

    def deny_then_timeout(app_id: str, policy: list[dict[str, Any]]) -> None:
        original_ingress(app_id, policy)
        if policy == resume.h.DENY:
            raise TimeoutError("synthetic ambiguous deny acknowledgement")

    monkeypatch.setattr(test, "ingress", deny_then_timeout)
    with pytest.raises(TimeoutError):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert test.mutations[len(before) :].count("deny") == 1
    assert (partial_run["original"] / resume.DENY_GUARD).exists()
    after_deny = test.mutations.copy()

    replay = partial_run["resume"].parent / "resume-replay"
    replay.mkdir(mode=0o700)
    for name in ("prepared.json", "approval.json"):
        finish.h.create(replay / name, finish.r.read(partial_run["resume"] / name))
    with pytest.raises(finish.h.RefusalError, match="already consumed"):
        resume.apply(argparse.Namespace(artifact_dir=replay, approval=replay / "approval.json"))
    assert test.mutations == after_deny
    assert test.mutations[len(before) :].count("deny") == 1
    assert not (partial_run["original"] / "restart-passed.json").exists()


def test_pre_boundary_approval_failure_does_not_mutate(
    partial_run: dict[str, Any],
) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    approval = finish.r.read(approval_path)
    approval["packet_sha256"] = "wrong"
    approval_path.write_text(json.dumps(approval))
    with pytest.raises(finish.h.RefusalError):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations == before
    assert not (partial_run["original"] / resume.RESUME_GUARD).exists()


def test_pre_boundary_lock_failure_does_not_mutate(partial_run: dict[str, Any]) -> None:
    approval_path = approve_resume(partial_run)
    before = partial_run["test"].mutations.copy()
    with (
        finish.r.lock(partial_run["original"] / "execution.lock", existing=True),
        pytest.raises(BlockingIOError),
    ):
        resume.apply(argparse.Namespace(artifact_dir=partial_run["resume"], approval=approval_path))
    assert partial_run["test"].mutations == before
    assert not (partial_run["original"] / resume.RESUME_GUARD).exists()


def test_fsync_records_use_the_active_budget_limit(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    limits: list[float] = []

    class RecordingBudget:
        def call(self, function: Any, *args: Any, limit: float, **kwargs: Any) -> Any:
            limits.append(limit)
            return function(*args, **kwargs)

    path = tmp_path / "bounded.json"
    resume.durable_create(RecordingBudget(), path, {"consumed": True})
    assert limits == [resume.ARTIFACT_SECONDS]
    assert finish.r.read(path) == {"consumed": True}


def test_durable_records_use_the_active_phase_deadline(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    observed_limits: list[float] = []

    class RecordingBudget:
        def call(self, function: Any, *args: Any, limit: float, **kwargs: Any) -> Any:
            observed_limits.append(limit)
            return function(*args, **kwargs)

    target = tmp_path / "durable.json"
    resume.durable_create(RecordingBudget(), target, {"marker": "consumed"})
    assert observed_limits == [resume.ARTIFACT_SECONDS]
    assert finish.r.read(target) == {"marker": "consumed"}


def test_durable_record_write_is_interrupted_by_real_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = resume.r.Budget()
    started = time.monotonic()

    def stalled_write(*_args: Any, **_kwargs: Any) -> None:
        time.sleep(12)

    monkeypatch.setattr(resume.h, "create", stalled_write)
    with pytest.raises(TimeoutError):
        resume.durable_create(budget, tmp_path / "stalled.json", {"blocked": True})
    assert time.monotonic() - started < 10
