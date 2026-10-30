"""No-network recovery tests; original G1 fixture code and helpers are read-only."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import signal
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/quality"))
RECOVERY_SPEC = importlib.util.spec_from_file_location(
    "table_production_acceptance_recovery",
    ROOT / "scripts/quality/table_production_acceptance_recovery.py",
)
assert RECOVERY_SPEC and RECOVERY_SPEC.loader
r = importlib.util.module_from_spec(RECOVERY_SPEC)
RECOVERY_SPEC.loader.exec_module(r)

SPEC = importlib.util.spec_from_file_location(
    "readonly_g1_fixtures", Path(__file__).with_name("test_table_production_acceptance.py")
)
assert SPEC and SPEC.loader
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)


class FastBudget:
    def __init__(self) -> None:
        self.end = time.monotonic() + 1800

    def call(self, function: Any, *args: Any, limit: float = 120, **kwargs: Any) -> Any:
        assert limit > 0
        return function(*args, **kwargs)

    def remaining(self, limit: float) -> float:
        return limit

    def pause(self, _seconds: float) -> None:
        return None


class FakeAzure:
    instances: ClassVar[dict[str, FakeAzure]] = {}

    def __init__(self, subscription: str, resource_group: str, name: str, budget: Any):
        if name in self.instances:
            self.__dict__ = self.instances[name].__dict__
            return
        self.subscription, self.resource_group, self.app, self.budget = (
            subscription,
            resource_group,
            name,
            budget,
        )
        self.env = fixtures.values()
        self.deployment = fixtures.app(name)
        self.active, self.live, self.draining = True, True, 0
        self.ticks, self.container, self.restart_count = "10", "old-container", 0
        self.deployment["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = (
            copy.deepcopy(r.h.DENY)
        )
        self.balances = r.h.accounts(fixtures.snapshot()["admin"])
        self.requests: list[str] = []
        self.mutations: list[str] = []
        self.fault = ""
        self.snapshots = 0
        if name == "production":
            self.env["FOUNDRY_STATE_BACKEND"] = "memory"
            self.env["FOUNDRY_BACKENDS_JSON"] = self.env["FOUNDRY_BACKENDS_JSON"].replace(
                "dedicated", "production"
            )
            self.deployment["properties"]["template"]["containers"][0]["image"] = (
                "synthetic@sha256:" + "b" * 64
            )
        self.instances[name] = self

    def show(self) -> dict[str, Any]:
        return copy.deepcopy(self.deployment)

    def writers(
        self, *, allow_none: bool = False, allow_draining: bool = False
    ) -> list[dict[str, Any]]:
        if not self.active:
            assert allow_draining
            if self.draining:
                self.draining -= 1
                return [{"name": "old-draining", "properties": {"containers": []}}]
            return []
        if not self.live:
            assert allow_none
            return []
        return [
            {
                "revision": self.deployment["properties"]["latestReadyRevisionName"],
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

    def ingress(self, _app_id: str, restrictions: list[dict[str, Any]]) -> None:
        self.mutations.append("deny" if restrictions == r.h.DENY else "allow")
        self.deployment["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = (
            copy.deepcopy(restrictions)
        )
        if not self.live and restrictions != r.h.DENY:
            self.live = True
            self.ticks = "20"
            self.container = "warm-old-container"
            if self.fault == "cold_balance":
                self.balances["one"]["estimated_remaining_usd"] += 1

    def app_command(self, arguments: list[str]) -> Any:
        assert arguments[0] != "update"
        if arguments[:2] == ["revision", "deactivate"]:
            self.mutations.append("stop")
            self.active, self.draining = False, 2
        elif arguments[:2] == ["revision", "restart"]:
            self.mutations.append("restart")
            self.container = "restarted-current-container"
            self.restart_count += 1
            if self.fault != "same_restart_process":
                self.ticks = "40"
            if self.fault == "restart_balance":
                self.balances["two"]["estimated_remaining_usd"] -= 1
        return None

    def run(self, arguments: list[str]) -> Any:
        assert arguments[:3] == ["rest", "--method", "patch"]
        assert not self.active and self.draining == 0
        assert not any(name.startswith("case-") for name in self.mutations)
        pointer = arguments[arguments.index("--body") + 1]
        assert pointer.startswith("@")
        path = Path(pointer[1:])
        assert (path.parent / "old-writers-absent.json").exists()
        assert (path.parent / "update-consumed.json").exists()
        if self.fault == "patch_uncertain":
            raise TimeoutError("untrusted secret detail")
        self.deployment["properties"]["template"] = copy.deepcopy(
            r.read(path)["properties"]["template"]
        )
        self.env["FOUNDRY_RETRY_ATTEMPTS"] = "0"
        self.active, self.live, self.ticks = True, True, "30"
        self.container = "current-container"
        self.deployment["properties"]["latestReadyRevisionName"] = "current"
        self.mutations.append("patch")
        return None

    def snapshot(self) -> dict[str, Any]:
        result = fixtures.snapshot(self.ticks)
        result["revision"] = self.deployment["properties"]["latestReadyRevisionName"]
        result["generation"] = ["replica", self.container, self.restart_count]
        result["server_command_sha256"] = "synthetic-single-worker-command"
        result["environment_sha256"] = {
            key: hashlib.sha256(value.encode()).hexdigest() for key, value in self.env.items()
        }
        result["request_counters"] = self.requests.copy()
        result["admin"]["config"]["retry_attempts"] = int(
            self.env.get("FOUNDRY_RETRY_ATTEMPTS", "2")
        )
        if self.ticks == "30":
            self.snapshots += 1
            if self.fault == "between_cases" and self.snapshots == 4:
                self.balances["two"]["estimated_remaining_usd"] += 0.01
        result["admin"]["credit_groups"] = {
            name: {"live": {**entry, "active_reservations": 0, "reserved_inflight_usd": 0}}
            for name, entry in self.balances.items()
        }
        if self.fault == "missing_current_counter" and self.ticks == "30":
            del result["admin"]["credit_groups"]["one"]["live"]["debited_usd_total"]
        return dict(result)


@pytest.fixture
def program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, FakeAzure]:  # noqa: PLR0915
    tmp_path.chmod(0o700)
    original_dir, recovery_dir = tmp_path / "original", tmp_path / "recovery"
    original_dir.mkdir(mode=0o700)
    recovery_dir.mkdir(mode=0o700)
    FakeAzure.instances.clear()
    budget = FastBudget()
    test = FakeAzure("synthetic", "rg", "test", budget)
    production = FakeAzure("synthetic", "rg", "production", budget)
    settings = r.h.settings_from(test.env)
    cases = r.h.cases_for(settings, ["one", "two"])
    old_app = test.show()
    old_app["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = []
    image = production.show()["properties"]["template"]["containers"][0]["image"]
    proposal = r.h.template_proposal(old_app, image)
    original = {
        "phase": "G1",
        "subscription": "synthetic",
        "test_rg": "rg",
        "test_app": "test",
        "production_rg": "rg",
        "production_app": "production",
        "test_projection": r.h.projection(old_app),
        "production_projection": r.h.projection(production.show()),
        "original_snapshot": test.snapshot(),
        "original_accounts": copy.deepcopy(test.balances),
        "test_pins": {},
        "production_pins": {},
        "image": image,
        "prior_metadata": "/synthetic-metadata",
        "binding": {"synthetic": True},
        "origin": "https://synthetic.example",
        "executor_ip": "192.0.2.25",
        "cases": cases,
        "program_limit_usd": 1,
        "program_attempts": 16,
        "phase_attempts": 4,
        "phase_reserved_usd": sum(case["reserve_usd"] for case in cases),
        "drain_seconds": 100,
        "dedicated_test_resources": {"synthetic": {"id": "synthetic-dedicated"}},
        "template_proposal_sha256": r.h.digest(proposal),
        "original_min": 0,
        "original_ingress": old_app["properties"]["configuration"]["ingress"],
        "program_ledger": str(original_dir / "program-ledger.json"),
    }
    r.h.create(original_dir / "prepared.json", original)
    packet_sha = r.h.file_hash(original_dir / "prepared.json")
    prior_approval = {
        "verdict": "approved",
        "packet_sha256": packet_sha,
        "independent_reviewer": "synthetic-prior-reviewer",
        "m1_closed": True,
        "liability_reserved_outside_production": True,
        "staged_fenced_completion_accepted": True,
        "liability_disposition": "synthetic disjoint resource",
    }
    r.h.create(original_dir / "approval.json", prior_approval)
    r.h.create(original_dir / "consumed.json", {"packet_sha256": packet_sha})
    r.h.create(
        original_dir / "program-ledger.json",
        {
            "packet_sha256": packet_sha,
            "limit_usd": 1,
            "attempt_limit": 16,
            "phase1_slots": cases,
            "phase1_reserved_usd": original["phase_reserved_usd"],
            "approval_sha256": r.h.digest(prior_approval),
        },
    )
    r.h.create(original_dir / "update-proposal.json", proposal)
    r.h.create(
        original_dir / "update-proposal-binding.json",
        {
            "body_sha256": r.h.digest(proposal),
            "file_sha256": r.h.file_hash(original_dir / "update-proposal.json"),
            "app_id": old_app["id"],
        },
    )
    r.h.create(
        original_dir / "apply-summary.log",
        {"status": "stopped_unverified", "reason": "Fence denial unproved"},
    )
    (original_dir / "execution.lock").touch(mode=0o600)
    monkeypatch.setattr(r, "ORIGINAL_PACKET_SHA", packet_sha)
    monkeypatch.setattr(r, "Azure", FakeAzure)
    monkeypatch.setattr(r, "Budget", FastBudget)
    monkeypatch.setattr(r.h, "source_binding", lambda *_args: {"synthetic": True})
    monkeypatch.setattr(r.h, "resolve", lambda azure, _app: (azure.env.copy(), {}))
    monkeypatch.setattr(
        r.h, "dedicated_resources", lambda *_args: original["dedicated_test_resources"]
    )
    monkeypatch.setattr(r.h, "local_snapshot", lambda azure, _app: azure.snapshot())

    async def public(_origin: str, _path: str, _key: str | None = None) -> tuple[int, bytes]:
        ingress = test.deployment["properties"]["configuration"]["ingress"][
            "ipSecurityRestrictions"
        ]
        return (403, b"") if ingress == r.h.DENY else (200, b'{"ready":true}')

    monkeypatch.setattr(r.h, "get_public_async", public)

    def dispatch(_origin: str, _key: str, case: dict[str, Any], observed: Path) -> dict[str, Any]:
        index = len([name for name in test.mutations if name.startswith("case-")])
        assert (original_dir / f"case-{index}-consumed.json").exists()
        assert (original_dir / r.GUARD).exists()
        test.mutations.append(f"case-{index}")
        if test.fault == "paid_uncertain":
            raise httpx.ReadTimeout("secret detail")
        usage = fixtures.terminal()["usage"]
        debit = r.estimate_response_usage_cost(
            SimpleNamespace(
                body=json.dumps({"usage": usage}).encode(),
                headers={"content-type": "application/json"},
            ),
            case["model"],
            settings.pricing,
        )
        assert debit is not None
        test.balances[case["group"]]["estimated_remaining_usd"] -= debit
        test.balances[case["group"]]["debited_usd_total"] += debit
        test.requests = [f"synthetic_requests_total {index + 1}"]
        result = {"http_status": 200, "completed": True, "usage": usage}
        r.h.create(observed, result)
        return result

    monkeypatch.setattr(r.h, "dispatch", dispatch)
    return original_dir, recovery_dir, test


def prepared(program: tuple[Path, Path, FakeAzure]) -> tuple[Path, Path]:
    original_dir, recovery_dir, _test = program
    r.prepare(
        argparse.Namespace(
            original_dir=original_dir, artifact_dir=recovery_dir, executor_ip="192.0.2.25"
        )
    )
    packet = r.read(recovery_dir / "prepared.json")
    hashes = packet["original_hashes"]
    approval = {
        "verdict": "approved",
        "packet_sha256": r.h.file_hash(recovery_dir / "prepared.json"),
        "original_prepared_sha256": hashes["prepared.json"],
        "original_consumed_sha256": hashes["consumed.json"],
        "original_ledger_sha256": hashes["program-ledger.json"],
        "independent_reviewer": "synthetic-other-session",
        "recovery_accepted": True,
        "unused_slots_verified": True,
        "staged_fenced_completion_accepted": True,
        "cold_rebase_accepted": True,
        "original_executor_exited": True,
    }
    r.h.create(recovery_dir / "approval.json", approval)
    return recovery_dir, recovery_dir / "approval.json"


@pytest.mark.parametrize("cold", [False, True])
def test_complete_recovery_preserves_original_budget_and_advances_only_original_slots(
    program: tuple[Path, Path, FakeAzure], cold: bool
) -> None:
    original_dir, recovery_dir, test = program
    original_hashes = {name: r.h.file_hash(original_dir / name) for name in r.BASE_FILES}
    test.live = not cold
    _, approval = prepared(program)
    assert test.mutations == [] and not (original_dir / r.GUARD).exists()
    packet = r.read(recovery_dir / "prepared.json")
    assert (packet["current_snapshot"] is None) == cold
    r.apply(argparse.Namespace(artifact_dir=recovery_dir, approval=approval))
    r.immutable(original_dir, original_hashes)
    assert len([name for name in test.mutations if name.startswith("case-")]) == 4
    assert test.mutations.count("allow") == (2 if cold else 1)
    assert test.mutations.count("deny") == (2 if cold else 1)
    assert test.mutations.count("patch") == test.mutations.count("restart") == 1
    assert FakeAzure.instances["production"].mutations == []
    result = r.read(original_dir / "results.json")
    assert (
        result["g1_four_calls_and_restart"] == "passed" and not result["original_apply_completed"]
    )
    assert (
        result["recovery_link"]["original_ledger_sha256"] == original_hashes["program-ledger.json"]
    )
    assert r.read(recovery_dir / "results.json")["original_result_sha256"] == r.h.file_hash(
        original_dir / "results.json"
    )
    if cold:
        assert not r.read(recovery_dir / "cold-old-baseline.json")[
            "current_image_restart_acceptance"
        ]
    with pytest.raises(r.h.RefusalError, match="already consumed"):
        r.apply(argparse.Namespace(artifact_dir=recovery_dir, approval=approval))


@pytest.mark.parametrize(
    "fault",
    [
        "cold_balance",
        "paid_uncertain",
        "patch_uncertain",
        "between_cases",
        "missing_current_counter",
        "same_restart_process",
        "restart_balance",
    ],
)
def test_failure_stops_without_replay_refund_or_later_slots(
    program: tuple[Path, Path, FakeAzure], fault: str
) -> None:
    original_dir, recovery_dir, test = program
    if fault == "cold_balance":
        test.live = False
    _, approval = prepared(program)
    test.fault = fault
    with pytest.raises((r.h.RefusalError, httpx.ReadTimeout, TimeoutError)):
        r.apply(argparse.Namespace(artifact_dir=recovery_dir, approval=approval))
    assert (original_dir / r.GUARD).exists()
    assert not (original_dir / "results.json").exists()
    assert r.read(original_dir / "program-ledger.json")["phase1_reserved_usd"] == pytest.approx(
        0.01792
    )
    if fault in {"cold_balance", "patch_uncertain", "missing_current_counter"}:
        assert not (original_dir / "case-0-consumed.json").exists()
    if fault in {"paid_uncertain", "between_cases"}:
        assert (original_dir / "case-0-consumed.json").exists()
        assert not (original_dir / "case-1-consumed.json").exists()
    if fault == "cold_balance":
        assert "stop" not in test.mutations


@pytest.mark.parametrize(
    "marker",
    [
        "case-0-consumed.json",
        "case-3-observed.json",
        "old-drained.json",
        "stop-consumed.json",
        "update-consumed.json",
        "restart-consumed.json",
        "unknown-journal.json",
        r.GUARD,
    ],
)
def test_any_started_or_ambiguous_original_history_refuses_prepare(
    program: tuple[Path, Path, FakeAzure], marker: str
) -> None:
    original_dir, recovery_dir, test = program
    r.h.create(original_dir / marker, {})
    with pytest.raises(r.h.RefusalError):
        r.prepare(
            argparse.Namespace(
                original_dir=original_dir, artifact_dir=recovery_dir, executor_ip="192.0.2.25"
            )
        )
    assert not (recovery_dir / "prepared.json").exists() and test.mutations == []


@pytest.mark.parametrize(
    "change", ["approval", "ledger", "failure", "proposal", "executor", "process"]
)
def test_binding_and_private_approval_refuse_before_consumption(
    program: tuple[Path, Path, FakeAzure], change: str
) -> None:
    original_dir, recovery_dir, test = program
    _, approval = prepared(program)
    if change == "approval":
        value = r.read(approval)
        value["unused_slots_verified"] = False
        approval.write_text(json.dumps(value))
    elif change == "executor":
        packet = r.read(recovery_dir / "prepared.json")
        packet["executor_ip"] = "192.0.2.99"
        (recovery_dir / "prepared.json").write_text(json.dumps(packet))
    elif change == "process":
        test.ticks = "different"
    else:
        filename = {
            "ledger": "program-ledger.json",
            "failure": "apply-summary.log",
            "proposal": "update-proposal.json",
        }[change]
        (original_dir / filename).write_text("{}")
    with pytest.raises((r.h.RefusalError, KeyError)):
        r.apply(argparse.Namespace(artifact_dir=recovery_dir, approval=approval))
    assert not (original_dir / r.GUARD).exists() and test.mutations == []


def test_canonical_lock_blocks_other_executor_and_guard_blocks_other_directory(
    program: tuple[Path, Path, FakeAzure],
) -> None:
    original_dir, recovery_dir, test = program
    with r.lock(original_dir / "execution.lock", existing=True), pytest.raises(BlockingIOError):
        r.prepare(
            argparse.Namespace(
                original_dir=original_dir, artifact_dir=recovery_dir, executor_ip="192.0.2.25"
            )
        )
    r.h.create(original_dir / r.GUARD, {"other_recovery": True})
    other = recovery_dir.parent / "other"
    other.mkdir(mode=0o700)
    with pytest.raises(r.h.RefusalError, match="already consumed"):
        r.prepare(
            argparse.Namespace(
                original_dir=original_dir, artifact_dir=other, executor_ip="192.0.2.25"
            )
        )
    assert test.mutations == []


def test_permission_and_symlink_guards(program: tuple[Path, Path, FakeAzure]) -> None:
    original_dir, recovery_dir, _test = program
    (original_dir / "approval.json").chmod(0o644)
    with pytest.raises(r.h.RefusalError, match="Owner-only"):
        r.history(original_dir)
    link = recovery_dir / "link"
    link.symlink_to(original_dir, target_is_directory=True)
    with pytest.raises(r.h.RefusalError):
        r.directory(link)


def test_total_public_wait_handles_delay_and_trickle_without_paid_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget = FastBudget()
    statuses = iter([200, 503, 403])
    calls = 0

    async def observed(_origin: str, _path: str) -> tuple[int, bytes]:
        nonlocal calls
        calls += 1
        return next(statuses), b""

    monkeypatch.setattr(r.h, "get_public_async", observed)
    # Keep polling bounded but quick without replacing the event loop clock.
    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds: float) -> None:
        await original_sleep(0)

    monkeypatch.setattr(r.asyncio, "sleep", fast_sleep)
    r.public_wait(budget, "https://synthetic.example", 403)
    assert calls == 3
    original_client = httpx.AsyncClient

    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            while True:
                await original_sleep(0.005)
                yield b" "

    monkeypatch.undo()
    monkeypatch.setattr(r, "PUBLIC_SECONDS", 0.04)
    monkeypatch.setattr(
        r.h.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, stream=Trickle())),
            **kwargs,
        ),
    )
    with pytest.raises(TimeoutError):
        r.public_wait(budget, "https://synthetic.example", 200)


def test_worker_deadline_noop_restart_and_absence_count_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget = FastBudget()
    writer = {
        "name": "replica",
        "properties": {
            "containers": [
                {"ready": True, "started": True, "containerId": "old-container", "restartCount": 0}
            ]
        },
    }
    azure = SimpleNamespace(writers=lambda **_kwargs: [writer])
    clock = iter([0, 0, 0, 181])
    monkeypatch.setattr(r.time, "monotonic", lambda: next(clock))
    with pytest.raises(r.h.RefusalError, match="transition deadline"):
        r.workers(budget, azure, replacement={"generation": ["replica", "old-container", 0]})


def test_real_budget_total_alarm_and_cleanup_reserve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r, "CLEANUP_SECONDS", 0.01)
    budget = r.Budget()
    previous = signal.getsignal(signal.SIGALRM)
    with pytest.raises(TimeoutError):
        budget.call(time.sleep, 0.1, limit=0.03)
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0
    budget.end = time.monotonic() - 1
    with pytest.raises(r.h.RefusalError):
        budget.pause(100)


def test_deadline_azure_command_redacts_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    budget = r.Budget()

    class Process:
        returncode = 1

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            assert 0 < timeout <= 60
            return b"credential", b"credential"

        def poll(self) -> int:
            return self.returncode

    monkeypatch.setattr(r.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    azure = r.Azure("synthetic", "rg", "test", budget)
    with pytest.raises(r.h.RefusalError) as error:
        azure.show()
    assert "credential" not in str(error.value)


def test_main_redacts_native_errors_and_restores_logging(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["recovery", "apply", "--artifact-dir", "/synthetic", "--approval", "/synthetic/approval"],
    )
    monkeypatch.setattr(r, "apply", lambda _: (_ for _ in ()).throw(TimeoutError("credential")))
    assert r.main() == 2
    assert "credential" not in capsys.readouterr().out


def test_current_executor_ip_is_freshly_bound_without_rewriting_original(
    program: tuple[Path, Path, FakeAzure],
) -> None:
    original_dir, recovery_dir, _test = program
    prior = r.h.file_hash(original_dir / "prepared.json")
    r.prepare(
        argparse.Namespace(
            original_dir=original_dir, artifact_dir=recovery_dir, executor_ip="192.0.2.99"
        )
    )
    packet = r.read(recovery_dir / "prepared.json")
    assert packet["executor_ip"] == "192.0.2.99" and packet["original_executor_ip"] == "192.0.2.25"
    assert r.h.file_hash(original_dir / "prepared.json") == prior


@pytest.mark.parametrize("invalid", ["overrun", "usage_type"])
def test_original_tiny_slot_charge_guard_retains_consumption(
    program: tuple[Path, Path, FakeAzure], monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    original_dir, recovery_dir, _test = program
    _, approval = prepared(program)
    original_dispatch = r.h.dispatch

    def invalid_dispatch(*args: Any) -> dict[str, Any]:
        result = dict(original_dispatch(*args))
        result["usage"]["output_tokens"] = 1000 if invalid == "overrun" else "invalid"
        return result

    monkeypatch.setattr(r.h, "dispatch", invalid_dispatch)
    with pytest.raises(
        r.h.RefusalError, match="Invalid terminal usage|Usage exceeds reserved bounds"
    ):
        r.apply(argparse.Namespace(artifact_dir=recovery_dir, approval=approval))
    assert (original_dir / "case-0-consumed.json").exists()
    assert not (original_dir / "case-1-consumed.json").exists()
    assert not (original_dir / "case-0-passed.json").exists()


def test_frozen_helper_drift_refuses_readonly_prepare(
    program: tuple[Path, Path, FakeAzure], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_dir, recovery_dir, test = program
    monkeypatch.setattr(r, "HELPER_SHA", "unreviewed")
    with pytest.raises(r.h.RefusalError, match="Frozen G1 helper drift"):
        r.prepare(
            argparse.Namespace(
                original_dir=original_dir, artifact_dir=recovery_dir, executor_ip="192.0.2.25"
            )
        )
    assert not (recovery_dir / "prepared.json").exists() and not test.mutations


def test_original_budget_cannot_be_replenished_or_replaced(
    program: tuple[Path, Path, FakeAzure],
) -> None:
    original_dir, recovery_dir, test = program
    path = original_dir / "program-ledger.json"
    ledger = r.read(path)
    ledger["limit_usd"] = 2
    path.write_text(json.dumps(ledger))
    with pytest.raises(r.h.RefusalError, match="Original allocation"):
        r.prepare(
            argparse.Namespace(
                original_dir=original_dir, artifact_dir=recovery_dir, executor_ip="192.0.2.25"
            )
        )
    assert not (recovery_dir / "prepared.json").exists() and not test.mutations


def test_cli_timeout_kills_only_owned_group_with_bounded_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget = r.Budget()
    killed: list[tuple[int, int]] = []

    class Process:
        pid = 12345
        returncode: int | None = None
        calls = 0

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            self.calls += 1
            if self.calls == 1:
                assert 0 < timeout <= 60
                raise r.subprocess.TimeoutExpired("az", timeout)
            assert 0 < timeout <= 3
            self.returncode = -9
            return b"", b""

        def poll(self) -> int | None:
            return self.returncode

    process = Process()
    monkeypatch.setattr(r.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(r.os, "killpg", lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(r.subprocess.TimeoutExpired):
        r.Azure("synthetic", "rg", "test", budget).show()
    assert killed == [(12345, signal.SIGKILL)] and process.calls == 2
