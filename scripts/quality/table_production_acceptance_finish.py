"""Ready-only G1 finish: no promotion, warming, old stop, new allocation or history replay."""

from __future__ import annotations

import argparse
import copy
import hashlib
import ipaddress
import json
import logging
import subprocess
import time
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import httpx
import table_production_acceptance as h
import table_production_acceptance_continue as c
import table_production_acceptance_recovery as r

from foundry_router.credit import estimate_response_usage_cost

if TYPE_CHECKING:
    from collections.abc import Iterator

Json = dict[str, Any]
ROOT = Path(__file__).resolve().parents[2]
CONTINUE_SHA = "a2b3e20c24141528ff92560c9675eebb6289a29339bb51257ea16566724280ee"
CONTINUE_TEST_SHA = "c912b9f8eaa93f1066819999cc8e19a8897d130a528ebb5b5d240708375b1191"
CONTINUE_PREP_SHA = "b9cc205e8c3c782e4c71371e00f93ea61d2e9170de2c7d320a38ac2baa310c4b"
READY_SHA = "aa820b62968cc4c44ba8c28589e697c4cd7320faecf882de9aba0ade435e5fbc"
GUARD = "ready-finish-consumed.json"
FINISH_LOCK = "ready-finish.lock"
ORIGINAL_FILES = c.ORIGINAL_FILES | {c.CONTINUATION_LOCK, c.GUARD, "api-2025-update-consumed.json"}
CONTINUE_FILES = {
    "prepared.json",
    "approval.json",
    "consumed.json",
    "execution.lock",
    "apply-summary.log",
}
MAX_ROLLING_WORKERS = 2


def history(
    original_dir: Path, recovery_dir: Path, continuation_dir: Path
) -> tuple[Json, Json, Json, Json]:
    h.require(not (original_dir / GUARD).exists(), "Ready finish already consumed")
    hashes = {
        "original": c.files(original_dir, ORIGINAL_FILES, optional={FINISH_LOCK}),
        "recovery": c.files(recovery_dir, c.RECOVERY_FILES),
        "continuation": c.files(continuation_dir, CONTINUE_FILES),
    }
    h.require(
        hashes["original"]["prepared.json"] == r.ORIGINAL_PACKET_SHA
        and hashes["recovery"]["prepared.json"] == c.RECOVERY_PREP_SHA
        and hashes["continuation"]["prepared.json"] == CONTINUE_PREP_SHA,
        "Exact consumed e/a/D history required",
    )
    original = r.read(original_dir / "prepared.json")
    recovery = r.read(recovery_dir / "prepared.json")
    continuation = r.read(continuation_dir / "prepared.json")
    h.validate_packet_budget(original)
    h.approved(original_dir / "prepared.json", original_dir / "approval.json")
    r.approval(recovery_dir / "approval.json", recovery_dir / "prepared.json", recovery)
    c.approval(continuation_dir / "approval.json", continuation_dir / "prepared.json", continuation)
    h.require(
        Path(recovery["original_dir"]) == original_dir
        and Path(continuation["original_dir"]) == original_dir
        and Path(continuation["recovery_dir"]) == recovery_dir,
        "Prior capsule directory linkage drift",
    )
    for group in ("original", "recovery"):
        for name, expected in continuation["prior_hashes"][group].items():
            h.require(hashes[group][name] == expected, "Immutable prepromotion history drift")
    ledger = r.read(original_dir / "program-ledger.json")
    h.require(
        Path(original["program_ledger"]) == original_dir / "program-ledger.json"
        and ledger["limit_usd"] == 1
        and ledger["attempt_limit"] == h.PROGRAM_ATTEMPTS
        and ledger["phase1_slots"] == original["cases"] == continuation["original_slots"]
        and ledger["phase1_reserved_usd"] == original["phase_reserved_usd"]
        and ledger["packet_sha256"] == hashes["original"]["prepared.json"]
        and ledger["approval_sha256"] == h.digest(r.read(original_dir / "approval.json")),
        "Original budget/slot ownership drift",
    )
    failed = r.read(continuation_dir / "apply-summary.log")
    h.require(
        failed["status"] == "api_continuation_stopped_unverified"
        and failed["reason"] == "Inactive revision has workers",
        "Known postpromotion checker failure required",
    )
    link = r.read(original_dir / c.GUARD)["continuation_link"]
    h.require(
        link["packet_sha256"] == hashes["continuation"]["prepared.json"]
        and link["continuation_id"] == continuation["continuation_id"]
        and Path(link["continuation_dir"]) == continuation_dir
        and link["api_version"] == c.API_VERSION
        and link["approval_sha256"] == h.digest(r.read(continuation_dir / "approval.json")),
        "Consumed D ownership drift",
    )
    for path in (
        continuation_dir / "consumed.json",
        original_dir / "api-2025-update-consumed.json",
    ):
        h.require(
            r.read(path)["continuation_link"] == link, "Successful promotion consumption mismatch"
        )
    h.require(
        r.read(original_dir / "api-2025-update-consumed.json")["proposal_sha256"]
        == hashes["original"]["update-proposal.json"],
        "Original promotion proposal changed",
    )
    h.unchanged(
        h.accounts(r.read(original_dir / "old-drained.json")["admin"], legacy=True),
        original["original_accounts"],
    )
    return original, recovery, continuation, hashes


