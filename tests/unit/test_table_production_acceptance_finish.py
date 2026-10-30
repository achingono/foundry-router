"""Ready-only finish mocks; no cloud deployment, provider request or prior-file edit."""

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
    "table_production_acceptance_finish",
    ROOT / "scripts/quality/table_production_acceptance_finish.py",
)
assert SPEC and SPEC.loader
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)
FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "readonly_continue_fixtures",
    Path(__file__).with_name("test_table_production_acceptance_continue.py"),
)
assert FIXTURE_SPEC and FIXTURE_SPEC.loader
previous = importlib.util.module_from_spec(FIXTURE_SPEC)
FIXTURE_SPEC.loader.exec_module(previous)


@pytest.fixture
def capsule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:  # noqa: PLR0915
    data = previous.capsule.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(f, "c", previous.c)
    monkeypatch.setattr(f, "r", previous.c.r)
    approval = previous.prepared(data)
    monkeypatch.setattr(
        f.r,
        "workers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            f.h.RefusalError("Inactive revision has workers")
        ),
    )
    with pytest.raises(f.h.RefusalError, match="Inactive revision has workers"):
        previous.c.apply(argparse.Namespace(artifact_dir=data["new"], approval=approval))
    f.h.create(
        data["new"] / "apply-summary.log",
        {
            "status": "api_continuation_stopped_unverified",
            "reason": "Inactive revision has workers",
        },
    )
    monkeypatch.setattr(f, "CONTINUE_PREP_SHA", f.h.file_hash(data["new"] / "prepared.json"))
    fake_class = previous.recovery_tests.FakeAzure
    original_metadata = fake_class.app_command
    test = data["test"]
    test.restart_states = []
    test.forced_topology = None
    test.restart_ticks_changed = True

    def metadata(self: Any, arguments: list[str]) -> Any:
        if arguments[:2] == ["revision", "restart"]:
            assert not any(
                op in {"stop", "patch"}
                for op in self.mutations[len(data["before"]) :]
                if op == "stop"
            )
            self.mutations.append("restart")
            self.container = "restarted-current-container"
            self.restart_count += 1
            if self.restart_ticks_changed:
                self.ticks = "40"
            if self.fault == "restart_balance":
                self.balances["two"]["estimated_remaining_usd"] -= 1
            return None
        result = original_metadata(self, arguments)
        if arguments[:2] == ["revision", "list"]:
            assert arguments.count("--all") == 1
            if self.restart_states:
                self.forced_topology = self.restart_states.pop(0)
            for row in result:
                template = copy.deepcopy(self.deployment["properties"]["template"])
                if row["name"] != self.deployment["properties"]["latestReadyRevisionName"]:
                    template["containers"][0]["image"] = "synthetic-old-image"
                row["properties"]["template"] = template
                if row["name"] == "current" and self.forced_topology == "inactive":
                    row["properties"]["active"] = False
            return result
        if arguments[:2] == ["replica", "list"] and arguments[-1] == "current":
            if self.forced_topology in {"zero", "inactive"}:
                return []
            if self.forced_topology == "two":
                return [*result, {**result[0], "name": "temporary-current-replica"}]
        return result

    monkeypatch.setattr(fake_class, "app_command", metadata)
    # Deployment is already finished: forbid another raw REST/template operation for the finish.
    monkeypatch.setattr(
        fake_class,
        "run",
        lambda *_args: (_ for _ in ()).throw(AssertionError("No finish deployment allowed")),
    )
    original_dispatch = f.h.dispatch

    def dispatch_with_wire_evidence(
        origin: str, key: str, case: dict[str, Any], observed: Path
    ) -> dict[str, Any]:
        result = original_dispatch(origin, key, case, observed)
        f.h.create(observed.with_name(observed.stem + "-http.json"), {"status": 200})
        if case["stream"]:
            f.h.create(
                observed.with_name(observed.stem + "-terminal.json"),
                {
                    "terminal_observed": True,
                    "usage": result["usage"],
                    "clean_eof": False,
                },
            )
        return result

    monkeypatch.setattr(f.h, "dispatch", dispatch_with_wire_evidence)
    ready_dir, own_dir = tmp_path / "ready-evidence", tmp_path / "finish"
    ready_dir.mkdir(mode=0o700)
    own_dir.mkdir(mode=0o700)
    app = test.show()
    ready_inventory = [
        {
            "name": revision["name"],
            "active": revision["properties"]["active"],
            "image": revision["properties"]["template"]["containers"][0]["image"],
            "workers": [
                {"name": row["name"], "containers": row["properties"]["containers"]}
                for row in test.app_command(["replica", "list", "--revision", revision["name"]])
            ],
        }
        for revision in test.app_command(["revision", "list", "--all"])
    ]
    ready = {
        "app_projection": f.h.projection(app),
        "public_status": 403,
        "snapshot": {**test.snapshot(), "ready": True},
        "revision_inventory": ready_inventory,
        "expected_accounts": copy.deepcopy(test.balances),
        "original_packet_sha256": f.h.file_hash(data["original"] / "prepared.json"),
        "continuation_prepared_sha256": f.h.file_hash(data["new"] / "prepared.json"),
        "continuation_failure_sha256": f.h.file_hash(data["new"] / "apply-summary.log"),
    }
    f.h.create(ready_dir / "ready.json", ready)
    monkeypatch.setattr(f, "READY_SHA", f.h.file_hash(ready_dir / "ready.json"))
    original_snapshot = fake_class.snapshot

    def snapshot(self: Any) -> dict[str, Any]:
        value = dict(original_snapshot(self))
        value["ready"] = True
        return value

    monkeypatch.setattr(fake_class, "snapshot", snapshot)
    data.update(
        continuation=data["new"], own=own_dir, ready=ready_dir, finish_before=test.mutations.copy()
    )
    return dict(data)


