"""Single-use recovery of the known fenced G1 failure; never replay original apply."""

from __future__ import annotations

import argparse
import asyncio
import copy
import fcntl
import ipaddress
import json
import logging
import os
import signal
import subprocess
import time
import uuid
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import httpx
import table_production_acceptance as h

from foundry_router.credit import estimate_response_usage_cost

if TYPE_CHECKING:
    from collections.abc import Iterator

Json = dict[str, Any]
HELPER_SHA = "701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922"
HELPER_TEST_SHA = "04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b"
ORIGINAL_PACKET_SHA = "721fc9be3e5a862741e3c71eaa327dc8c0e153c789ee0a17029af4ee13a9e8de"
ROOT = Path(__file__).resolve().parents[2]
BASE_FILES = {
    "prepared.json",
    "approval.json",
    "consumed.json",
    "program-ledger.json",
    "update-proposal.json",
    "update-proposal-binding.json",
    "apply-summary.log",
    "execution.lock",
}
GUARD = "recovery-consumed.json"
PROGRAM_LOCK = "recovery-program.lock"
OVERALL_SECONDS = 1800
PUBLIC_SECONDS = 120
WORKER_SECONDS = 180
CLEANUP_SECONDS = 8  # Frozen PTY helper has at most two three-second cleanup waits.
DRAIN_SECONDS = 100
OWNER_FILE_MODE = 0o600


def directory(path: Path) -> None:
    h.private_directory(path)
    h.require(path == path.resolve(), "Canonical nonsymlink artifact directory required")


def private_file(path: Path) -> None:
    directory(path.parent)
    h.require(not path.is_symlink() and path.is_file(), "Owned nonsymlink artifact required")
    stat = path.stat()
    h.require(
        stat.st_uid == os.getuid() and stat.st_mode & 0o777 == OWNER_FILE_MODE,
        "Owner-only artifact required",
    )
    h.require(stat.st_size <= h.MAX_BYTES, "Artifact capacity exceeded")


def read(path: Path) -> Json:
    private_file(path)
    return h.read_json(path)


@contextmanager
def lock(path: Path, *, existing: bool = False) -> Iterator[None]:
    directory(path.parent)
    if existing:
        private_file(path)
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | (0 if existing else os.O_CREAT), OWNER_FILE_MODE)
    with os.fdopen(fd, "r+b") as handle:
        private_file(path)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Budget:
    """Main-thread total deadlines, reserving frozen-helper subprocess cleanup time."""

    def __init__(self) -> None:
        self.end = time.monotonic() + OVERALL_SECONDS
        self.active_end = self.end
        self.active_call = False

    def remaining(self, limit: float) -> float:
        value = min(limit, self.end - time.monotonic(), self.active_end - time.monotonic())
        h.require(value > CLEANUP_SECONDS, "Recovery deadline exhausted")
        return value

    def call(self, function: Any, *args: Any, limit: float = PUBLIC_SECONDS, **kwargs: Any) -> Any:
        start = time.monotonic()
        end = start + self.remaining(limit)
        prior_end = self.active_end
        prior_active = self.active_call
        prior_handler = signal.getsignal(signal.SIGALRM)
        prior_timer = signal.getitimer(signal.ITIMER_REAL)
        h.require(prior_timer[0] == 0, "Conflicting process deadline timer")
        self.active_end = end
        self.active_call = True

        def expired(_signal: int, _frame: Any) -> None:
            raise TimeoutError("Recovery operation deadline")

        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, end - start - CLEANUP_SECONDS))
        try:
            return function(*args, **kwargs)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, prior_handler)
            self.active_end = prior_end
            self.active_call = prior_active

    def pause(self, seconds: float) -> None:
        h.require(
            self.remaining(seconds + CLEANUP_SECONDS + 1) >= seconds + CLEANUP_SECONDS,
            "Insufficient recovery time for drain or observation",
        )
        time.sleep(seconds)