def binding(original: Json, recovery: Json, continuation: Json) -> Json:
    h.require(
        h.file_hash(Path(c.__file__)) == CONTINUE_SHA
        and h.file_hash(ROOT / "tests/unit/test_table_production_acceptance_continue.py")
        == CONTINUE_TEST_SHA,
        "Frozen continuation source/test drift",
    )
    dependencies = c.release(original, recovery)
    h.require(dependencies == continuation["binding"], "Frozen runtime/image/dependency drift")
    return {
        "dependencies": dependencies,
        "finish_sha256": h.file_hash(Path(__file__)),
        "tests_sha256": h.file_hash(ROOT / "tests/unit/test_table_production_acceptance_finish.py"),
    }


def original_raw(original: Json, current: Json) -> Json:
    """Hydrate old literals from verified current literals and the recorded old retry."""
    old = copy.deepcopy(original["test_projection"])
    current_env = {
        item["name"]: item for item in current["properties"]["template"]["containers"][0]["env"]
    }
    for entry in old["properties"]["template"]["containers"][0]["env"]:
        if "value" not in entry:
            continue
        value = (
            str(original["original_snapshot"]["admin"]["config"]["retry_attempts"])
            if entry["name"] == "FOUNDRY_RETRY_ATTEMPTS"
            else current_env[entry["name"]]["value"]
        )
        h.require(
            h.digest(value) == entry["value"]["sha256"], "Original literal hydration hash mismatch"
        )
        entry["value"] = value
    return dict(old)


def inventory(azure: c.AllRevisionsAzure) -> list[Json]:
    result = []
    for revision in azure.app_command(["revision", "list", "--all"]):
        containers = revision["properties"]["template"]["containers"]
        h.require(len(containers) == 1, "Revision must contain one configured container")
        replicas = azure.app_command(["replica", "list", "--revision", revision["name"]])
        result.append(
            {
                "name": revision["name"],
                "active": revision["properties"].get("active"),
                "image": containers[0]["image"],
                "template": revision["properties"]["template"],
                "workers": [
                    {"name": replica["name"], "containers": replica["properties"]["containers"]}
                    for replica in replicas
                ],
            }
        )
    return result


def topology(
    items: list[Json], revision: str, image: str, template: Json | None, *, rolling: bool = False
) -> list[Json]:
    owned = []
    found = False
    for item in items:
        h.require(type(item["active"]) is bool, "Unknown revision activity")
        if item["name"] != revision:
            h.require(
                item["active"] is False and not item["workers"],
                "Old or unapproved revision has writers/activity",
            )
            continue
        h.require(not found and item["image"] == image, "Approved current revision/image mismatch")
        found = True
        if template is not None:
            h.require(item["template"] == template, "Current revision settings drift")
        if rolling:
            h.require(
                len(item["workers"]) <= MAX_ROLLING_WORKERS,
                "Unexpected rolling worker multiplicity",
            )
        else:
            h.require(
                item["active"] is True and len(item["workers"]) == 1,
                "Settled one-active/one-worker required",
            )
        owned = [
            {"name": worker["name"], "properties": {"containers": worker["containers"]}}
            for worker in item["workers"]
        ]
        if not rolling:
            h.generation(owned[0])
    h.require(found or rolling, "Approved current revision missing")
    return owned