def args(data: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        original_dir=data["original"],
        recovery_dir=data["recovery"],
        continuation_dir=data["continuation"],
        ready_evidence_dir=data["ready"],
        artifact_dir=data["own"],
        executor_ip="192.0.2.25",
    )


def approved(data: dict[str, Any]) -> Path:
    f.prepare(args(data))
    packet = f.r.read(data["own"] / "prepared.json")
    path = data["own"] / "approval.json"
    f.h.create(
        path,
        {
            "verdict": "approved",
            "packet_sha256": f.h.file_hash(data["own"] / "prepared.json"),
            "independent_reviewer": "synthetic-independent-review",
            "prior_hashes_sha256": f.h.digest(packet["prior_hashes"]),
            "ready_sha256": f.READY_SHA,
            "revision": packet["baseline"]["revision"],
            "generation_sha256": f.h.digest(packet["baseline"]["generation"]),
            "finish_accepted": True,
            "unused_slots_verified": True,
            "current_ready_old_workers_zero": True,
            "financial_equality_verified": True,
            "previous_executors_exited": True,
            "production_writer_paused": True,
            "staged_fenced_min1_accepted": True,
        },
    )
    return Path(path)


def test_ready_finish_exactly_four_original_slots_no_deployment(capsule: dict[str, Any]) -> None:
    hashes = {
        "original": {name: f.h.file_hash(capsule["original"] / name) for name in f.ORIGINAL_FILES},
        "recovery": {
            name: f.h.file_hash(capsule["recovery"] / name) for name in f.c.RECOVERY_FILES
        },
        "continuation": {
            name: f.h.file_hash(capsule["continuation"] / name) for name in f.CONTINUE_FILES
        },
    }
    approval = approved(capsule)
    assert capsule["test"].mutations == capsule["finish_before"]
    f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    assert capsule["test"].mutations[len(capsule["finish_before"]) :] == [
        "allow",
        "case-0",
        "case-1",
        "case-2",
        "case-3",
        "deny",
        "restart",
    ]
    for directory, key in (
        (capsule["original"], "original"),
        (capsule["recovery"], "recovery"),
        (capsule["continuation"], "continuation"),
    ):
        f.r.immutable(directory, hashes[key])
    result = f.r.read(capsule["original"] / "results.json")
    assert (
        result["schema"] == "g1-fence-recovery-result-v1" and not result["original_apply_completed"]
    )
    assert (
        len(result["case_hashes"]) == 4
        and result["finish_link"]
        and result["continuation_link"]
        and result["recovery_link"]
    )
    for index, case in enumerate(capsule["original_value"]["cases"]):
        passed = f.r.read(capsule["original"] / f"case-{index}-passed.json")
        f.verify_case_evidence(
            capsule["original"],
            capsule["own"],
            index,
            passed,
            stream=case["stream"],
        )
    with pytest.raises(f.h.RefusalError, match="already consumed"):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))


