"""No Azure or paid HTTP: Phase 0/1 acceptance invariants and orchestration mocks."""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/quality/table_production_acceptance.py"
SPEC = importlib.util.spec_from_file_location("table_production_acceptance", SCRIPT)
assert SPEC and SPEC.loader
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)


def values() -> dict[str, str]:
    backends = {
        name: {
            "endpoint": "https://dedicated.openai.azure.com",
            "deployment": name,
            "credential": "synthetic-only",
            "credit_group": name,
        }
        for name in ("one", "two")
    }
    return {
        "FOUNDRY_BACKENDS_JSON": json.dumps(backends),
        "FOUNDRY_MODELS_JSON": json.dumps({name: {"backends": {name: 1}} for name in backends}),
        "FOUNDRY_PRICING_JSON": json.dumps(
            {
                name: {
                    "input_per_million": 10,
                    "output_per_million": 30,
                    "cached_input_per_million": 5,
                }
                for name in backends
            }
        ),
        "FOUNDRY_CLIENT_API_KEYS_JSON": '["synthetic-client"]',
        "FOUNDRY_ADMIN_API_KEYS_JSON": '["synthetic-admin"]',
        "FOUNDRY_STATE_BACKEND": "table",
        "FOUNDRY_TABLE_ENDPOINT": "https://synthetic.table.core.windows.net/",
        "FOUNDRY_TABLE_CREDIT_NAME": "syntheticcredit",
        "FOUNDRY_TABLE_HEALTH_NAME": "synthetichealth",
        "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON": '{"one":1,"two":1}',
        "FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON": '{"one":100,"two":100}',
        "FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON": '{"one":100,"two":100}',
    }


def app(name: str = "test") -> dict[str, Any]:
    return {
        "id": "/synthetic/" + name,
        "name": name,
        "properties": {
            "latestReadyRevisionName": "old",
            "latestRevisionName": "old",
            "template": {
                "containers": [
                    {
                        "name": "router",
                        "image": "synthetic@sha256:" + "a" * 64,
                        "env": [{"name": key, "value": value} for key, value in values().items()],
                    }
                ],
                "scale": {"maxReplicas": 1, "minReplicas": 0},
            },
            "configuration": {
                "activeRevisionsMode": "Single",
                "secrets": [],
                "ingress": {
                    "external": True,
                    "fqdn": "synthetic.example",
                    "allowInsecure": False,
                    "ipSecurityRestrictions": [],
                },
            },
        },
    }


def snapshot(ticks: str = "10", remaining: float = 100, debit: float = 0) -> dict[str, Any]:
    groups = {
        name: {
            "live": {
                "active_reservations": 0,
                "reserved_inflight_usd": 0,
                "estimated_remaining_usd": remaining if name == "one" else 100,
                "current_cycle_start_utc": "synthetic-cycle",
                "debited_usd_total": debit if name == "one" else 0,
                "recovered_debit_usd_total": 0,
            }
        }
        for name in ("one", "two")
    }
    return {
        "revision": "old",
        "replica": "replica",
        "boot_id": "boot",
        "process_start_ticks": ticks,
        "environment_sha256": {},
        "request_counters": [],
        "generation": ["replica", "container", 0],
        "admin": {"credit_groups": groups, "config": {"retry_attempts": 0}},
    }


@pytest.fixture
def private(tmp_path: Path) -> Path:
    tmp_path.chmod(0o700)
    return tmp_path


def test_settings_estimator_and_budget_use_current_source() -> None:
    settings = h.settings_from(values())
    cases = h.cases_for(settings, ["one", "two"])
    assert len(cases) == 4
    assert sum(case["reserve_usd"] for case in cases) < 1
    assert all(case["reserve_usd"] >= case["local_estimate_usd"] for case in cases)
    assert h.body_for("one", True)["max_output_tokens"] == 128


@pytest.mark.parametrize("mutation", ["duplicate", "pool", "price", "alias"])
def test_invalid_case_contract(mutation: str) -> None:
    settings = h.settings_from(values())
    models = ["one", "two"]
    if mutation == "duplicate":
        models = ["one", "one"]
    elif mutation == "pool":
        settings.models["one"].backends["two"] = 1
    elif mutation == "price":
        settings.pricing["one"].input_per_million = 1e9
    else:
        settings.model_aliases["alias"] = "one"
    with pytest.raises(h.RefusalError):
        h.cases_for(settings, models)


@pytest.mark.parametrize(
    "mutation", ["scale", "mode", "state", "quota", "telemetry", "command", "http"]
)
def test_mode_drift(mutation: str) -> None:
    deployment, settings = app(), h.settings_from(values())
    if mutation == "scale":
        deployment["properties"]["template"]["scale"]["maxReplicas"] = 2
    elif mutation == "mode":
        deployment["properties"]["configuration"]["activeRevisionsMode"] = "Multiple"
    elif mutation == "state":
        settings.state_backend = "memory"
    elif mutation == "quota":
        settings.rate_limit_backend = "table"
    elif mutation == "telemetry":
        settings.telemetry_enabled = True
    elif mutation == "command":
        deployment["properties"]["template"]["containers"][0]["args"] = ["--workers", "2"]
    else:
        deployment["properties"]["configuration"]["ingress"]["allowInsecure"] = True
    with pytest.raises(h.RefusalError):
        h.validate_modes(deployment, settings)