def revision_template(items: list[Json], revision: str) -> Json:
    matches = [item for item in items if item["name"] == revision]
    h.require(len(matches) == 1, "Approved current revision template missing or duplicated")
    template = matches[0].get("template")
    if not isinstance(template, dict):
        raise h.RefusalError("Approved current revision template unavailable")
    return dict(template)


def compare_template_views(revision_view: Json, app_view: Json) -> None:
    """Compare configured template fields across ARM's app and revision views."""
    actual, expected = copy.deepcopy(revision_view), copy.deepcopy(app_view)
    if actual.get("revisionSuffix") is None:
        actual.pop("revisionSuffix", None)
        expected.pop("revisionSuffix", None)
    actual_containers = actual.get("containers", [])
    expected_containers = expected.get("containers", [])
    h.require(
        len(actual_containers) == len(expected_containers),
        "App/revision container template mismatch",
    )
    for actual_container, expected_container in zip(
        actual_containers, expected_containers, strict=True
    ):
        if "probes" in actual_container and "probes" not in expected_container:
            actual_container.pop("probes")
        actual_resources = actual_container.get("resources", {})
        expected_resources = expected_container.get("resources", {})
        h.require(
            isinstance(actual_resources, dict) and isinstance(expected_resources, dict),
            "Invalid app/revision resource template",
        )
        if "ephemeralStorage" in expected_resources and "ephemeralStorage" not in actual_resources:
            expected_resources.pop("ephemeralStorage")
            if not expected_resources:
                expected_container.pop("resources", None)
    actual_scale = actual.get("scale", {})
    expected_scale = expected.get("scale", {})
    h.require(
        isinstance(actual_scale, dict) and isinstance(expected_scale, dict),
        "Invalid app/revision scale template",
    )
    for field in ("cooldownPeriod", "pollingInterval"):
        if field in expected_scale and actual_scale.get(field) is None:
            expected_scale.pop(field)
            actual_scale.pop(field, None)
    h.require(actual == expected, "Current revision settings drift")


def verify_revision_binding(actual: list[Json], expected: list[Json], revision: str) -> None:
    h.require(
        revision_template(actual, revision) == revision_template(expected, revision),
        "Approved revision template drift",
    )


def evidence(path: Path, original: Json, hashes: Json) -> Json:
    data = r.read(path)
    h.require(
        h.file_hash(path) == READY_SHA
        and data["public_status"] == h.HTTP_DENIED
        and data["original_packet_sha256"] == hashes["original"]["prepared.json"]
        and data["continuation_prepared_sha256"] == hashes["continuation"]["prepared.json"]
        and data["continuation_failure_sha256"] == hashes["continuation"]["apply-summary.log"],
        "Exact ready evidence provenance required",
    )
    h.require(data["snapshot"]["ready"] is True, "Ready evidence has no ready process")
    h.unchanged(data["expected_accounts"], original["original_accounts"])
    h.unchanged(h.accounts(data["snapshot"]["admin"]), original["original_accounts"])
    topology(data["revision_inventory"], data["snapshot"]["revision"], original["image"], None)
    return data