class Azure(h.Azure):
    def __init__(self, subscription: str, resource_group: str, app: str, budget: Budget):
        super().__init__(subscription, resource_group, app)
        self.budget = budget

    def run(self, arguments: list[str]) -> Any:
        if not self.budget.active_call:
            return self.budget.call(self._run, arguments, limit=h.TIMEOUT + CLEANUP_SECONDS)
        return self._run(arguments)

    def _run(self, arguments: list[str]) -> Any:
        timeout = self.budget.remaining(h.TIMEOUT + CLEANUP_SECONDS) - CLEANUP_SECONDS
        process = subprocess.Popen(
            ["az", *arguments, "--subscription", self.subscription, "-o", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, _stderr = process.communicate(
                timeout=min(
                    timeout, self.budget.remaining(h.TIMEOUT + CLEANUP_SECONDS) - CLEANUP_SECONDS
                )
            )
        except (TimeoutError, subprocess.TimeoutExpired):
            timed_out = True
            raise
        finally:
            if timed_out or process.poll() is None:
                # Missing owned group means the CLI already exited, not a mutation retry.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                remaining = min(self.budget.end, self.budget.active_end) - time.monotonic()
                h.require(remaining > 0, "Azure CLI cleanup deadline exhausted")
                process.communicate(timeout=min(3, remaining))
        h.require(process.returncode == 0, "Azure command unsuccessful; raw output withheld")
        h.require(len(stdout) <= h.MAX_BYTES, "Azure metadata capacity exceeded")
        return json.loads(stdout or b"null")


async def public_wait_async(origin: str, expected: int, end: float) -> None:
    async with asyncio.timeout_at(end):
        while True:
            try:
                status, body = await h.get_public_async(origin, "/health/ready")
            except (httpx.TimeoutException, TimeoutError):
                # Read-only propagation/startup observation, never inference or mutation retry.
                await asyncio.sleep(1)
                continue
            if status == expected:
                if expected == h.HTTP_OK:
                    data = json.loads(body)
                    h.require(
                        isinstance(data, dict) and data.get("ready") is True,
                        "Recovery public readiness incomplete",
                    )
                return
            h.require(
                status in {h.HTTP_OK, h.HTTP_DENIED, 502, 503, 504},
                "Unexpected recovery public status",
            )
            await asyncio.sleep(1)


def public_wait(budget: Budget, origin: str, expected: int) -> None:
    end = min(budget.end, time.monotonic() + PUBLIC_SECONDS)
    asyncio.run(public_wait_async(origin, expected, end))


def workers(
    budget: Budget, azure: Azure, *, absent: bool = False, replacement: Json | None = None
) -> None:
    end = min(budget.end, time.monotonic() + WORKER_SECONDS)
    while time.monotonic() + CLEANUP_SECONDS < end:
        found = budget.call(
            azure.writers, allow_none=True, allow_draining=absent, limit=end - time.monotonic()
        )
        if absent and not found:
            return
        if not absent and found:
            containers = found[0]["properties"]["containers"]
            if len(containers) == 1 and containers[0].get("ready") and containers[0].get("started"):
                generation = h.generation(found[0])
                if replacement is None:
                    return
                before = replacement["generation"]
                if generation[:2] != before[:2] or generation[2] > before[2]:
                    return
        budget.pause(1)
    raise h.RefusalError("Recovery worker transition deadline")


def shape(projected: Json) -> Json:
    return {
        "id": projected["id"],
        "identity": projected.get("identity"),
        "location": projected.get("location"),
        "properties": {
            key: projected["properties"].get(key)
            for key in ("configuration", "template", "environmentId", "managedEnvironmentId")
        },
    }


def immutable(original_dir: Path, hashes: Json) -> None:
    for name, expected in hashes.items():
        private_file(original_dir / name)
        h.require(h.file_hash(original_dir / name) == expected, "Original immutable history drift")


def history(original_dir: Path) -> tuple[Json, Json]:
    directory(original_dir)
    h.require(not (original_dir / GUARD).exists(), "Original program recovery already consumed")
    entries = {path.name for path in original_dir.iterdir()}
    h.require(
        not any(
            name.startswith(
                (
                    "case-",
                    "old-drained",
                    "stop-",
                    "update-consumed",
                    "restart-",
                    "results",
                    "recovery-",
                )
            )
            and name != PROGRAM_LOCK
            for name in entries
        ),
        "Original slots or operations are started or ambiguous",
    )
    h.require(
        entries >= BASE_FILES and entries <= BASE_FILES | {PROGRAM_LOCK},
        "Conflicting original artifact or journal",
    )
    hashes = {}
    for name in BASE_FILES:
        private_file(original_dir / name)
        hashes[name] = h.file_hash(original_dir / name)
    h.require(
        hashes["prepared.json"] == ORIGINAL_PACKET_SHA, "Known failed original packet required"
    )
    original = read(original_dir / "prepared.json")
    h.validate_packet_budget(original)
    h.approved(original_dir / "prepared.json", original_dir / "approval.json")
    h.require(
        read(original_dir / "consumed.json")["packet_sha256"] == hashes["prepared.json"],
        "Original outer consumption missing",
    )
    failed = read(original_dir / "apply-summary.log")
    h.require(
        failed.get("status") == "stopped_unverified"
        and failed.get("reason") == "Fence denial unproved",
        "Known fence-only failure evidence required",
    )
    ledger = read(original_dir / "program-ledger.json")
    h.require(
        Path(original["program_ledger"]) == original_dir / "program-ledger.json",
        "Canonical original program location required",
    )
    h.require(
        ledger["packet_sha256"] == hashes["prepared.json"]
        and ledger["limit_usd"] == 1
        and ledger["attempt_limit"] == h.PROGRAM_ATTEMPTS
        and ledger["phase1_slots"] == original["cases"]
        and ledger["phase1_reserved_usd"] == original["phase_reserved_usd"]
        and ledger["approval_sha256"] == h.digest(read(original_dir / "approval.json")),
        "Original allocation or unused slot identity mismatch",
    )
    proposal = read(original_dir / "update-proposal.json")
    binding = read(original_dir / "update-proposal-binding.json")
    h.require(
        binding["file_sha256"] == hashes["update-proposal.json"]
        and binding["body_sha256"] == h.digest(proposal) == original["template_proposal_sha256"]
        and binding["app_id"] == original["test_projection"]["id"],
        "Original proposal binding drift",
    )
    h.require(
        len(original["original_accounts"]) == h.MODEL_COUNT
        and original["drain_seconds"] == DRAIN_SECONDS,
        "Exact two-account/drain scope required",
    )
    return original, hashes


def release_binding(original: Json) -> Json:
    h.require(h.file_hash(Path(h.__file__)) == HELPER_SHA, "Frozen G1 helper drift")
    h.require(
        h.file_hash(ROOT / "tests/unit/test_table_production_acceptance.py") == HELPER_TEST_SHA,
        "Frozen G1 tests drift",
    )
    source = h.source_binding(Path(original["prior_metadata"]), original["image"])
    h.require(source == original["binding"], "Original runtime/image provenance drift")
    return {
        "original_binding": source,
        "runner_sha256": h.file_hash(Path(__file__)),
        "tests_sha256": h.file_hash(
            ROOT / "tests/unit/test_table_production_acceptance_recovery.py"
        ),
    }


def discovery(budget: Budget, original: Json) -> tuple[Azure, Json, dict[str, str], Json]:
    azure = Azure(original["subscription"], original["test_rg"], original["test_app"], budget)
    production = Azure(
        original["subscription"], original["production_rg"], original["production_app"], budget
    )
    app, prod = azure.show(), production.show()
    expected = copy.deepcopy(original["test_projection"])
    expected["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = h.DENY
    h.require(shape(h.projection(app)) == shape(expected), "Recovery old-app configuration drift")
    h.require(h.projection(prod) == original["production_projection"], "Read-only production drift")
    values, pins = budget.call(h.resolve, azure, app)
    prod_values, prod_pins = budget.call(h.resolve, production, prod)
    h.require(
        pins == original["test_pins"] and prod_pins == original["production_pins"],
        "Recovery secret pin drift",
    )
    settings = h.settings_from(values)
    h.validate_modes(app, settings)
    h.require(
        app["properties"]["template"]["scale"]["minReplicas"] == 0, "Known old Table/min0 required"
    )
    h.require(
        h.cases_for(settings, list(dict.fromkeys(case["model"] for case in original["cases"])))
        == original["cases"],
        "Original model/pricing/slot drift",
    )
    resources = budget.call(
        h.dedicated_resources, azure, original["cases"], h.settings_from(prod_values)
    )
    h.require(resources == original["dedicated_test_resources"], "Dedicated test resource drift")
    h.require(
        h.digest(h.template_proposal(app, original["image"]))
        == original["template_proposal_sha256"],
        "Bound original template proposal drift",
    )
    return azure, app, values, pins


def snapshot(budget: Budget, azure: Azure, values: dict[str, str]) -> Json:
    result = budget.call(h.local_snapshot, azure, azure.show())
    h.verify_environment(result, values)
    return dict(result)


def old_baseline(current: Json, original: Json, *, cold: bool) -> None:
    h.unchanged(h.accounts(current["admin"], legacy=True), original["original_accounts"])
    h.require(
        current["server_command_sha256"] == original["original_snapshot"]["server_command_sha256"],
        "Old worker launch drift",
    )
    if not cold:
        h.require(
            h.process_identity(current) == h.process_identity(original["original_snapshot"]),
            "Existing old worker identity drift",
        )
        h.require(
            current["request_counters"] == original["original_snapshot"]["request_counters"],
            "Unreserved old-worker requests observed",
        )
    else:
        h.require(
            all(float(line.rsplit(" ", 1)[1]) == 0 for line in current["request_counters"]),
            "Cold old-worker baseline has unreserved requests",
        )


def prepare(args: argparse.Namespace) -> None:
    directory(args.artifact_dir)
    h.require(not any(args.artifact_dir.iterdir()), "Fresh recovery directory required")
    h.require(args.artifact_dir != args.original_dir, "Separate recovery identity required")
    budget = Budget()
    with lock(args.original_dir / "execution.lock", existing=True):
        original, hashes = history(args.original_dir)
        binding = release_binding(original)
        ip = str(ipaddress.IPv4Address(args.executor_ip))
        azure, app, values, _pins = discovery(budget, original)
        public_wait(budget, original["origin"], h.HTTP_DENIED)
        found = azure.writers(allow_none=True)
        current = snapshot(budget, azure, values) if found else None
        if current is not None:
            old_baseline(current, original, cold=False)
        immutable(args.original_dir, hashes)
        h.create(
            args.artifact_dir / "prepared.json",
            {
                "schema": "g1-fence-recovery-v1",
                "recovery_id": uuid.uuid4().hex,
                "original_dir": str(args.original_dir),
                "original_hashes": hashes,
                "binding": binding,
                "current_projection": shape(h.projection(app)),
                "current_snapshot": current,
                "cold_rebase_permitted": True,
                "executor_ip": ip,
                "original_executor_ip": original["executor_ip"],
                "original_slots": original["cases"],
                "original_ledger_sha256": hashes["program-ledger.json"],
                "original_ingress_pointer": "original prepared.json.original_ingress",
            },
        )
    print(
        json.dumps(
            {
                "status": "recovery_prepared_not_approved",
                "packet_sha256": h.file_hash(args.artifact_dir / "prepared.json"),
                "cold_baseline_deferred": current is None,
            }
        )
    )


def approval(path: Path, prepared: Path, packet: Json) -> Json:
    value = read(path)
    keys = {
        "verdict",
        "packet_sha256",
        "original_prepared_sha256",
        "original_consumed_sha256",
        "original_ledger_sha256",
        "independent_reviewer",
        "recovery_accepted",
        "unused_slots_verified",
        "staged_fenced_completion_accepted",
        "cold_rebase_accepted",
        "original_executor_exited",
    }
    h.require(
        set(value) == keys
        and value["verdict"] == "approved"
        and value["packet_sha256"] == h.file_hash(prepared)
        and bool(value["independent_reviewer"]),
        "Fresh independent exact recovery approval required",
    )
    for name in (
        "recovery_accepted",
        "unused_slots_verified",
        "staged_fenced_completion_accepted",
        "cold_rebase_accepted",
        "original_executor_exited",
    ):
        h.require(value[name] is True, "Recovery disposition or unused ownership not approved")
    for key, name in (
        ("original_prepared_sha256", "prepared.json"),
        ("original_consumed_sha256", "consumed.json"),
        ("original_ledger_sha256", "program-ledger.json"),
    ):
        h.require(
            value[key] == packet["original_hashes"][name], "Recovery prior hash-chain mismatch"
        )
    return value


def apply(args: argparse.Namespace) -> None:  # noqa: PLR0915 -- bounded single-use recovery sequence
    directory(args.artifact_dir)
    prepared_path = args.artifact_dir / "prepared.json"
    packet = read(prepared_path)
    h.require(packet["schema"] == "g1-fence-recovery-v1", "Recovery schema mismatch")
    verdict = approval(args.approval, prepared_path, packet)
    original_dir = Path(packet["original_dir"])
    budget = Budget()
    with ExitStack() as stack:
        stack.enter_context(lock(original_dir / "execution.lock", existing=True))
        stack.enter_context(lock(original_dir / PROGRAM_LOCK))
        stack.enter_context(lock(args.artifact_dir / "execution.lock"))
        original, hashes = history(original_dir)
        h.require(
            hashes == packet["original_hashes"] and release_binding(original) == packet["binding"],
            "Recovery executable or original binding drift",
        )
        h.require(packet["original_slots"] == original["cases"], "Recovery slot identity drift")
        h.require(
            str(ipaddress.IPv4Address(packet["executor_ip"])) == packet["executor_ip"]
            and packet["original_executor_ip"] == original["executor_ip"]
            and packet["cold_rebase_permitted"] is True,
            "Recovery executor or cold branch binding drift",
        )
        azure, app, values, pins = discovery(budget, original)
        public_wait(budget, original["origin"], h.HTTP_DENIED)
        found = azure.writers(allow_none=True)
        baseline = snapshot(budget, azure, values) if found else None
        if baseline is not None:
            old_baseline(baseline, original, cold=False)
            if packet["current_snapshot"] is not None:
                h.require(
                    h.process_identity(baseline) == h.process_identity(packet["current_snapshot"]),
                    "Prepared warm old-worker identity drift",
                )
        link = {
            "recovery_id": packet["recovery_id"],
            "packet_sha256": h.file_hash(prepared_path),
            "original_prepared_sha256": hashes["prepared.json"],
            "original_consumed_sha256": hashes["consumed.json"],
            "original_failure_sha256": hashes["apply-summary.log"],
            "original_ledger_sha256": hashes["program-ledger.json"],
            "approval_sha256": h.digest(verdict),
            "recovery_dir": str(args.artifact_dir),
        }

        def record(name: str, data: Json, *, original_location: bool = False) -> None:
            budget.call(
                h.create,
                (original_dir if original_location else args.artifact_dir) / name,
                {**data, "recovery_link": link},
                limit=15,
            )

        record(
            GUARD, {"unused_slot_indices": list(range(h.PHASE_ATTEMPTS))}, original_location=True
        )
        record("consumed.json", {"cold_old_worker": baseline is None})
        allow = [
            {
                "name": "g1-executor",
                "ipAddressRange": packet["executor_ip"] + "/32",
                "action": "Allow",
            }
        ]

        def ingress(stage: str, restrictions: list[Json], expected: int) -> None:
            record(stage + "-consumed.json", {"restrictions_sha256": h.digest(restrictions)})
            budget.call(azure.ingress, app["id"], restrictions)
            public_wait(budget, original["origin"], expected)

        if baseline is None:
            ingress("cold-warm-allow", allow, h.HTTP_OK)
            workers(budget, azure)
            warmed = azure.show()
            expected_shape = copy.deepcopy(packet["current_projection"])
            expected_shape["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = (
                allow
            )
            h.require(
                shape(h.projection(warmed)) == expected_shape, "Cold warm old configuration drift"
            )
            new_values, new_pins = budget.call(h.resolve, azure, warmed)
            h.require(new_values == values and new_pins == pins, "Cold warm pinned settings drift")
            baseline = snapshot(budget, azure, values)
            old_baseline(baseline, original, cold=True)
            record(
                "cold-old-baseline.json",
                {"snapshot": baseline, "current_image_restart_acceptance": False},
            )
            ingress("cold-old-deny", h.DENY, h.HTTP_DENIED)
        assert baseline is not None
        fenced = snapshot(budget, azure, values)
        h.require(
            h.process_identity(fenced) == h.process_identity(baseline), "Old fence process changed"
        )
        h.unchanged(h.accounts(fenced["admin"], legacy=True), original["original_accounts"])
        budget.pause(DRAIN_SECONDS)
        drained = snapshot(budget, azure, values)
        h.require(
            h.process_identity(drained) == h.process_identity(baseline), "Old drain process changed"
        )
        h.unchanged(h.accounts(drained["admin"], legacy=True), original["original_accounts"])
        h.require(
            drained["request_counters"] == baseline["request_counters"], "Old drain request drift"
        )
        record("old-drained.json", drained, original_location=True)
        record("stop-consumed.json", {"revision": baseline["revision"]}, original_location=True)
        budget.call(
            azure.app_command, ["revision", "deactivate", "--revision", baseline["revision"]]
        )
        workers(budget, azure, absent=True)
        record("old-writers-absent.json", {"verified": True}, original_location=True)
        h.require(
            azure.show()["properties"]["template"] == app["properties"]["template"],
            "Old template drift before promotion",
        )
        immutable(original_dir, hashes)
        h.verify_template_proposal(
            app, read(original_dir / "update-proposal.json"), original["image"]
        )
        current_pins = budget.call(h.resolve, azure, azure.show())[1]
        h.require(current_pins == pins, "Promotion secret drift")
        record(
            "update-consumed.json",
            {"proposal_sha256": hashes["update-proposal.json"]},
            original_location=True,
        )
        budget.call(
            azure.run,
            [
                "rest",
                "--method",
                "patch",
                "--url",
                app["id"] + "?api-version=2024-03-01",
                "--body",
                "@" + str(original_dir / "update-proposal.json"),
            ],
        )
        workers(budget, azure)
        successor = azure.show()
        h.verify_successor(app, successor, original["image"])
        current_values, current_pins = budget.call(h.resolve, azure, successor)
        h.require(
            current_values == {**values, "FOUNDRY_RETRY_ATTEMPTS": "0"} and current_pins == pins,
            "Current successor configuration drift",
        )
        h.validate_modes(successor, h.settings_from(current_values))
        current = snapshot(budget, azure, current_values)
        last_accounts = h.accounts(current["admin"])
        h.unchanged(last_accounts, original["original_accounts"])
        h.require(current["admin"]["config"]["retry_attempts"] == 0, "Current retries not zero")
        record("successor-baseline.json", current, original_location=True)
        ingress("successor-allow", allow, h.HTTP_OK)
        settings = h.settings_from(current_values)
        for index, case in enumerate(original["cases"]):
            immutable(original_dir, hashes)
            before = snapshot(budget, azure, current_values)
            h.require(
                h.process_identity(before) == h.process_identity(current),
                "Paid recovery worker changed",
            )
            h.unchanged(last_accounts, h.accounts(before["admin"]))
            record(
                f"case-{index}-consumed.json",
                {"reserve_usd": case["reserve_usd"], "attempts": 1},
                original_location=True,
            )
            record(f"case-{index}-ownership.json", {"original_slot_index": index})
            result = budget.call(
                h.dispatch,
                original["origin"],
                h.credential(current_values, "FOUNDRY_CLIENT_API_KEYS_JSON"),
                case,
                original_dir / f"case-{index}-observed.json",
            )
            h.require(
                result["http_status"] == h.HTTP_OK and result["completed"] is True,
                "Recovery terminal observation invalid",
            )
            usage = h.response_usage({"status": "completed", "usage": result["usage"]})
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
                "Recovery debit exceeds original slot",
            )
            assert debit is not None
            after = snapshot(budget, azure, current_values)
            h.require(
                h.process_identity(after) == h.process_identity(current),
                "Settlement recovery worker changed",
            )
            after_accounts = h.accounts(after["admin"])
            h.verify_debit(last_accounts, after_accounts, case["group"], debit)
            last_accounts = after_accounts
            record(
                f"case-{index}-passed.json",
                {"debit_usd": debit, "accounts": last_accounts},
                original_location=True,
            )
        ingress("final-deny", h.DENY, h.HTTP_DENIED)
        budget.pause(DRAIN_SECONDS)
        final = snapshot(budget, azure, current_values)
        h.require(
            h.process_identity(final) == h.process_identity(current),
            "Final recovery worker changed",
        )
        h.unchanged(h.accounts(final["admin"]), last_accounts)
        h.require(
            final["request_counters"] == after["request_counters"], "Final recovery request drift"
        )
        record("restart-consumed.json", final, original_location=True)
        budget.call(azure.app_command, ["revision", "restart", "--revision", final["revision"]])
        workers(budget, azure, replacement=final)
        restarted = snapshot(budget, azure, current_values)
        h.verify_successor(app, azure.show(), original["image"])
        h.require(
            restarted["revision"] == final["revision"], "Restart changed the approved revision"
        )
        h.require(
            h.process_identity(restarted) != h.process_identity(final),
            "No actual recovery process replacement",
        )
        h.unchanged(h.accounts(restarted["admin"]), last_accounts)
        record("restart-passed.json", restarted, original_location=True)
        immutable(original_dir, hashes)
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
        }
        record("results.json", result, original_location=True)
        record(
            "results.json",
            {**result, "original_result_sha256": h.file_hash(original_dir / "results.json")},
        )
    print(json.dumps({"status": "recovery_g1_passed_fenced_restoration_pending"}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="phase", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--original-dir", type=Path, required=True)
    prep.add_argument("--artifact-dir", type=Path, required=True)
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
                    "status": "recovery_stopped_unverified",
                    "exception_type": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, h.RefusalError)
                    else "Details withheld",
                    "recovery": "Retain fence/history/uncertainty; no replay, refund or rollback",
                }
            )
        )
        return 2
    finally:
        logging.disable(prior)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