def test_mode_success() -> None:
    h.validate_modes(app(), h.settings_from(values()))


def test_owner_permissions_exclusive_consumption(private: Path) -> None:
    path = private / "consumed.json"
    h.create(path, {"consumed": True})
    assert path.stat().st_mode & 0o777 == 0o600
    assert h.read_json(path) == {"consumed": True}
    with pytest.raises(FileExistsError):
        h.create(path, {"replay": True})
    private.chmod(0o755)
    with pytest.raises(h.RefusalError):
        h.private_directory(private)


def test_symlink_directory_refused(private: Path) -> None:
    link = private / "link"
    link.symlink_to(private, target_is_directory=True)
    with pytest.raises(h.RefusalError):
        h.private_directory(link)


def test_projection_never_retains_values() -> None:
    projected = h.projection(app())
    assert "synthetic-client" not in json.dumps(projected)
    changed = app()
    changed["properties"]["template"]["containers"][0]["env"][0]["value"] = "drift"
    assert h.projection(changed) != projected


@pytest.mark.parametrize(
    "reference",
    [
        "https://synthetic.vault.azure.net/secrets/key",
        "http://bad/secrets/key/" + "a" * 32,
        "https://synthetic.vault.azure.net/secrets/key/" + "a" * 32 + "?x=y",
    ],
)
def test_unpinned_secret_refused(reference: str) -> None:
    with pytest.raises(h.RefusalError):
        h.Azure("synthetic", "rg", "test").secret(reference)


def test_secret_versions_values_hashed_only(monkeypatch: pytest.MonkeyPatch) -> None:
    azure = h.Azure("synthetic", "rg", "test")
    reference = "https://synthetic.vault.azure.net/secrets/key/" + "a" * 32
    monkeypatch.setattr(azure, "run", lambda _: {"id": reference, "value": "never-record"})
    deployment = app()
    deployment["properties"]["template"]["containers"][0]["env"] = [
        {"name": "FOUNDRY_TEST", "secretRef": "key"}
    ]
    deployment["properties"]["configuration"]["secrets"] = [
        {"name": "key", "keyVaultUrl": reference, "identity": "synthetic"}
    ]
    resolved, pins = h.resolve(azure, deployment)
    assert resolved["FOUNDRY_TEST"] == "never-record"
    assert "never-record" not in json.dumps(pins)
    monkeypatch.setattr(
        azure,
        "run",
        lambda _: {"id": reference.replace("a" * 32, "b" * 32), "value": "never-record"},
    )
    with pytest.raises(h.RefusalError, match="version drift"):
        h.resolve(azure, deployment)


def test_dedicated_resources_disjoint_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = h.settings_from(values())
    cases = h.cases_for(settings, ["one", "two"])
    azure = h.Azure("synthetic", "rg", "test")
    with pytest.raises(h.RefusalError, match="overlaps"):
        h.dedicated_resources(azure, cases, settings)
    for backend in settings.backends.values():
        backend.endpoint = (
            h.settings_from(values())
            .backends["one"]
            .endpoint.__class__("https://production.openai.azure.com")
        )
    monkeypatch.setattr(
        azure,
        "run",
        lambda _: [
            {
                "id": "/synthetic/dedicated",
                "name": "dedicated",
                "kind": "OpenAI",
                "properties": {"endpoints": {"OpenAI": "https://dedicated.openai.azure.com/"}},
            }
        ],
    )
    assert (
        h.dedicated_resources(azure, cases, settings)["dedicated.openai.azure.com"]["id"]
        == "/synthetic/dedicated"
    )
    monkeypatch.setattr(azure, "run", lambda _: [])
    with pytest.raises(h.RefusalError):
        h.dedicated_resources(azure, cases, settings)


def test_writer_overlap_and_missing_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    azure = h.Azure("synthetic", "rg", "test")
    revisions = [{"name": name, "properties": {"active": True}} for name in ("old", "new")]
    monkeypatch.setattr(azure, "app_command", lambda _: revisions)
    with pytest.raises(h.RefusalError, match="Overlapping"):
        azure.writers()
    monkeypatch.setattr(azure, "app_command", lambda _: [])
    assert azure.writers(allow_none=True) == []
    with pytest.raises(h.RefusalError):
        azure.writers()


def test_single_writer_and_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    azure = h.Azure("synthetic", "rg", "test")
    writer: dict[str, Any] = {
        "name": "replica",
        "properties": {
            "containers": [
                {"ready": True, "started": True, "containerId": "container", "restartCount": 0}
            ]
        },
    }
    monkeypatch.setattr(
        azure,
        "app_command",
        lambda command: (
            [{"name": "old", "properties": {"active": True}}]
            if command[0] == "revision"
            else [writer]
        ),
    )
    assert h.generation(azure.writers()[0]) == ["replica", "container", 0]
    writer["properties"]["containers"][0]["ready"] = False
    with pytest.raises(h.RefusalError):
        h.generation(writer)