def test_accepted_case_hash_chain_detects_observation_drift(capsule: dict[str, Any]) -> None:
    approval = approved(capsule)
    f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    case = capsule["original_value"]["cases"][0]
    passed = f.r.read(capsule["original"] / "case-0-passed.json")
    f.verify_case_evidence(capsule["original"], capsule["own"], 0, passed, stream=case["stream"])
    observed_path = capsule["original"] / "case-0-observed.json"
    observed = f.r.read(observed_path)
    observed["evidence_marker"] = "tampered"
    observed_path.write_text(json.dumps(observed))
    with pytest.raises(f.h.RefusalError, match="hash chain drift"):
        f.verify_case_evidence(
            capsule["original"], capsule["own"], 0, passed, stream=case["stream"]
        )


def test_prepared_bytes_are_locked_and_rechecked_before_mutation(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = approved(capsule)
    prepared = capsule["own"] / "prepared.json"
    original_approval = f.approval

    def replace_after_approval(path: Path, digest: str, packet: dict[str, Any]) -> dict[str, Any]:
        with pytest.raises(BlockingIOError):
            with f.r.lock(capsule["own"] / "execution.lock", existing=True):
                pass
        result = original_approval(path, digest, packet)
        prepared.write_text("{}")
        return result

    monkeypatch.setattr(f, "approval", replace_after_approval)
    with pytest.raises(f.h.RefusalError, match="changed after approval"):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    assert capsule["test"].mutations == capsule["finish_before"]
    assert not (capsule["original"] / f.GUARD).exists()


def test_restart_phase_budget_caps_nested_work_and_restores_overall_deadline() -> None:
    budget = f.r.Budget()
    overall_end = budget.end
    with f.bounded_phase(budget, f.r.WORKER_SECONDS):
        assert budget.end <= overall_end
        assert budget.end - f.time.monotonic() <= f.r.WORKER_SECONDS
    assert budget.end == overall_end


@pytest.mark.parametrize("states", [["zero", "two", "one"], ["inactive", "two", "one"]])
def test_owned_current_rolling_restart_finishes_only_at_settled_one(
    capsule: dict[str, Any], states: list[str]
) -> None:
    approval = approved(capsule)
    original_command = previous.recovery_tests.FakeAzure.app_command

    def restart(self: Any, arguments: list[str]) -> Any:
        result = original_command(self, arguments)
        if arguments[:2] == ["revision", "restart"]:
            self.restart_states = states.copy()
        return result

    from unittest.mock import patch

    with patch.object(previous.recovery_tests.FakeAzure, "app_command", restart):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    assert (capsule["original"] / "restart-passed.json").exists()
    assert capsule["test"].forced_topology == "one"


@pytest.mark.parametrize(
    "where,name",
    [
        ("original", "case-0-consumed.json"),
        ("original", "case-2-observed-terminal.json"),
        ("original", "successor-baseline.json"),
        ("original", "restart-consumed.json"),
        ("continuation", "case-0-ownership.json"),
        ("original", "ready-finish-consumed.json"),
        ("original", "results.json"),
    ],
)
def test_started_or_ambiguous_histories_refuse_without_allow(
    capsule: dict[str, Any], where: str, name: str
) -> None:
    f.h.create(capsule[where] / name, {})
    with pytest.raises(f.h.RefusalError):
        f.prepare(args(capsule))
    assert capsule["test"].mutations == capsule["finish_before"]


@pytest.mark.parametrize(
    "fault",
    [
        "missing_current_counter",
        "paid_uncertain",
        "between_cases",
        "same_restart_process",
        "restart_balance",
    ],
)
def test_faults_stop_without_refund_or_later_calls(capsule: dict[str, Any], fault: str) -> None:
    approval = approved(capsule)
    if fault == "same_restart_process":
        capsule["test"].restart_ticks_changed = False
    else:
        capsule["test"].fault = fault
    # Fresh finish snapshots start the same financial-chain counter used in the fixture.
    capsule["test"].snapshots = 0
    with pytest.raises((f.h.RefusalError, httpx.ReadTimeout)):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    assert not (capsule["original"] / "results.json").exists()
    if fault in {"paid_uncertain", "between_cases"}:
        assert not (capsule["original"] / "case-1-consumed.json").exists()


@pytest.mark.parametrize(
    "drift",
    [
        "image",
        "active_old",
        "worker_old",
        "balance",
        "cycle",
        "environment",
        "process",
        "command",
        "counter",
    ],
)
def test_not_ready_or_unapproved_state_refuses_before_money(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    test = capsule["test"]
    if drift == "image":
        test.deployment["properties"]["template"]["containers"][0]["image"] = "unapproved"
    elif drift == "worker_old":
        test.hidden_worker_revision = "historical-1"
    elif drift == "balance":
        test.balances["two"]["estimated_remaining_usd"] += 1
    elif drift == "cycle":
        test.balances["two"]["current_cycle_start_utc"] = "different"
    elif drift == "environment":
        test.env["FOUNDRY_RETRY_ATTEMPTS"] = "1"
    elif drift == "process":
        test.ticks = "other-process"
    elif drift == "counter":
        test.fault = "missing_current_counter"
    else:
        original_metadata = previous.recovery_tests.FakeAzure.app_command
        original_snapshot = previous.recovery_tests.FakeAzure.snapshot

        def metadata(self: Any, arguments: list[str]) -> Any:
            value = original_metadata(self, arguments)
            if drift == "active_old" and arguments[:2] == ["revision", "list"]:
                next(row for row in value if row["name"] == "old")["properties"]["active"] = True
            return value

        def snapshot(self: Any) -> dict[str, Any]:
            value = dict(original_snapshot(self))
            value["server_command_sha256"] = "changed-command"
            return value

        monkeypatch.setattr(previous.recovery_tests.FakeAzure, "app_command", metadata)
        if drift == "command":
            monkeypatch.setattr(previous.recovery_tests.FakeAzure, "snapshot", snapshot)
    with pytest.raises(f.h.RefusalError):
        f.prepare(args(capsule))
    assert not (capsule["original"] / f.GUARD).exists()
    assert capsule["test"].mutations == capsule["finish_before"]


@pytest.mark.parametrize(
    "key",
    [
        "unused_slots_verified",
        "current_ready_old_workers_zero",
        "financial_equality_verified",
        "previous_executors_exited",
        "revision",
        "generation_sha256",
    ],
)
def test_exact_approval_cannot_be_weakened(capsule: dict[str, Any], key: str) -> None:
    approval = approved(capsule)
    value = f.r.read(approval)
    value[key] = "wrong" if key in {"revision", "generation_sha256"} else False
    approval.write_text(json.dumps(value))
    with pytest.raises(f.h.RefusalError):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    assert not (capsule["original"] / f.GUARD).exists()


def test_source_ready_and_lock_drift_refuse(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = approved(capsule)
    with (
        f.r.lock(capsule["continuation"] / "execution.lock", existing=True),
        pytest.raises(BlockingIOError),
    ):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    monkeypatch.setattr(f, "CONTINUE_SHA", "unreviewed")
    with pytest.raises(f.h.RefusalError, match="Frozen continuation"):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))


@pytest.mark.parametrize(
    "state", ["old_worker", "wrong_current_image", "same_generation", "three_current"]
)
def test_restart_observation_never_accepts_unapproved_or_unsettled_topology(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    test = capsule["test"]
    ready = f.r.read(capsule["ready"] / "ready.json")
    azure = f.c.AllRevisionsAzure("synthetic", "rg", "test", f.r.Budget())
    original_metadata = previous.recovery_tests.FakeAzure.app_command
    if state == "old_worker":
        test.hidden_worker_revision = "old"
    elif state == "wrong_current_image":
        test.deployment["properties"]["template"]["containers"][0]["image"] = "old-version"
    elif state == "three_current":

        def metadata(self: Any, arguments: list[str]) -> Any:
            value = original_metadata(self, arguments)
            return (
                value * 3
                if arguments[:2] == ["replica", "list"] and arguments[-1] == "current"
                else value
            )

        monkeypatch.setattr(previous.recovery_tests.FakeAzure, "app_command", metadata)
    clock = iter([0, 0, 0, 181])
    monkeypatch.setattr(f.time, "monotonic", lambda: next(clock))
    with pytest.raises(f.h.RefusalError):
        f.restart_wait(
            f.r.Budget(),
            azure,
            ready["app_projection"]["properties"]["template"],
            ready["snapshot"],
            capsule["original_value"]["image"],
        )


def test_public_deadlines_remain_true_total_no_paid_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    previous.recovery_tests.test_total_public_wait_handles_delay_and_trickle_without_paid_retry(
        monkeypatch
    )


def test_native_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["finish", "apply", "--artifact-dir", "/synthetic", "--approval", "/synthetic/approval"],
    )
    monkeypatch.setattr(f, "apply", lambda _: (_ for _ in ()).throw(TimeoutError("credential")))
    assert f.main() == 2
    assert "credential" not in capsys.readouterr().out


def test_live403_required_before_finish_consumption(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def live(_origin: str, _path: str, _key: str | None = None) -> tuple[int, bytes]:
        return 200, b'{"ready":true}'

    monkeypatch.setattr(f.h, "get_public_async", live)
    monkeypatch.setattr(f.r, "PUBLIC_SECONDS", 0.02)
    with pytest.raises(TimeoutError):
        f.prepare(args(capsule))
    assert not (capsule["original"] / f.GUARD).exists()
    assert capsule["test"].mutations == capsule["finish_before"]


def test_ready_capture_hash_drift_cannot_be_used_as_live_proof(capsule: dict[str, Any]) -> None:
    path = capsule["ready"] / "ready.json"
    path.write_text("{}")
    with pytest.raises(f.h.RefusalError, match="Exact ready evidence"):
        f.prepare(args(capsule))
    assert not (capsule["original"] / f.GUARD).exists()


def test_literal_hydration_does_not_double_hash_or_mutate_projection(
    capsule: dict[str, Any],
) -> None:
    original = f.r.read(capsule["original"] / "prepared.json")
    before = copy.deepcopy(original)
    old = f.original_raw(original, capsule["test"].show())
    assert f.h.projection(old) == original["test_projection"]
    assert original == before


def test_old_worker_appearing_only_during_restart_prevents_completion(
    capsule: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = approved(capsule)
    original_command = previous.recovery_tests.FakeAzure.app_command

    def restart(self: Any, arguments: list[str]) -> Any:
        result = original_command(self, arguments)
        if arguments[:2] == ["revision", "restart"]:
            self.hidden_worker_revision = "old"
        return result

    monkeypatch.setattr(previous.recovery_tests.FakeAzure, "app_command", restart)
    with pytest.raises(f.h.RefusalError, match="Old or unapproved"):
        f.apply(argparse.Namespace(artifact_dir=capsule["own"], approval=approval))
    assert (capsule["original"] / "case-3-passed.json").exists()
    assert not (capsule["original"] / "results.json").exists()