def current(
    budget: r.Budget, original: Json, ready: Json, *, allow: list[Json] | None = None
) -> tuple[c.AllRevisionsAzure, Json, dict[str, str], Json, Json]:
    azure = c.AllRevisionsAzure(
        original["subscription"], original["test_rg"], original["test_app"], budget
    )
    app = azure.show()
    expected_projection = copy.deepcopy(ready["app_projection"])
    if allow is not None:
        expected_projection["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = (
            allow
        )
    h.require(
        r.shape(h.projection(app)) == r.shape(expected_projection),
        "Ready current configuration drift",
    )
    h.verify_successor(
        original_raw(original, app),
        app
        if allow is None
        else {
            **app,
            "properties": {
                **app["properties"],
                "configuration": {
                    **app["properties"]["configuration"],
                    "ingress": {
                        **app["properties"]["configuration"]["ingress"],
                        "ipSecurityRestrictions": h.DENY,
                    },
                },
            },
        },
        original["image"],
    )
    values, pins = budget.call(h.resolve, azure, app)
    h.require(pins == original["test_pins"], "Current secret pins drift")
    settings = h.settings_from(values)
    h.validate_modes(app, settings)
    h.require(
        settings.retry_attempts == 0 and app["properties"]["template"]["scale"]["minReplicas"] == 1,
        "Ready Table/min1/retry0 required",
    )
    h.require(
        h.cases_for(settings, list(dict.fromkeys(case["model"] for case in original["cases"])))
        == original["cases"],
        "Original pricing/pool/slot drift",
    )
    items = budget.call(inventory, azure, limit=r.WORKER_SECONDS)
    compare_template_views(
        revision_template(items, ready["snapshot"]["revision"]),
        app["properties"]["template"],
    )
    topology(
        items,
        ready["snapshot"]["revision"],
        original["image"],
        None,
    )
    snapshot = r.snapshot(budget, azure, values)
    h.require(
        snapshot["ready"] is True
        and snapshot["revision"] == ready["snapshot"]["revision"]
        and snapshot["server_command_sha256"] == ready["snapshot"]["server_command_sha256"],
        "Current worker launch/readiness drift",
    )
    return azure, app, values, snapshot, {"inventory": items, "pins": pins}


def production(budget: r.Budget, original: Json) -> None:
    azure = c.AllRevisionsAzure(
        original["subscription"], original["production_rg"], original["production_app"], budget
    )
    app = azure.show()
    h.require(
        h.projection(app) == original["production_projection"], "Read-only production config drift"
    )
    values, pins = budget.call(h.resolve, azure, app)
    h.require(pins == original["production_pins"], "Production secret pin drift")
    test = c.AllRevisionsAzure(
        original["subscription"], original["test_rg"], original["test_app"], budget
    )
    h.require(
        budget.call(h.dedicated_resources, test, original["cases"], h.settings_from(values))
        == original["dedicated_test_resources"],
        "Dedicated test resource drift",
    )


def locks(
    stack: ExitStack,
    original: Path,
    recovery: Path,
    continuation: Path,
) -> None:
    for path in (
        original / "execution.lock",
        original / r.PROGRAM_LOCK,
        original / c.CONTINUATION_LOCK,
        recovery / "execution.lock",
        continuation / "execution.lock",
    ):
        stack.enter_context(r.lock(path, existing=True))


@contextmanager
def bounded_phase(budget: r.Budget, seconds: float) -> Iterator[float]:
    """Constrain every nested budget-aware operation to one phase deadline."""
    prior_end = budget.end
    budget.end = min(prior_end, time.monotonic() + seconds)
    try:
        yield budget.end
    finally:
        budget.end = prior_end