@pytest.mark.parametrize(
    "field",
    [
        "active_reservations",
        "reserved_inflight_usd",
        "estimated_remaining_usd",
        "debited_usd_total",
    ],
)
def test_bad_account_diagnostics(field: str) -> None:
    data = snapshot()["admin"]
    data["credit_groups"]["one"]["live"][field] = (
        1 if "reserv" in field or "inflight" in field else float("nan")
    )
    with pytest.raises(h.RefusalError):
        h.accounts(data)


def test_debit_counter_persistence_and_legacy_baseline() -> None:
    before = h.accounts(snapshot()["admin"])
    after = h.accounts(snapshot(remaining=99.99, debit=0.01)["admin"])
    h.verify_debit(before, after, "one", 0.01)
    h.unchanged(after, copy.deepcopy(after))
    after["one"]["debited_usd_total"] = 0
    with pytest.raises(h.RefusalError, match="counter"):
        h.verify_debit(before, after, "one", 0.01)
    legacy = snapshot()["admin"]
    del legacy["credit_groups"]["one"]["live"]["debited_usd_total"]
    with pytest.raises(h.RefusalError):
        h.accounts(legacy)
    assert h.accounts(legacy, legacy=True)["one"]["debited_usd_total"] == 0


@pytest.mark.parametrize("mutation", ["cycle", "recovery", "other", "membership"])
def test_unexpected_account_changes(mutation: str) -> None:
    before = h.accounts(snapshot()["admin"])
    after = copy.deepcopy(before)
    if mutation == "cycle":
        after["one"]["current_cycle_start_utc"] = "next"
    elif mutation == "recovery":
        after["one"]["recovered_debit_usd_total"] = 1
    elif mutation == "other":
        after["two"]["estimated_remaining_usd"] = 90
    else:
        del after["two"]
    with pytest.raises(h.RefusalError):
        h.verify_debit(before, after, "one", 0)


def test_environment_pin() -> None:
    data = snapshot()
    with pytest.raises(h.RefusalError):
        h.verify_environment(data, {"FOUNDRY_TEST": "value"})
    import hashlib

    data["environment_sha256"]["FOUNDRY_TEST"] = hashlib.sha256(b"value").hexdigest()
    h.verify_environment(data, {"FOUNDRY_TEST": "value"})


def terminal() -> dict[str, Any]:
    return {
        "status": "completed",
        "usage": {
            "input_tokens": 4,
            "output_tokens": 1,
            "total_tokens": 5,
            "input_tokens_details": {"cached_tokens": 2},
        },
        "output": [{"text": "never-persist-output"}],
    }


@pytest.mark.parametrize("stream", [False, True])
def test_dispatch_observed_before_diagnostics(
    private: Path, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    original = httpx.AsyncClient
    payload = terminal()
    wire = (
        b"data: "
        + json.dumps({"type": "response.completed", "response": payload}).encode()
        + b"\r\n\r\ndata: [DONE]\r\n\r\n"
    )

    def transport(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["max_output_tokens"] == 128
        return httpx.Response(200, content=wire if stream else json.dumps(payload).encode())

    monkeypatch.setattr(
        h.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    result = h.dispatch(
        "https://synthetic.example",
        "synthetic-client",
        {"model": "one", "stream": stream},
        private / "observed.json",
    )
    assert result["completed"]
    assert "never-persist-output" not in (private / "observed.json").read_text()
    assert h.read_json(private / "observed-http.json") == {"status": 200}
    debit = h.estimate_response_usage_cost(
        SimpleNamespace(
            body=json.dumps({"usage": result["usage"]}).encode(),
            headers={"content-type": "application/json"},
        ),
        "one",
        h.settings_from(values()).pricing,
    )
    assert debit == pytest.approx(0.00006)


def test_uncertain_failure_does_not_replenish_consumed_slot(
    private: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = httpx.AsyncClient

    def transport(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("uncertain")

    monkeypatch.setattr(
        h.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    h.create(private / "slot-consumed.json", {"reserve_usd": 0.1})
    with pytest.raises(httpx.ReadTimeout):
        h.dispatch(
            "https://synthetic.example",
            "synthetic",
            {"model": "one", "stream": False},
            private / "observed.json",
        )
    assert h.read_json(private / "slot-consumed.json")["reserve_usd"] == 0.1
    assert not (private / "observed.json").exists()


@pytest.mark.parametrize("mutation", ["status", "total", "output", "input", "missing"])
def test_invalid_response_usage(mutation: str) -> None:
    data = terminal()
    if mutation == "status":
        data["status"] = "incomplete"
    elif mutation == "missing":
        data.pop("usage")
    else:
        data["usage"][
            {"total": "total_tokens", "output": "output_tokens", "input": "input_tokens"}[mutation]
        ] = 1000
    with pytest.raises(h.RefusalError):
        h.response_usage(data)


def test_approval_requires_exact_hash_and_disposition(private: Path) -> None:
    packet, approval = private / "prepared.json", private / "approval.json"
    h.create(packet, {"phase": "G1"})
    h.create(
        approval,
        {
            "packet_sha256": h.file_hash(packet),
            "verdict": "approved",
            "independent_reviewer": "other-session",
            "m1_closed": True,
            "liability_reserved_outside_production": True,
            "staged_fenced_completion_accepted": True,
            "liability_disposition": "dedicated disjoint account",
        },
    )
    assert h.approved(packet, approval)["m1_closed"]
    packet.write_text('{"phase":"changed"}')
    with pytest.raises(h.RefusalError):
        h.approved(packet, approval)


def test_azure_errors_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        h.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1, stdout=b"credential", stderr=b"credential"
        ),
    )
    with pytest.raises(h.RefusalError) as error:
        h.Azure("synthetic", "rg", "test").show()
    assert "credential" not in str(error.value)


def test_main_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [str(SCRIPT), "apply", "--artifact-dir", "/synthetic", "--approval", "/synthetic/approval"],
    )
    monkeypatch.setattr(
        h, "apply", lambda _: (_ for _ in ()).throw(ValueError("credential must not escape"))
    )
    assert h.main() == 2
    assert "credential" not in capsys.readouterr().out


def test_prepare_and_apply_drift_before_consumption(
    private: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet = {
        "subscription": "synthetic",
        "test_rg": "rg",
        "test_app": "test",
        "production_rg": "rg",
        "production_app": "production",
        "prior_metadata": "/synthetic",
        "image": "synthetic",
        "binding": {"script": "original"},
    }
    h.create(private / "prepared.json", packet)
    monkeypatch.setattr(h, "approved", lambda *_args: {})
    monkeypatch.setattr(h, "validate_packet_budget", lambda _packet: None)
    monkeypatch.setattr(h, "source_binding", lambda *_args: {"script": "drift"})
    with pytest.raises(h.RefusalError, match="drift"):
        h.apply(argparse.Namespace(artifact_dir=private, approval=private / "approval.json"))
    assert not (private / "consumed.json").exists()


class FakeAzure:
    """Read/mutation model with sole-writer state and monotonic debit persistence."""

    instances: ClassVar[dict[str, FakeAzure]] = {}

    def __init__(self, subscription: str, resource_group: str, name: str):
        if name in FakeAzure.instances:
            self.__dict__ = FakeAzure.instances[name].__dict__
            return
        self.subscription, self.resource_group, self.app = subscription, resource_group, name
        self.deployment = app(name)
        self.env = values()
        if name == "production":
            self.env["FOUNDRY_STATE_BACKEND"] = "memory"
            self.env["FOUNDRY_BACKENDS_JSON"] = self.env["FOUNDRY_BACKENDS_JSON"].replace(
                "dedicated", "production"
            )
        self.active = True
        self.ticks = "10"
        self.balances = h.accounts(snapshot()["admin"])
        self.calls: list[list[str]] = []
        FakeAzure.instances[name] = self

    def show(self) -> dict[str, Any]:
        return copy.deepcopy(self.deployment)

    def app_command(self, command: list[str]) -> Any:
        self.calls.append(command)
        if command[:2] == ["revision", "deactivate"]:
            self.active = False
        elif command[0] == "update":
            assert not self.active, "new image cannot overlap old writer"
            self.active = True
            self.env["FOUNDRY_RETRY_ATTEMPTS"] = "0"
            self.deployment["properties"]["template"]["scale"]["minReplicas"] = 1
            self.deployment["properties"]["template"]["containers"][0]["env"].append(
                {"name": "FOUNDRY_RETRY_ATTEMPTS", "value": "0"}
            )
            self.ticks = "20"
            self.deployment["properties"]["latestReadyRevisionName"] = "new"
            self.deployment["properties"]["template"]["containers"][0]["image"] = command[
                command.index("--image") + 1
            ]
        elif command[:2] == ["revision", "restart"]:
            self.ticks = "30"
        elif command[:2] == ["revision", "list"]:
            return [{"name": "old", "properties": {"active": self.active}}]
        return None

    def writers(self, *, allow_none: bool = False) -> list[dict[str, Any]]:
        assert allow_none or self.active
        return (
            [{"name": "replica", "properties": {"containers": [{"ready": True, "started": True}]}}]
            if self.active
            else []
        )

    def ingress(self, _app_id: str, restrictions: list[dict[str, Any]]) -> None:
        self.deployment["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = (
            copy.deepcopy(restrictions)
        )

    def snapshot(self) -> dict[str, Any]:
        result = snapshot(self.ticks)
        result["revision"] = self.deployment["properties"]["latestReadyRevisionName"]
        result["admin"]["credit_groups"] = {
            name: {"live": {**entry, "active_reservations": 0, "reserved_inflight_usd": 0}}
            for name, entry in self.balances.items()
        }
        return result


def mocked_program(private: Path, monkeypatch: pytest.MonkeyPatch) -> argparse.Namespace:
    FakeAzure.instances.clear()
    monkeypatch.setattr(h, "Azure", FakeAzure)
    monkeypatch.setattr(h, "resolve", lambda azure, _app: (azure.env.copy(), {}))
    monkeypatch.setattr(h, "source_binding", lambda *_args: {"current": True})
    monkeypatch.setattr(
        h,
        "dedicated_resources",
        lambda *_args: {"dedicated.openai.azure.com": {"id": "/synthetic"}},
    )
    monkeypatch.setattr(h, "local_snapshot", lambda azure, _app: azure.snapshot())
    monkeypatch.setattr(h, "verify_environment", lambda *_args: None)
    monkeypatch.setattr(h.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(h, "wait_replacement", lambda *_args: None)

    def public(_origin: str, path: str, key: str | None = None) -> tuple[int, bytes]:
        azure = FakeAzure.instances["test"]
        restrictions = azure.deployment["properties"]["configuration"]["ingress"][
            "ipSecurityRestrictions"
        ]
        if restrictions == h.DENY:
            return 403, b""
        if path == "/admin/status":
            return (200, json.dumps(azure.snapshot()["admin"]).encode()) if key else (401, b"")
        return 200, b'{"ready":true}'

    monkeypatch.setattr(h, "get_public", public)
    return argparse.Namespace(
        artifact_dir=private,
        program_ledger=private / "program-ledger.json",
        subscription="synthetic",
        test_rg="rg",
        test_app="test",
        production_rg="rg",
        production_app="production",
        image=None,
        models=["one", "two"],
        executor_ip="192.0.2.25",
        prior_metadata=private / "prior.json",
    )


def approve_mock(private: Path) -> Path:
    path = private / "approval.json"
    h.create(
        path,
        {
            "packet_sha256": h.file_hash(private / "prepared.json"),
            "verdict": "approved",
            "independent_reviewer": "synthetic-reviewer",
            "m1_closed": True,
            "liability_reserved_outside_production": True,
            "staged_fenced_completion_accepted": True,
            "liability_disposition": "disjoint",
        },
    )
    return path


def test_full_program_no_overlap_no_reset_no_production_mutation(
    private: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = mocked_program(private, monkeypatch)
    h.prepare(args)
    approval = approve_mock(private)
    expected = FakeAzure.instances["test"].balances.copy()

    def dispatch(_origin: str, _key: str, case: dict[str, Any], observed: Path) -> dict[str, Any]:
        # Slot must be fsynced before HTTP; never infer consumption from a later result.
        assert observed.with_name(observed.stem.replace("observed", "consumed") + ".json").exists()
        azure = FakeAzure.instances["test"]
        debit = 0.00006
        azure.balances[case["group"]]["estimated_remaining_usd"] -= debit
        azure.balances[case["group"]]["debited_usd_total"] += debit
        result = {"usage": terminal()["usage"], "completed": True, "http_status": 200}
        h.create(observed, result)
        return result

    monkeypatch.setattr(h, "dispatch", dispatch)
    h.apply(argparse.Namespace(artifact_dir=private, approval=approval))
    assert len(list(private.glob("case-*-passed.json"))) == 4
    assert (private / "restart-passed.json").exists()
    assert FakeAzure.instances["production"].calls == []
    assert FakeAzure.instances["test"].balances["one"]["estimated_remaining_usd"] < 100
    assert expected["two"]["recovered_debit_usd_total"] == 0
    assert h.read_json(private / "results.json")["ingress"] == "fenced"
    # No ledger/slot replay even if a fresh process attempts apply again.
    with pytest.raises((h.RefusalError, FileExistsError)):
        h.apply(argparse.Namespace(artifact_dir=private, approval=approval))


def test_apply_uncertain_http_stops_before_later_slots_and_restart(
    private: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = mocked_program(private, monkeypatch)
    h.prepare(args)
    approval = approve_mock(private)
    monkeypatch.setattr(
        h, "dispatch", lambda *_args: (_ for _ in ()).throw(httpx.ReadTimeout("uncertain"))
    )
    with pytest.raises(httpx.ReadTimeout):
        h.apply(argparse.Namespace(artifact_dir=private, approval=approval))
    assert (private / "consumed.json").exists()
    assert (private / "case-0-consumed.json").exists()
    assert not (private / "case-1-consumed.json").exists()
    assert not (private / "restart-consumed.json").exists()
    assert h.read_json(private / "program-ledger.json")["phase1_reserved_usd"] > 0


def test_source_manifest_drift_and_immutable_image(
    private: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = private / "source"
    runtime = root / "src/foundry_router"
    runtime.mkdir(parents=True)
    for path in (runtime / "runtime.py", root / "Dockerfile", root / "pyproject.toml"):
        path.write_text("synthetic")
    (root / "tests/unit").mkdir(parents=True)
    (root / "tests/unit/test_table_production_acceptance.py").write_text("synthetic tests")
    monkeypatch.setattr(h, "ROOT", root)
    image = "synthetic@sha256:" + "a" * 64
    hashes = {
        str(path.relative_to(root)): h.file_hash(path)
        for path in (runtime / "runtime.py", root / "Dockerfile", root / "pyproject.toml")
    }
    metadata = private / "prior.json"
    h.create(
        metadata, {"image": image, "source_hashes": hashes, "historical_ledger": "never replay"}
    )
    assert h.source_binding(metadata, image)["source_hashes"] == hashes
    (runtime / "runtime.py").write_text("drift")
    with pytest.raises(h.RefusalError, match="differs"):
        h.source_binding(metadata, image)


def test_waits_bounded_and_replacement_is_actual(monkeypatch: pytest.MonkeyPatch) -> None:
    azure = h.Azure("synthetic", "rg", "test")
    writer = {
        "name": "new",
        "properties": {
            "containers": [
                {"ready": True, "started": True, "containerId": "new-container", "restartCount": 0}
            ]
        },
    }
    monkeypatch.setattr(azure, "writers", lambda **_kwargs: [writer])
    h.wait_writers(azure)
    h.wait_replacement(azure, snapshot())
    monkeypatch.setattr(h, "POLL_SECONDS", 0)
    with pytest.raises(h.RefusalError):
        h.wait_writers(azure, absent=True)
    with pytest.raises(h.RefusalError):
        h.wait_replacement(azure, snapshot())


def test_usage_artifact_drops_arbitrary_strings() -> None:
    data = terminal()
    data["usage"]["output"] = "secret-output"
    data["usage"]["input_tokens_details"]["cached_tokens"] = "secret-cache"
    result = h.response_usage(data)
    assert "secret" not in json.dumps(result)
    assert result["input_tokens_details"]["cached_tokens"] is None


@pytest.mark.parametrize("mutation", ["budget", "attempts", "nan", "phase"])
def test_global_packet_budget_guards(mutation: str) -> None:
    packet = {
        "phase": "G1",
        "program_limit_usd": 1,
        "program_attempts": 16,
        "phase_attempts": 4,
        "cases": [{"reserve_usd": 0.1}] * 4,
        "phase_reserved_usd": 0.4,
    }
    h.validate_packet_budget(packet)
    if mutation == "budget":
        packet["phase_reserved_usd"] = 2
    elif mutation == "attempts":
        packet["phase_attempts"] = 5
    elif mutation == "nan":
        packet["cases"] = [{"reserve_usd": float("nan")}] * 4
    else:
        packet["phase"] = "production"
    with pytest.raises(h.RefusalError):
        h.validate_packet_budget(packet)


def test_successor_preserves_tables_identity_and_all_other_config() -> None:
    old, new = app(), app()
    new["properties"]["configuration"]["ingress"]["ipSecurityRestrictions"] = h.DENY
    new["properties"]["template"]["scale"]["minReplicas"] = 1
    new["properties"]["template"]["containers"][0]["env"].append(
        {"name": "FOUNDRY_RETRY_ATTEMPTS", "value": "0"}
    )
    h.verify_successor(old, new, new["properties"]["template"]["containers"][0]["image"])
    new["identity"] = {"type": "changed"}
    with pytest.raises(h.RefusalError, match="identity"):
        h.verify_successor(old, new, new["properties"]["template"]["containers"][0]["image"])


def test_pty_snapshot_is_bounded_redacted_and_targeted(monkeypatch: pytest.MonkeyPatch) -> None:
    azure = h.Azure("synthetic-subscription", "synthetic-rg", "test")
    writer = {
        "name": "replica",
        "revision": "old",
        "properties": {
            "containers": [
                {"ready": True, "started": True, "containerId": "container", "restartCount": 0}
            ]
        },
    }
    monkeypatch.setattr(azure, "writers", lambda **_kwargs: [writer])
    command: list[str] = []

    class Process:
        stopped = False

        def poll(self) -> int | None:
            return 0 if self.stopped else None

        def terminate(self) -> None:
            self.stopped = True

        def wait(self, timeout: int) -> int:
            assert timeout == 3
            return 0

    def popen(arguments: list[str], **_kwargs: Any) -> Process:
        command.extend(arguments)
        return Process()

    monkeypatch.setattr(h.subprocess, "Popen", popen)
    monkeypatch.setattr(h.select, "select", lambda *_args: ([1], [], []))
    monkeypatch.setattr(
        h.os, "read", lambda *_args: b"G1_SNAPSHOT:" + json.dumps(snapshot()).encode() + b"\r\n"
    )
    result = h.local_snapshot(azure, app())
    assert result["generation"] == ["replica", "container", 0]
    assert command[command.index("--subscription") + 1] == "synthetic-subscription"
    assert command[command.index("--revision") + 1] == "old"
    assert command[command.index("--replica") + 1] == "replica"
    assert "synthetic-admin" not in " ".join(command)
    exec_command = command[command.index("--command") + 1]
    encoded = exec_command.split("b64decode('", 1)[1].split("')", 1)[0]
    assert exec_command == (
        "python -c \"exec(__import__('zlib').decompress(__import__('base64').b64decode('"
        + encoded
        + "')))\""
    )
    assert h.zlib.decompress(h.base64.b64decode(encoded)) == h.SNAPSHOT_PROGRAM.encode()
    assert len(exec_command) <= 1800  # Local regression bound, not an Azure platform limit.
    assert "FOUNDRY_ADMIN_API_KEYS_JSON" not in exec_command
    monkeypatch.setattr(h.os, "read", lambda *_args: b"G1_SNAPSHOT:{}\nG1_SNAPSHOT:{}\n")
    with pytest.raises(h.RefusalError, match="unique"):
        h.local_snapshot(azure, app())


@pytest.mark.parametrize("next_case", [0, 1])
@pytest.mark.parametrize(
    "mutation",
    [
        "debit",
        "increase",
        "other_debit",
        "other_increase",
        "cycle",
        "other_cycle",
        "membership",
        "recovery",
    ],
)
def test_financial_drift_refused_before_next_slot(
    private: Path, monkeypatch: pytest.MonkeyPatch, next_case: int, mutation: str
) -> None:
    args = mocked_program(private, monkeypatch)
    h.prepare(args)
    approval = approve_mock(private)
    snapshot_count, dispatch_count = 0, 0

    def diagnostic(azure: FakeAzure, _app: dict[str, Any]) -> dict[str, Any]:
        nonlocal snapshot_count
        if azure.ticks == "20":
            snapshot_count += 1
            if snapshot_count == 2 + next_case * 2:
                group = "two" if mutation.startswith("other_") else "one"
                if "cycle" in mutation:
                    azure.balances[group]["current_cycle_start_utc"] = "unexplained-next-cycle"
                elif mutation == "membership":
                    del azure.balances["two"]
                elif mutation == "recovery":
                    azure.balances[group]["recovered_debit_usd_total"] += 0.01
                else:
                    delta = 0.01 if "increase" in mutation else -0.01
                    azure.balances[group]["estimated_remaining_usd"] += delta
        return azure.snapshot()

    def dispatch(_origin: str, _key: str, case: dict[str, Any], observed: Path) -> dict[str, Any]:
        nonlocal dispatch_count
        dispatch_count += 1
        azure = FakeAzure.instances["test"]
        azure.balances[case["group"]]["estimated_remaining_usd"] -= 0.00006
        azure.balances[case["group"]]["debited_usd_total"] += 0.00006
        result = {"usage": terminal()["usage"], "completed": True, "http_status": 200}
        h.create(observed, result)
        return result

    monkeypatch.setattr(h, "local_snapshot", diagnostic)
    monkeypatch.setattr(h, "dispatch", dispatch)
    with pytest.raises(h.RefusalError, match="Persisted account state changed"):
        h.apply(argparse.Namespace(artifact_dir=private, approval=approval))
    assert dispatch_count == next_case
    assert not (private / f"case-{next_case}-consumed.json").exists()
    assert not (private / "restart-consumed.json").exists()


def test_public_get_normal_response_has_absolute_and_inactivity_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = httpx.AsyncClient
    calls = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/health/ready"
        return httpx.Response(200, json={"ready": True})

    def client(**kwargs: Any) -> httpx.AsyncClient:
        assert kwargs["timeout"] == 60
        assert not kwargs["trust_env"] and not kwargs["follow_redirects"]
        return original(transport=httpx.MockTransport(transport), **kwargs)

    monkeypatch.setattr(h.httpx, "AsyncClient", client)
    status, body = h.get_public("https://synthetic.example", "/health/ready")
    assert status == 200 and json.loads(body)["ready"]
    assert calls == 1


def test_public_get_trickle_expires_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    original = httpx.AsyncClient
    calls, chunks = 0, 0

    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            nonlocal chunks
            while True:
                await asyncio.sleep(0.005)
                chunks += 1
                yield b" "

    def transport(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, stream=Trickle())

    monkeypatch.setattr(h, "TIMEOUT", 0.04)
    monkeypatch.setattr(
        h.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    with pytest.raises(TimeoutError):
        h.get_public("https://synthetic.example", "/health/ready")
    assert calls == 1 and chunks >= 2


def test_prepare_cold_empty_workers_then_ready(
    private: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = mocked_program(private, monkeypatch)
    cold_reads = 0

    def writers(_self: FakeAzure, *, allow_none: bool = False) -> list[dict[str, Any]]:
        nonlocal cold_reads
        assert allow_none
        cold_reads += 1
        return (
            []
            if cold_reads == 1
            else [{"properties": {"containers": [{"ready": True, "started": True}]}}]
        )

    monkeypatch.setattr(FakeAzure, "writers", writers)
    h.prepare(args)
    assert cold_reads == 2
    assert (private / "prepared.json").exists()
    assert not args.program_ledger.exists()
    assert FakeAzure.instances["test"].calls == []


@pytest.mark.parametrize("failure", ["warm_deadline", "worker_deadline"])
def test_prepare_cold_deadline_leaves_no_packet_or_consumption(
    private: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    args = mocked_program(private, monkeypatch)
    if failure == "warm_deadline":
        monkeypatch.setattr(h, "get_public", lambda *_args: (_ for _ in ()).throw(TimeoutError()))
    else:
        monkeypatch.setattr(FakeAzure, "writers", lambda _self, **_kwargs: [])
        clock = iter([0, 0, 61])
        monkeypatch.setattr(h.time, "monotonic", lambda: next(clock))
    with pytest.raises((TimeoutError, h.RefusalError)):
        h.prepare(args)
    assert not (private / "prepared.json").exists()
    assert not (private / "consumed.json").exists()
    assert not args.program_ledger.exists()
    assert FakeAzure.instances["test"].calls == []


def test_completed_stream_stalled_eof_retains_only_terminal_evidence(
    private: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = httpx.AsyncClient
    wire = (
        b"data: "
        + json.dumps({"type": "response.completed", "response": terminal()}).encode()
        + b"\n\n"
    )

    class Stalled(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            yield wire[:7]
            yield wire[7:]
            await asyncio.sleep(1)

    calls = 0

    def transport(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, stream=Stalled())

    monkeypatch.setattr(h, "TIMEOUT", 0.04)
    monkeypatch.setattr(
        h.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    h.create(private / "slot-consumed.json", {"reserve_usd": 0.1})
    with pytest.raises(TimeoutError):
        h.dispatch(
            "https://synthetic.example",
            "synthetic",
            {"model": "one", "stream": True},
            private / "observed.json",
        )
    assert h.read_json(private / "observed-terminal.json")["clean_eof"] is False
    assert not (private / "observed.json").exists()
    assert (private / "slot-consumed.json").exists() and calls == 1


def test_unchanged_ready_container_rejected_over_poll_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    azure = h.Azure("synthetic", "rg", "test")
    writer = {
        "name": "replica",
        "properties": {
            "containers": [
                {"ready": True, "started": True, "containerId": "container", "restartCount": 0}
            ]
        },
    }
    polls = 0

    def writers(**_kwargs: Any) -> list[dict[str, Any]]:
        nonlocal polls
        polls += 1
        return [writer]

    monkeypatch.setattr(azure, "writers", writers)
    clock = iter([0, 0, 1, 181])
    monkeypatch.setattr(h.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(h.time, "sleep", lambda _seconds: None)
    with pytest.raises(h.RefusalError, match="replacement deadline"):
        h.wait_replacement(azure, snapshot())
    assert polls == 2


def test_main_literal_refusal_reason_is_actionable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [str(SCRIPT), "apply", "--artifact-dir", "/synthetic", "--approval", "/synthetic/approval"],
    )
    monkeypatch.setattr(
        h, "apply", lambda _: (_ for _ in ()).throw(h.RefusalError("Account not quiet"))
    )
    assert h.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "Account not quiet" and result["exception_type"] == "RefusalError"


@pytest.mark.parametrize("failure", ["incomplete", "unchanged_process"])
def test_orchestration_terminal_failure_and_noop_restart_cannot_pass(
    private: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    args = mocked_program(private, monkeypatch)
    h.prepare(args)
    approval = approve_mock(private)

    def dispatch(_origin: str, _key: str, case: dict[str, Any], observed: Path) -> dict[str, Any]:
        if failure == "incomplete":
            payload = terminal()
            payload["status"] = "incomplete"
            h.response_usage(payload)
        azure = FakeAzure.instances["test"]
        azure.balances[case["group"]]["estimated_remaining_usd"] -= 0.00006
        azure.balances[case["group"]]["debited_usd_total"] += 0.00006
        result = {"usage": terminal()["usage"], "completed": True, "http_status": 200}
        h.create(observed, result)
        return result

    monkeypatch.setattr(h, "dispatch", dispatch)
    original_command = FakeAzure.app_command

    def command(self: FakeAzure, arguments: list[str]) -> Any:
        if arguments[:2] == ["revision", "restart"]:
            return None
        return original_command(self, arguments)

    monkeypatch.setattr(FakeAzure, "app_command", command)
    with pytest.raises(h.RefusalError):
        h.apply(argparse.Namespace(artifact_dir=private, approval=approval))
    assert not (private / "results.json").exists()
    if failure == "incomplete":
        assert (private / "case-0-consumed.json").exists()
        assert not (private / "case-1-consumed.json").exists()
        assert not (private / "restart-consumed.json").exists()
    else:
        assert (private / "restart-consumed.json").exists()
        assert not (private / "restart-passed.json").exists()


def test_fragmented_failed_stream_retains_consumption_not_success(
    private: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = httpx.AsyncClient

    class Failed(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            yield b'data: {"type":"response.'
            yield b'failed"}\n\n'

    monkeypatch.setattr(
        h.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, stream=Failed())),
            **kwargs,
        ),
    )
    h.create(private / "slot-consumed.json", {"reserve_usd": 0.1})
    with pytest.raises(h.RefusalError, match="Failed SSE"):
        h.dispatch(
            "https://synthetic.example",
            "synthetic",
            {"model": "one", "stream": True},
            private / "observed.json",
        )
    assert (private / "observed-http.json").exists()
    assert not (private / "observed.json").exists()
    assert (private / "slot-consumed.json").exists()