def prepare(args: argparse.Namespace) -> None:
    r.directory(args.artifact_dir)
    h.require(not any(args.artifact_dir.iterdir()), "Fresh finish directory required")
    budget = r.Budget()
    with ExitStack() as stack:
        locks(stack, args.original_dir, args.recovery_dir, args.continuation_dir)
        original, recovery, continuation, hashes = history(
            args.original_dir, args.recovery_dir, args.continuation_dir
        )
        release = binding(original, recovery, continuation)
        ready_path = args.ready_evidence_dir / "ready.json"
        ready = evidence(ready_path, original, hashes)
        production(budget, original)
        _azure, app, _values, snapshot, details = current(budget, original, ready)
        h.require(
            h.process_identity(snapshot) == h.process_identity(ready["snapshot"])
            and snapshot["generation"] == ready["snapshot"]["generation"],
            "Ready evidence process/generation stale",
        )
        h.unchanged(h.accounts(snapshot["admin"]), original["original_accounts"])
        r.public_wait(budget, original["origin"], h.HTTP_DENIED)
        h.create(
            args.artifact_dir / "prepared.json",
            {
                "schema": "g1-ready-finish-v1",
                "finish_id": uuid.uuid4().hex,
                "original_dir": str(args.original_dir),
                "recovery_dir": str(args.recovery_dir),
                "continuation_dir": str(args.continuation_dir),
                "prior_hashes": hashes,
                "binding": release,
                "ready_path": str(ready_path),
                "ready_sha256": READY_SHA,
                "current_projection": r.shape(h.projection(app)),
                "baseline": snapshot,
                "inventory": details["inventory"],
                "pins": details["pins"],
                "executor_ip": str(ipaddress.IPv4Address(args.executor_ip)),
                "original_slots": original["cases"],
            },
        )
    print(
        json.dumps(
            {
                "status": "ready_finish_prepared_not_approved",
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
        "prior_hashes_sha256",
        "ready_sha256",
        "revision",
        "generation_sha256",
        "finish_accepted",
        "unused_slots_verified",
        "current_ready_old_workers_zero",
        "financial_equality_verified",
        "previous_executors_exited",
        "production_writer_paused",
        "staged_fenced_min1_accepted",
    }
    h.require(
        set(data) == keys
        and data["verdict"] == "approved"
        and bool(data["independent_reviewer"])
        and data["packet_sha256"] == prepared_sha256
        and data["prior_hashes_sha256"] == h.digest(packet["prior_hashes"])
        and data["ready_sha256"] == packet["ready_sha256"] == READY_SHA
        and data["revision"] == packet["baseline"]["revision"]
        and data["generation_sha256"] == h.digest(packet["baseline"]["generation"]),
        "Fresh independent ready-only finish approval required",
    )
    for key in (
        "finish_accepted",
        "unused_slots_verified",
        "current_ready_old_workers_zero",
        "financial_equality_verified",
        "previous_executors_exited",
        "production_writer_paused",
        "staged_fenced_min1_accepted",
    ):
        h.require(data[key] is True, "Finish ownership/state/staged disposition not approved")
    return data


def case_evidence(original_dir: Path, finish_dir: Path, index: int, *, stream: bool) -> Json:
    """Verify and hash-link the dispatch observation and stream EOF evidence."""
    observed_path = original_dir / f"case-{index}-observed.json"
    http_path = original_dir / f"case-{index}-observed-http.json"
    observed = r.read(observed_path)
    http = r.read(http_path)
    usage = h.response_usage({"status": "completed", "usage": observed.get("usage")})
    h.require(
        http == {"status": h.HTTP_OK}
        and observed.get("http_status") == h.HTTP_OK
        and observed.get("completed") is True
        and h.response_usage({"status": "completed", "usage": observed["usage"]}) == usage,
        "Accepted dispatch evidence mismatch",
    )
    proof = {
        "observation_sha256": h.file_hash(observed_path),
        "http_sha256": h.file_hash(http_path),
    }
    if stream:
        terminal_path = original_dir / f"case-{index}-observed-terminal.json"
        eof_path = finish_dir / f"case-{index}-stream-eof.json"
        terminal = r.read(terminal_path)
        eof = r.read(eof_path)
        h.require(
            terminal.get("terminal_observed") is True
            and terminal.get("clean_eof") is False
            and terminal.get("usage") == usage
            and eof.get("completed") is True
            and eof.get("clean_eof") is True,
            "Accepted stream completion/EOF evidence mismatch",
        )
        proof.update(
            {
                "terminal_sha256": h.file_hash(terminal_path),
                "stream_eof_sha256": h.file_hash(eof_path),
            }
        )
    return proof


def verify_case_evidence(
    original_dir: Path, finish_dir: Path, index: int, passed: Json, *, stream: bool
) -> None:
    """Check a pass receipt still matches its immutable response evidence files."""
    expected = case_evidence(original_dir, finish_dir, index, stream=stream)
    h.require(passed.get("evidence") == expected, "Case evidence hash chain drift")


def restart_wait(
    budget: r.Budget,
    azure: c.AllRevisionsAzure,
    templates: tuple[Json, Json],
    before: Json,
    image: str,
) -> None:
    app_template, revision_view_template = templates
    end = min(budget.end, time.monotonic() + r.WORKER_SECONDS)
    while time.monotonic() + r.CLEANUP_SECONDS < end:
        app = azure.show()
        h.require(
            app["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] == h.DENY
            and app["properties"]["template"] == app_template,
            "Restart fence/settings drift",
        )
        items = budget.call(inventory, azure, limit=end - time.monotonic())
        owned = topology(items, before["revision"], image, revision_view_template, rolling=True)
        active = [item for item in items if item["name"] == before["revision"] and item["active"]]
        if len(active) == 1 and len(owned) == 1:
            containers = owned[0]["properties"]["containers"]
            if len(containers) == 1 and containers[0].get("ready") and containers[0].get("started"):
                generation = h.generation(owned[0])
                prior = before["generation"]
                if generation[:2] != prior[:2] or generation[2] > prior[2]:
                    return
        budget.pause(1)
    raise h.RefusalError("Ready finish actual restart deadline")


def apply(args: argparse.Namespace) -> None:  # noqa: PLR0915 -- no deployment path, four slots once
    r.directory(args.artifact_dir)
    prepared_path = args.artifact_dir / "prepared.json"
    budget = r.Budget()
    with ExitStack() as stack:
        # Lock before reading: approval and execution must bind the same packet bytes.
        stack.enter_context(r.lock(args.artifact_dir / "execution.lock"))
        r.private_file(prepared_path)
        prepared_bytes = prepared_path.read_bytes()
        h.require(len(prepared_bytes) <= h.MAX_BYTES, "Artifact capacity exceeded")
        parsed = json.loads(prepared_bytes)
        h.require(isinstance(parsed, dict), "Object artifact required")
        packet = dict(parsed)
        prepared_sha256 = hashlib.sha256(prepared_bytes).hexdigest()
        h.require(packet["schema"] == "g1-ready-finish-v1", "Finish schema mismatch")
        verdict = approval(args.approval, prepared_sha256, packet)
        original_dir, recovery_dir, continuation_dir = (
            Path(packet[key]) for key in ("original_dir", "recovery_dir", "continuation_dir")
        )
        locks(stack, original_dir, recovery_dir, continuation_dir)
        stack.enter_context(r.lock(original_dir / FINISH_LOCK))
        original, recovery, continuation, hashes = history(
            original_dir, recovery_dir, continuation_dir
        )
        h.require(
            hashes == packet["prior_hashes"]
            and binding(original, recovery, continuation) == packet["binding"],
            "Finish source/history binding drift",
        )
        h.require(
            packet["original_slots"] == original["cases"], "Finish original slot identity drift"
        )
        ready = evidence(Path(packet["ready_path"]), original, hashes)
        production(budget, original)
        azure, app, values, baseline, details = current(budget, original, ready)
        verify_revision_binding(details["inventory"], packet["inventory"], baseline["revision"])
        h.require(
            h.process_identity(baseline) == h.process_identity(packet["baseline"])
            and baseline["generation"] == packet["baseline"]["generation"],
            "Approved ready worker changed before finish",
        )
        last = h.accounts(baseline["admin"])
        h.unchanged(last, original["original_accounts"])
        r.public_wait(budget, original["origin"], h.HTTP_DENIED)
        h.require(
            h.file_hash(prepared_path) == prepared_sha256,
            "Prepared packet changed after approval",
        )
        link = {
            "finish_id": packet["finish_id"],
            "packet_sha256": prepared_sha256,
            "finish_dir": str(args.artifact_dir),
            "approval_sha256": h.digest(verdict),
            "prior_hashes_sha256": h.digest(hashes),
            "ready_sha256": READY_SHA,
        }

        def record(name: str, data: Json, *, old: bool = False) -> None:
            budget.call(
                h.create,
                (original_dir if old else args.artifact_dir) / name,
                {**data, "finish_link": link},
                limit=15,
            )

        def immutable() -> None:
            for directory, key in (
                (original_dir, "original"),
                (recovery_dir, "recovery"),
                (continuation_dir, "continuation"),
            ):
                r.immutable(directory, hashes[key])

        record(GUARD, {"original_slot_indices": list(range(h.PHASE_ATTEMPTS))}, old=True)
        record("consumed.json", {"deployment_repeated": False})
        record("successor-baseline.json", baseline, old=True)
        allow = [
            {
                "name": "g1-executor",
                "ipAddressRange": str(ipaddress.IPv4Address(packet["executor_ip"])) + "/32",
                "action": "Allow",
            }
        ]

        def ingress(stage: str, policy: list[Json], status: int) -> None:
            record(stage + "-consumed.json", {"policy_sha256": h.digest(policy)})
            budget.call(azure.ingress, app["id"], policy)
            r.public_wait(budget, original["origin"], status)

        ingress("executor-allow", allow, h.HTTP_OK)
        settings = h.settings_from(values)
        for index, case in enumerate(original["cases"]):
            immutable()
            _azure, _app, _values, before, before_details = current(
                budget, original, ready, allow=allow
            )
            verify_revision_binding(
                before_details["inventory"], packet["inventory"], before["revision"]
            )
            h.require(
                h.process_identity(before) == h.process_identity(baseline),
                "Finish paid worker changed",
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
                h.credential(values, "FOUNDRY_CLIENT_API_KEYS_JSON"),
                case,
                original_dir / f"case-{index}-observed.json",
            )
            if case["stream"]:
                record(
                    f"case-{index}-stream-eof.json",
                    {"completed": True, "clean_eof": True},
                )
            evidence_hashes = case_evidence(
                original_dir, args.artifact_dir, index, stream=case["stream"]
            )
            h.require(
                observed["http_status"] == h.HTTP_OK and observed["completed"] is True,
                "Finish terminal observation invalid",
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
                "Finish charge exceeds original slot",
            )
            assert debit is not None
            _azure, _app, _values, after, after_details = current(
                budget, original, ready, allow=allow
            )
            verify_revision_binding(
                after_details["inventory"], packet["inventory"], after["revision"]
            )
            h.require(
                h.process_identity(after) == h.process_identity(baseline),
                "Finish settlement worker changed",
            )
            next_accounts = h.accounts(after["admin"])
            h.verify_debit(last, next_accounts, case["group"], debit)
            last = next_accounts
            record(
                f"case-{index}-passed.json",
                {"debit_usd": debit, "accounts": last, "evidence": evidence_hashes},
                old=True,
            )
            verify_case_evidence(
                original_dir,
                args.artifact_dir,
                index,
                r.read(original_dir / f"case-{index}-passed.json"),
                stream=case["stream"],
            )
        ingress("final-deny", h.DENY, h.HTTP_DENIED)
        budget.pause(r.DRAIN_SECONDS)
        _azure, final_app, _values, final, final_details = current(budget, original, ready)
        verify_revision_binding(final_details["inventory"], packet["inventory"], final["revision"])
        h.require(
            h.process_identity(final) == h.process_identity(baseline)
            and final["request_counters"] == after["request_counters"],
            "Final finish drain process/request drift",
        )
        h.unchanged(h.accounts(final["admin"]), last)
        record("restart-consumed.json", final, old=True)
        with bounded_phase(budget, r.WORKER_SECONDS):
            budget.call(
                azure.app_command,
                ["revision", "restart", "--revision", final["revision"]],
            )
            restart_wait(
                budget,
                azure,
                (
                    final_app["properties"]["template"],
                    revision_template(final_details["inventory"], final["revision"]),
                ),
                final,
                original["image"],
            )
            _azure, _app, _values, restarted, restarted_details = current(budget, original, ready)
            verify_revision_binding(
                restarted_details["inventory"], packet["inventory"], restarted["revision"]
            )
            h.require(
                h.process_identity(restarted) != h.process_identity(final),
                "No actual finish process replacement",
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
                "case_hashes": [
                    h.file_hash(original_dir / f"case-{index}-passed.json")
                    for index in range(h.PHASE_ATTEMPTS)
                ],
                "restart_sha256": h.file_hash(original_dir / "restart-passed.json"),
                "prior_hashes": hashes,
                "binding": packet["binding"],
                "ready_sha256": READY_SHA,
                "recovery_link": r.read(original_dir / r.GUARD)["recovery_link"],
                "continuation_link": r.read(original_dir / c.GUARD)["continuation_link"],
            }
            record("results.json", result, old=True)
            record(
                "results.json",
                {**result, "original_result_sha256": h.file_hash(original_dir / "results.json")},
            )
    print(json.dumps({"status": "ready_finish_g1_passed_fenced_cleanup_pending"}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="phase", required=True)
    prep = subs.add_parser("prepare")
    for name in (
        "original-dir",
        "recovery-dir",
        "continuation-dir",
        "ready-evidence-dir",
        "artifact-dir",
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
                    "status": "ready_finish_stopped_unverified",
                    "exception_type": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, h.RefusalError)
                    else "Details withheld",
                    "recovery": "Keep fence/history/uncertainty; no replay, refund or rollback",
                }
            )
        )
        return 2
    finally:
        logging.disable(prior)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
