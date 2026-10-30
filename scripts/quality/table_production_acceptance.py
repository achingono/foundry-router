"""Phase 0/1 only: private read-only preparation and single-use isolated acceptance.

No production mutation, ledger replay, Table initialization, or balance reset exists here.
Run with the repository Python environment. Independent exact-packet review is mandatory.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import errno
import fcntl
import hashlib
import ipaddress
import json
import logging
import math
import os
import pty
import re
import select
import subprocess
import time
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit

import httpx

from foundry_router.config import Settings
from foundry_router.credit import estimate_request_cost_checked, estimate_response_usage_cost

ROOT = Path(__file__).resolve().parents[2]
MAX_OUTPUT = 128
MAX_INPUT = 64
MAX_BYTES = 4 * 1024 * 1024
TIMEOUT = 60
POLL_SECONDS = 180
TOLERANCE = 0.000002
OWNER_MODE = 0o700
MODEL_COUNT = 2
HTTP_OK = 200
HTTP_DENIED = 403
PROGRAM_ATTEMPTS = 16
PHASE_ATTEMPTS = 4
PROMPT = "Reply with one short word."
DENY = [{"name": "g1-fence", "ipAddressRange": "0.0.0.0/0", "action": "Deny"}]
Json = dict[str, Any]


class RefusalError(ValueError):
    """Sanitized fail-closed operational error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RefusalError(message)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Json:
    require(path.stat().st_size <= MAX_BYTES, "Artifact capacity exceeded")
    value = json.loads(path.read_text())
    require(isinstance(value, dict), "Object artifact required")
    return dict(value)


def private_directory(path: Path) -> None:
    require(path.is_absolute() and not path.is_symlink(), "Absolute nonsymlink directory required")
    require(path.is_dir(), "Caller must create approved artifact directory")
    info = path.stat()
    require(
        info.st_uid == os.getuid() and info.st_mode & 0o777 == OWNER_MODE,
        "Owner-only directory required",
    )
    require(not path.resolve().is_relative_to(ROOT), "Artifacts must remain outside repository")


def create(path: Path, value: Json) -> None:
    """Exclusive immutable record, fsynced before any associated operation."""
    private_directory(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class Azure:
    def __init__(self, subscription: str, resource_group: str, app: str):
        self.subscription, self.resource_group, self.app = subscription, resource_group, app

    def run(self, arguments: list[str]) -> Any:
        result = subprocess.run(
            ["az", *arguments, "--subscription", self.subscription, "-o", "json"],
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
        )
        require(result.returncode == 0, "Azure command unsuccessful; raw output withheld")
        require(len(result.stdout) <= MAX_BYTES, "Azure metadata capacity exceeded")
        return json.loads(result.stdout or b"null")

    def app_command(self, arguments: list[str]) -> Any:
        return self.run(["containerapp", *arguments, "-g", self.resource_group, "-n", self.app])

    def show(self) -> Json:
        return dict(self.app_command(["show"]))

    def writers(self, *, allow_none: bool = False) -> list[Json]:
        revisions = self.app_command(["revision", "list"])
        require(
            sum(revision["properties"].get("active") is True for revision in revisions) <= 1,
            "Overlapping active revisions",
        )
        writers: list[Json] = []
        for revision in revisions:
            replicas = self.app_command(["replica", "list", "--revision", revision["name"]])
            if replicas:
                require(
                    revision["properties"].get("active") is True, "Inactive revision has workers"
                )
            writers.extend({"revision": revision["name"], **replica} for replica in replicas)
        require(
            len(writers) == 1 or (allow_none and not writers), "Conflicting or missing replicas"
        )
        return writers

    def ingress(self, app_id: str, restrictions: list[Json]) -> None:
        self.run(
            [
                "rest",
                "--method",
                "patch",
                "--url",
                app_id + "?api-version=2024-03-01",
                "--body",
                json.dumps(
                    {
                        "properties": {
                            "configuration": {
                                "ingress": {
                                    "ipSecurityRestrictions": restrictions,
                                }
                            }
                        }
                    }
                ),
            ]
        )

    def secret(self, reference: str) -> str:
        parsed = urlsplit(reference)
        require(
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and (parsed.hostname or "").endswith(".vault.azure.net")
            and parsed.port is None
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and re.fullmatch(r"/secrets/[\w-]+/[a-fA-F0-9]{32}", parsed.path) is not None,
            "Version-pinned Key Vault secret required",
        )
        metadata = self.run(
            ["keyvault", "secret", "show", "--id", reference, "--query", "{id:id,value:value}"]
        )
        require(metadata["id"] == reference, "Secret version drift")
        return str(metadata["value"])


def resolve(azure: Azure, app: Json) -> tuple[dict[str, str], Json]:
    secrets = {item["name"]: item for item in app["properties"]["configuration"]["secrets"]}
    containers = app["properties"]["template"]["containers"]
    require(len(containers) == 1, "One container required")
    values, pins = {}, {}
    for item in containers[0]["env"]:
        name = item["name"]
        if "secretRef" in item:
            secret = secrets[item["secretRef"]]
            require(
                "value" not in secret and bool(secret.get("identity")),
                "Key Vault identity required",
            )
            reference = secret["keyVaultUrl"]
            value = azure.secret(reference)
            pins[name] = {
                "reference": reference,
                "identity": secret["identity"],
                "sha256": digest(value),
            }
        else:
            value = str(item.get("value", ""))
        values[name] = value
    return values, pins


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Any,
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        _ = settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


def settings_from(values: dict[str, str]) -> LocalSettings:
    fields: Json = {key: value for key, value in values.items() if key.startswith("FOUNDRY_")}
    return LocalSettings(**fields)


def projection(app: Json) -> Json:
    """Azure metadata binding without credential values or unredacted env."""
    result = json.loads(json.dumps(app))
    result.pop("systemData", None)
    result["properties"].pop("provisioningState", None)
    for container in result["properties"]["template"]["containers"]:
        for item in container.get("env", []):
            if "value" in item:
                item["value"] = {"sha256": digest(item["value"])}
    for secret in result["properties"]["configuration"].get("secrets", []):
        require("value" not in secret, "Inline app secret forbidden")
    return dict(result)


def validate_modes(app: Json, settings: Settings, *, production: bool = False) -> None:
    template = app["properties"]["template"]
    require(template["scale"]["maxReplicas"] == 1, "Maximum one replica required")
    require(
        app["properties"]["configuration"]["activeRevisionsMode"] == "Single",
        "Single revision mode required",
    )
    require(settings.state_backend == ("memory" if production else "table"), "State mode mismatch")
    require(
        settings.reconciliation_provider == "static" and settings.rate_limit_backend == "memory",
        "Unexpected reconciliation/quota mode",
    )
    require(not settings.telemetry_enabled, "Unexpected telemetry mode")
    ingress = app["properties"]["configuration"]["ingress"]
    require(
        ingress["external"] is True and ingress.get("allowInsecure") is not True,
        "Public HTTPS required",
    )
    container = template["containers"][0]
    require(
        not container.get("command") and not container.get("args"),
        "Default single worker entrypoint required",
    )
    if not production:
        require(
            not settings.protected_emergency_fallback, "Emergency fallback must remain disabled"
        )
        require(
            not settings.reconciliation_overrides_usd,
            "Reconciliation overrides could reset historical funds",
        )
        require(
            settings.table_credit_name != settings.table_health_name,
            "Distinct existing tables required",
        )


def verify_successor(original: Json, successor: Json, image: str) -> None:
    """Only reviewed image/retry/minimum changes may alter effective app configuration."""
    expected, actual = projection(original), projection(successor)
    expected_props, actual_props = expected["properties"], actual["properties"]
    expected_props["configuration"]["ingress"]["ipSecurityRestrictions"] = DENY
    expected_props["template"]["scale"]["minReplicas"] = 1
    container = expected_props["template"]["containers"][0]
    container["image"] = image
    env = {entry["name"]: entry for entry in container["env"]}
    env["FOUNDRY_RETRY_ATTEMPTS"] = {
        "name": "FOUNDRY_RETRY_ATTEMPTS",
        "value": {"sha256": digest("0")},
    }
    container["env"] = list(env.values())
    for props in (expected_props, actual_props):
        props["template"].pop("revisionSuffix", None)
        for candidate in props["template"]["containers"]:
            candidate["env"].sort(key=lambda entry: entry["name"])
    for key in ("identity", "location"):
        require(expected.get(key) == actual.get(key), "Successor identity/location drift")
    for key in ("configuration", "template", "environmentId", "managedEnvironmentId"):
        require(
            expected_props.get(key) == actual_props.get(key), "Successor app configuration drift"
        )


def source_binding(metadata: Path, image: str) -> Json:
    prior = read_json(
        metadata
    )  # Metadata only: never import/replay the historical executable or ledger.
    expected = prior["source_hashes"]
    actual_files = {
        str(path.relative_to(ROOT)) for path in (ROOT / "src/foundry_router").rglob("*.py")
    }
    require(
        set(expected) == actual_files | {"Dockerfile", "pyproject.toml"},
        "Incomplete source manifest",
    )
    require(
        prior["image"] == image and re.fullmatch(r"[^@]+@sha256:[a-f0-9]{64}", image) is not None,
        "Production immutable image provenance mismatch",
    )
    for name, sha in expected.items():
        require(file_hash(ROOT / name) == sha, "Source differs from deployed image")
    return {
        "source_hashes": expected,
        "metadata_sha256": file_hash(metadata),
        "script_sha256": file_hash(Path(__file__)),
        "tests_sha256": file_hash(ROOT / "tests/unit/test_table_production_acceptance.py"),
    }


def body_for(model: str, stream: bool) -> Json:
    return {"model": model, "input": PROMPT, "max_output_tokens": MAX_OUTPUT, "stream": stream}


def cases_for(settings: Settings, models: list[str]) -> list[Json]:
    require(
        len(models) == MODEL_COUNT and len(set(models)) == MODEL_COUNT,
        "Two distinct selected models required",
    )
    require(
        set(settings.models) == set(models) and not settings.model_aliases,
        "Exact isolated model pools required",
    )
    cases: list[Json] = []
    for model in models:
        pool = settings.models[model]
        require(
            len(pool.backends) == 1 and pool.streaming_enabled,
            "Single streaming-enabled backend required",
        )
        backend_id = next(iter(pool.backends))
        backend = settings.backends[backend_id]
        require(backend.credit_metered, "Metered test backend required")
        host = backend.endpoint.host or ""
        require(
            backend.provider == "azure_foundry"
            and bool(backend.deployment)
            and host.endswith((".openai.azure.com", ".services.ai.azure.com")),
            "Azure deployment required",
        )
        for stream in (False, True):
            estimate = estimate_request_cost_checked(
                model=model,
                operation="responses",
                body=body_for(model, stream),
                pricing=settings.pricing,
                settings=settings,
            )
            require(estimate is not None, "Missing current local estimate")
            assert estimate is not None
            price = settings.pricing[model]
            # Reserve 64 input tokens to cover uncertainty above the local heuristic.
            reserve = max(
                estimate.estimated_cost_usd,
                (MAX_INPUT * price.input_per_million + MAX_OUTPUT * price.output_per_million)
                / 1_000_000,
            )
            cases.append(
                {
                    "model": model,
                    "stream": stream,
                    "backend": backend_id,
                    "group": backend.credit_group or backend_id,
                    "host": host,
                    "pricing": price.model_dump(),
                    "local_estimate_usd": estimate.estimated_cost_usd,
                    "reserve_usd": reserve,
                }
            )
    require(sum(case["reserve_usd"] for case in cases) <= 1, "Program reservation exceeds USD 1")
    return cases


def dedicated_resources(azure: Azure, cases: list[Json], production: Settings) -> Json:
    production_hosts = {backend.endpoint.host for backend in production.backends.values()}
    test_hosts = {case["host"] for case in cases}
    require(test_hosts.isdisjoint(production_hosts), "Test inference account overlaps production")
    resources = azure.run(["cognitiveservices", "account", "list"])
    result = {}
    for host in test_hosts:
        matches = []
        for resource in resources:
            properties = resource["properties"]
            endpoints = [properties.get("endpoint", ""), *properties.get("endpoints", {}).values()]
            if host in {
                urlsplit(endpoint).hostname for endpoint in endpoints if isinstance(endpoint, str)
            }:
                matches.append(
                    {"id": resource["id"], "name": resource["name"], "kind": resource["kind"]}
                )
        require(len(matches) == 1, "Unique management resource endpoint mapping required")
        require(
            matches[0]["kind"] in {"OpenAI", "AIServices"},
            "Dedicated Azure inference resource required",
        )
        result[host] = matches[0]
    return result


def credential(values: dict[str, str], name: str) -> str:
    keys = json.loads(values[name])
    key = next(iter(keys.values())) if isinstance(keys, dict) else keys[0]
    require(isinstance(key, str) and bool(key), "Missing runtime credential")
    return str(key)


def get_public(origin: str, path: str, key: str | None = None) -> tuple[int, bytes]:
    return asyncio.run(get_public_async(origin, path, key))


async def get_public_async(origin: str, path: str, key: str | None = None) -> tuple[int, bytes]:
    # Absolute deadline covers headers and the complete body, even with continuous trickle traffic.
    async with (
        asyncio.timeout(TIMEOUT),
        httpx.AsyncClient(timeout=TIMEOUT, trust_env=False, follow_redirects=False) as client,
        client.stream(
            "GET", origin + path, headers={"Authorization": "Bearer " + key} if key else {}
        ) as response,
    ):
        payload = bytearray()
        async for chunk in response.aiter_bytes():
            payload.extend(chunk)
            require(len(payload) <= MAX_BYTES, "Public diagnostic capacity exceeded")
        return response.status_code, bytes(payload)


def accounts(admin: Json, *, legacy: bool = False) -> Json:
    result = {}
    for group, data in admin["credit_groups"].items():
        live = data["live"]
        require(
            live["active_reservations"] == 0 and live["reserved_inflight_usd"] == 0,
            "Account not quiet",
        )
        entry = {
            name: live[name] for name in ("estimated_remaining_usd", "current_cycle_start_utc")
        }
        for name in ("debited_usd_total", "recovered_debit_usd_total"):
            require(name in live or legacy, "Current ledger counters absent")
            entry[name] = live.get(name, 0)
        for name in ("estimated_remaining_usd", "debited_usd_total", "recovered_debit_usd_total"):
            require(
                type(entry[name]) in {int, float}
                and math.isfinite(entry[name])
                and entry[name] >= 0,
                "Invalid financial diagnostic",
            )
        result[group] = entry
    require(bool(result), "Missing canonical accounts")
    return result


SNAPSHOT_PROGRAM = r"""
import os,json,urllib.request,hashlib
keys=json.loads(os.environ['FOUNDRY_ADMIN_API_KEYS_JSON'])
key=next(iter(keys.values())) if isinstance(keys,dict) else keys[0]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(path):
    req=urllib.request.Request('http://127.0.0.1:8000'+path,headers={'Authorization':'Bearer '+key})
    with opener.open(req,timeout=10) as response:
        data=response.read(4194305)
        if len(data)>4194304: raise ValueError('capacity')
        return data
admin=json.loads(get('/admin/status'))
metrics=get('/metrics').decode()
request_counters=[line for line in metrics.splitlines()
                  if line.startswith('foundry_router_requests_total{')]
ready=json.loads(get('/health/ready'))
if ready.get('ready') is not True: raise ValueError('not ready')
out={'process_start_ticks':open('/proc/1/stat').read().split()[21],
     'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip(),
     'server_command_sha256':hashlib.sha256(open('/proc/1/cmdline','rb').read()).hexdigest(),
     'environment_sha256':{k:hashlib.sha256(v.encode()).hexdigest()
                           for k,v in os.environ.items() if k.startswith('FOUNDRY_')},
     'admin':{'credit_groups':admin['credit_groups'],'config':admin['config'],
              'models':admin['models'],'model_aliases':admin.get('model_aliases',{})},
     'metrics_sha256':hashlib.sha256(metrics.encode()).hexdigest(),
     'request_counters':request_counters,'ready':True}
print('G1_SNAPSHOT:'+json.dumps(out,separators=(',',':')),flush=True)
"""


def local_snapshot(azure: Azure, app: Json) -> Json:
    writer = azure.writers()[0]
    require(
        writer["revision"] == app["properties"]["latestReadyRevisionName"],
        "Exact ready revision required",
    )
    container = app["properties"]["template"]["containers"][0]["name"]
    command = (
        "python -c \"exec(__import__('zlib').decompress(__import__('base64').b64decode('"
        + base64.b64encode(zlib.compress(SNAPSHOT_PROGRAM.encode(), level=9)).decode()
        + "')))\""
    )
    arguments = [
        "az",
        "containerapp",
        "exec",
        "--subscription",
        azure.subscription,
        "-g",
        azure.resource_group,
        "-n",
        azure.app,
        "--revision",
        writer["revision"],
        "--replica",
        writer["name"],
        "--container",
        container,
        "--command",
        command,
    ]
    master, slave = pty.openpty()
    process = subprocess.Popen(
        arguments, stdin=slave, stdout=slave, stderr=slave, start_new_session=True
    )
    os.close(slave)
    payload = bytearray()
    deadline = time.monotonic() + TIMEOUT
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    require(error.errno == errno.EIO, "PTY read failure")
                    break
                if not chunk:
                    break
                payload.extend(chunk)
                require(len(payload) <= MAX_BYTES, "Snapshot capacity exceeded")
                if b"G1_SNAPSHOT:" in payload and b"\n" in payload.split(b"G1_SNAPSHOT:", 1)[1]:
                    break
            if process.poll() is not None:
                break
        else:
            raise RefusalError("Snapshot deadline")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        os.close(master)
    records = [
        line.split(b"G1_SNAPSHOT:", 1)[1]
        for line in payload.splitlines()
        if b"G1_SNAPSHOT:" in line
    ]
    require(len(records) == 1, "No unique structured snapshot; console withheld")
    return {
        **json.loads(records[0]),
        "revision": writer["revision"],
        "replica": writer["name"],
        "container": container,
        "generation": generation(writer),
    }


def generation(writer: Json) -> list[Any]:
    containers = writer["properties"]["containers"]
    require(len(containers) == 1, "One actual container required")
    container = containers[0]
    require(
        container.get("ready") is True
        and container.get("started") is True
        and bool(container.get("containerId"))
        and type(container.get("restartCount")) is int,
        "Ready container identity/restart count required",
    )
    return [writer["name"], container["containerId"], container["restartCount"]]


def wait_replacement(azure: Azure, before: Json) -> None:
    deadline = time.monotonic() + POLL_SECONDS
    while time.monotonic() < deadline:
        writers = azure.writers(allow_none=True)
        if writers:
            containers = writers[0]["properties"]["containers"]
            if len(containers) == 1 and containers[0].get("ready") and containers[0].get("started"):
                current = generation(writers[0])
                previous = before["generation"]
                if current[:2] != previous[:2] or current[2] > previous[2]:
                    return
        time.sleep(2)
    raise RefusalError("Actual replacement deadline")


def process_identity(snapshot: Json) -> tuple[Any, ...]:
    return tuple(snapshot[key] for key in ("revision", "replica", "boot_id", "process_start_ticks"))


def verify_environment(snapshot: Json, values: dict[str, str]) -> None:
    for name, value in values.items():
        if name.startswith("FOUNDRY_"):
            require(
                snapshot["environment_sha256"].get(name)
                == hashlib.sha256(value.encode()).hexdigest(),
                "Effective runtime environment drift",
            )


def wait_writers(
    azure: Azure, *, absent: bool = False, deadline_seconds: float | None = None
) -> None:
    deadline = time.monotonic() + (POLL_SECONDS if deadline_seconds is None else deadline_seconds)
    while time.monotonic() < deadline:
        writers = azure.writers(allow_none=True)
        if absent and not writers:
            return
        if not absent and writers:
            containers = writers[0].get("properties", {}).get("containers", [])
            if len(containers) == 1 and containers[0].get("ready") and containers[0].get("started"):
                return
        time.sleep(2)
    raise RefusalError("Writer transition deadline")


def unchanged(before: Json, after: Json) -> None:
    require(before == after, "Persisted account state changed")


def verify_debit(before: Json, after: Json, group: str, debit: float) -> None:
    require(set(before) == set(after), "Canonical membership drift")
    for name in before:
        old, new = before[name], after[name]
        if name != group:
            unchanged(old, new)
            continue
        require(old["current_cycle_start_utc"] == new["current_cycle_start_utc"], "Cycle changed")
        require(
            old["recovered_debit_usd_total"] == new["recovered_debit_usd_total"],
            "Unexpected recovery",
        )
        require(
            abs(old["estimated_remaining_usd"] - new["estimated_remaining_usd"] - debit)
            <= TOLERANCE
            and abs(new["debited_usd_total"] - old["debited_usd_total"] - debit) <= TOLERANCE,
            "Account debit/counter mismatch",
        )


def response_usage(payload: Json) -> Json:
    require(payload.get("status") == "completed", "Terminal completion required")
    usage = payload.get("usage", {})
    require(isinstance(usage, dict), "Terminal usage object required")
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        require(type(usage.get(name)) is int and usage[name] >= 0, "Invalid terminal usage")
    require(
        usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
        and usage["input_tokens"] <= MAX_INPUT
        and usage["output_tokens"] <= MAX_OUTPUT,
        "Usage exceeds reserved bounds",
    )
    numeric = {name: usage[name] for name in ("input_tokens", "output_tokens", "total_tokens")}
    for name in ("prompt_tokens", "completion_tokens"):
        if name in usage:
            numeric[name] = usage[name] if type(usage[name]) is int else None
    for name in ("input_tokens_details", "prompt_tokens_details"):
        if name in usage:
            details = usage[name]
            cached = details.get("cached_tokens") if isinstance(details, dict) else None
            numeric[name] = {"cached_tokens": cached if type(cached) is int else None}
    return numeric


def dispatch(origin: str, key: str, case: Json, observed: Path) -> Json:
    return asyncio.run(dispatch_async(origin, key, case, observed))


async def dispatch_async(origin: str, key: str, case: Json, observed: Path) -> Json:
    """Persist header status and numeric terminal observation before later diagnostics."""
    async with (
        asyncio.timeout(TIMEOUT),
        httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5), trust_env=False, follow_redirects=False
        ) as client,
        client.stream(
            "POST",
            origin + "/openai/v1/responses",
            headers={"Authorization": "Bearer " + key},
            json=body_for(case["model"], case["stream"]),
        ) as response,
    ):
        create(observed.with_name(observed.stem + "-http.json"), {"status": response.status_code})
        require(response.status_code == HTTP_OK, "Paid HTTP unsuccessful")
        total, buffer, terminal = 0, bytearray(), None
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            require(total <= MAX_BYTES, "Response capacity exceeded")
            buffer.extend(chunk)
            if case["stream"]:
                buffer[:] = buffer.replace(b"\r\n", b"\n")
                while b"\n\n" in buffer:
                    frame, remaining = buffer.split(b"\n\n", 1)
                    buffer[:] = remaining
                    data = b"\n".join(
                        line[5:].lstrip()
                        for line in frame.splitlines()
                        if line.startswith(b"data:")
                    )
                    if data and data != b"[DONE]":
                        event = json.loads(data)
                        require(isinstance(event, dict), "SSE object required")
                        require(
                            event.get("type")
                            not in {"error", "response.failed", "response.incomplete"},
                            "Failed SSE response",
                        )
                        if event.get("type") == "response.completed":
                            require(terminal is None, "Duplicate completion")
                            terminal = event["response"]
                            require(isinstance(terminal, dict), "SSE terminal object required")
                            create(
                                observed.with_name(observed.stem + "-terminal.json"),
                                {
                                    "terminal_observed": True,
                                    "usage": response_usage(terminal),
                                    "clean_eof": False,
                                },
                            )
        if case["stream"]:
            require(not buffer.strip() and terminal is not None, "Incomplete SSE boundary")
        else:
            terminal = json.loads(buffer)
        require(isinstance(terminal, dict), "Terminal object required")
        usage = response_usage(dict(terminal or {}))
        result = {"http_status": 200, "completed": True, "usage": usage}
        create(observed, result)
        return result


def prepare(args: argparse.Namespace) -> None:
    directory = args.artifact_dir
    private_directory(directory)
    private_directory(args.program_ledger.parent)
    require(not args.program_ledger.exists(), "New program ledger path required")
    azure = Azure(args.subscription, args.test_rg, args.test_app)
    production = Azure(args.subscription, args.production_rg, args.production_app)
    test_app, production_app = azure.show(), production.show()
    require(
        test_app["id"].casefold() != production_app["id"].casefold(), "Isolated target required"
    )
    test_values, test_pins = resolve(azure, test_app)
    production_values, production_pins = resolve(production, production_app)
    settings, production_settings = settings_from(test_values), settings_from(production_values)
    validate_modes(test_app, settings)
    validate_modes(production_app, production_settings, production=True)
    image = args.image or production_app["properties"]["template"]["containers"][0]["image"]
    require(
        image == production_app["properties"]["template"]["containers"][0]["image"],
        "Current production image required",
    )
    binding = source_binding(args.prior_metadata, image)
    cases = cases_for(settings, args.models)
    resources = dedicated_resources(azure, cases, production_settings)
    origin = "https://" + test_app["properties"]["configuration"]["ingress"]["fqdn"]
    # Prepare only: public readiness intake can cold-start min0 without configuration mutation
    # or inference. Exec cannot target a nonexistent replica; warm before snapshot discovery.
    warm_status, warm_body = get_public(origin, "/health/ready")
    require(warm_status == HTTP_OK, "Prepare readiness warm unsuccessful")
    warm_ready = json.loads(warm_body)
    require(
        isinstance(warm_ready, dict) and warm_ready.get("ready") is True,
        "Prepare readiness warm incomplete",
    )
    wait_writers(azure, deadline_seconds=TIMEOUT)
    test_app = azure.show()
    original = local_snapshot(azure, test_app)
    verify_environment(original, test_values)
    balances = accounts(original["admin"], legacy=True)
    status, payload = get_public(
        origin, "/admin/status", credential(test_values, "FOUNDRY_ADMIN_API_KEYS_JSON")
    )
    require(status == HTTP_OK, "Public admin baseline unavailable")
    unchanged(balances, accounts(json.loads(payload), legacy=True))
    require(get_public(origin, "/admin/status")[0] in {401, 403}, "Public admin auth not enforced")
    packet = {
        "phase": "G1",
        "subscription": args.subscription,
        "test_rg": args.test_rg,
        "test_app": args.test_app,
        "production_rg": args.production_rg,
        "production_app": args.production_app,
        "image": image,
        "binding": binding,
        "prior_metadata": str(args.prior_metadata),
        "test_projection": projection(test_app),
        "production_projection": projection(production_app),
        "test_pins": test_pins,
        "production_pins": production_pins,
        "original_snapshot": original,
        "original_accounts": balances,
        "original_ingress": test_app["properties"]["configuration"]["ingress"],
        "original_min": test_app["properties"]["template"]["scale"]["minReplicas"],
        "origin": origin,
        "cases": cases,
        "executor_ip": str(ipaddress.IPv4Address(args.executor_ip)),
        "program_ledger": str(args.program_ledger),
        "program_limit_usd": 1,
        "program_attempts": 16,
        "phase_attempts": 4,
        "phase_reserved_usd": sum(case["reserve_usd"] for case in cases),
        "tables": {
            "credit": settings.table_credit_name,
            "health": settings.table_health_name,
            "endpoint": settings.table_endpoint,
        },
        "drain_seconds": settings.intake_timeout_seconds + 60 + 10,
        "dedicated_test_resources": resources,
        "production_hosts_disjoint": True,
        "production_account_coverage": "None; dedicated test resources only",
        "liability_disposition": (
            "Fresh exclusive USD 1 program on disjoint test resources; historical seed is not funds"
        ),
    }
    require(
        packet["drain_seconds"] <= POLL_SECONDS, "Drain period needs reviewed deadline amendment"
    )
    create(directory / "prepared.json", packet)
    print(
        json.dumps(
            {
                "status": "prepared_not_approved",
                "packet_sha256": file_hash(directory / "prepared.json"),
                "phase_reserved_usd": packet["phase_reserved_usd"],
                "dedicated_test_resources": resources,
                "production_account_coverage": "None",
            }
        )
    )


def approved(packet_path: Path, approval_path: Path) -> Json:
    approval = read_json(approval_path)
    require(
        approval.get("packet_sha256") == file_hash(packet_path)
        and approval.get("verdict") == "approved"
        and bool(approval.get("independent_reviewer"))
        and approval.get("m1_closed") is True
        and approval.get("liability_reserved_outside_production") is True
        and approval.get("staged_fenced_completion_accepted") is True
        and bool(approval.get("liability_disposition")),
        "Fresh independent exact packet approval required",
    )
    return approval


def validate_packet_budget(packet: Json) -> None:
    require(
        packet["phase"] == "G1"
        and packet["program_limit_usd"] == 1
        and packet["program_attempts"] == PROGRAM_ATTEMPTS
        and packet["phase_attempts"] == PHASE_ATTEMPTS
        and len(packet["cases"]) == PHASE_ATTEMPTS,
        "Fixed G1 program bounds required",
    )
    amounts = [case["reserve_usd"] for case in packet["cases"]]
    require(
        all(
            type(amount) in {int, float} and math.isfinite(amount) and amount >= 0
            for amount in amounts
        ),
        "Invalid program reservation",
    )
    require(
        sum(amounts) == packet["phase_reserved_usd"] and sum(amounts) <= 1, "Program budget drift"
    )


def apply(args: argparse.Namespace) -> None:  # noqa: PLR0915 -- explicit single-use operational sequence
    directory = args.artifact_dir
    private_directory(directory)
    packet_path = directory / "prepared.json"
    packet = read_json(packet_path)
    validate_packet_budget(packet)
    approval = approved(packet_path, args.approval)
    azure = Azure(packet["subscription"], packet["test_rg"], packet["test_app"])
    production = Azure(packet["subscription"], packet["production_rg"], packet["production_app"])
    require(
        source_binding(Path(packet["prior_metadata"]), packet["image"]) == packet["binding"],
        "Helper/source drift",
    )
    app, prod = azure.show(), production.show()
    require(
        projection(app) == packet["test_projection"]
        and projection(prod) == packet["production_projection"],
        "Live metadata drift",
    )
    values, pins = resolve(azure, app)
    require(
        cases_for(
            settings_from(values), list(dict.fromkeys(case["model"] for case in packet["cases"]))
        )
        == packet["cases"],
        "Bound model/pricing contract drift",
    )
    _, prod_pins = resolve(production, prod)
    require(
        pins == packet["test_pins"] and prod_pins == packet["production_pins"],
        "Secret version/value drift",
    )
    require(
        dedicated_resources(azure, packet["cases"], settings_from(resolve(production, prod)[0]))
        == packet["dedicated_test_resources"],
        "Dedicated account resource drift",
    )
    initial = local_snapshot(azure, app)
    verify_environment(initial, values)
    require(
        process_identity(initial) == process_identity(packet["original_snapshot"]),
        "Old process drift",
    )
    unchanged(accounts(initial["admin"], legacy=True), packet["original_accounts"])
    ledger = Path(packet["program_ledger"])
    private_directory(ledger.parent)
    with (directory / "execution.lock").open("a+b") as lock:
        (directory / "execution.lock").chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Neither ledger nor execution marker can ever be replayed, even after uncertain failure.
        create(
            ledger,
            {
                "packet_sha256": file_hash(packet_path),
                "limit_usd": 1,
                "attempt_limit": 16,
                "phase1_slots": packet["cases"],
                "phase1_reserved_usd": packet["phase_reserved_usd"],
                "approval_sha256": digest(approval),
            },
        )
        create(directory / "consumed.json", {"packet_sha256": file_hash(packet_path)})
        azure.ingress(app["id"], DENY)
        require(
            get_public(packet["origin"], "/health/ready")[0] == HTTP_DENIED, "Fence denial unproved"
        )
        fenced = local_snapshot(azure, azure.show())
        require(process_identity(fenced) == process_identity(initial), "Fence replaced old process")
        time.sleep(packet["drain_seconds"])
        drained = local_snapshot(azure, azure.show())
        require(process_identity(drained) == process_identity(initial), "Drain process changed")
        unchanged(accounts(drained["admin"], legacy=True), packet["original_accounts"])
        require(
            drained["request_counters"] == fenced["request_counters"],
            "Requests changed during drain",
        )
        create(directory / "old-drained.json", drained)
        create(directory / "stop-consumed.json", {"revision": initial["revision"]})
        azure.app_command(["revision", "deactivate", "--revision", initial["revision"]])
        wait_writers(azure, absent=True)
        require(
            not any(
                revision["properties"].get("active")
                for revision in azure.app_command(["revision", "list"])
            ),
            "Old revision still active",
        )
        create(directory / "old-writers-absent.json", {"verified": True})
        create(directory / "update-consumed.json", {"image": packet["image"]})
        azure.app_command(
            [
                "update",
                "--image",
                packet["image"],
                "--min-replicas",
                "1",
                "--max-replicas",
                "1",
                "--set-env-vars",
                "FOUNDRY_RETRY_ATTEMPTS=0",
            ]
        )
        wait_writers(azure)
        successor = azure.show()
        verify_successor(app, successor, packet["image"])
        current_values, current_pins = resolve(azure, successor)
        expected_values = {**values, "FOUNDRY_RETRY_ATTEMPTS": "0"}
        require(
            current_values == expected_values and current_pins == pins,
            "Successor configuration drift",
        )
        validate_modes(successor, settings_from(current_values))
        require(
            successor["properties"]["template"]["containers"][0]["image"] == packet["image"],
            "Successor image drift",
        )
        baseline = local_snapshot(azure, successor)
        verify_environment(baseline, current_values)
        require(baseline["admin"]["config"]["retry_attempts"] == 0, "Effective retries not zero")
        unchanged(accounts(baseline["admin"]), packet["original_accounts"])
        create(directory / "successor-baseline.json", baseline)
        allow = [
            {
                "name": "g1-executor",
                "ipAddressRange": packet["executor_ip"] + "/32",
                "action": "Allow",
            }
        ]
        azure.ingress(app["id"], allow)
        require(
            get_public(packet["origin"], "/health/ready")[0] == HTTP_OK,
            "Executor ingress unavailable",
        )
        settings = settings_from(current_values)
        last_accounts = accounts(baseline["admin"])
        for index, case in enumerate(packet["cases"]):
            before = local_snapshot(azure, azure.show())
            require(process_identity(before) == process_identity(baseline), "Paid worker changed")
            verify_environment(before, current_values)
            before_accounts = accounts(before["admin"])
            unchanged(last_accounts, before_accounts)
            create(
                directory / f"case-{index}-consumed.json",
                {"reserve_usd": case["reserve_usd"], "attempts": 1},
            )
            result = dispatch(
                packet["origin"],
                credential(current_values, "FOUNDRY_CLIENT_API_KEYS_JSON"),
                case,
                directory / f"case-{index}-observed.json",
            )
            debit = estimate_response_usage_cost(
                SimpleNamespace(
                    body=json.dumps({"usage": result["usage"]}).encode(),
                    headers={"content-type": "application/json"},
                ),
                case["model"],
                settings.pricing,
            )
            require(
                debit is not None and debit <= case["reserve_usd"], "Debit exceeds slot reservation"
            )
            assert debit is not None
            after = local_snapshot(azure, azure.show())
            require(
                process_identity(after) == process_identity(baseline), "Settlement worker changed"
            )
            after_accounts = accounts(after["admin"])
            verify_debit(before_accounts, after_accounts, case["group"], debit)
            last_accounts = after_accounts
            create(
                directory / f"case-{index}-passed.json",
                {"debit_usd": debit, "accounts": accounts(after["admin"])},
            )
        azure.ingress(app["id"], DENY)
        require(
            get_public(packet["origin"], "/health/ready")[0] == HTTP_DENIED,
            "Restart fence unproved",
        )
        time.sleep(packet["drain_seconds"])
        final = local_snapshot(azure, azure.show())
        require(process_identity(final) == process_identity(baseline), "Pre-restart worker changed")
        unchanged(accounts(final["admin"]), last_accounts)
        require(
            final["request_counters"] == after["request_counters"],
            "Requests changed during restart drain",
        )
        create(directory / "restart-consumed.json", final)
        azure.app_command(["revision", "restart", "--revision", final["revision"]])
        wait_replacement(azure, final)
        restarted = local_snapshot(azure, azure.show())
        require(
            process_identity(restarted) != process_identity(final), "No actual worker replacement"
        )
        verify_environment(restarted, current_values)
        unchanged(accounts(final["admin"]), accounts(restarted["admin"]))
        create(directory / "restart-passed.json", restarted)
        # Restoring min creates a revision: review separately, never reactivate stale writers.
        create(
            directory / "results.json",
            {
                "g1_four_calls_and_restart": "passed",
                "ingress": "fenced",
                "min_replicas": 1,
                "original_min": packet["original_min"],
                "restoration": "Separate independently reviewed exact restoration required",
            },
        )
        print(json.dumps({"status": "g1_passed_fenced_restoration_pending"}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="phase", required=True)
    prep = sub.add_parser("prepare")
    for option in (
        "subscription",
        "test-rg",
        "test-app",
        "production-rg",
        "production-app",
        "executor-ip",
    ):
        prep.add_argument("--" + option, required=True)
    prep.add_argument("--models", nargs=2, required=True)
    prep.add_argument("--image")
    prep.add_argument("--prior-metadata", type=Path, required=True)
    prep.add_argument("--program-ledger", type=Path, required=True)
    prep.add_argument("--artifact-dir", type=Path, required=True)
    execution = sub.add_parser("apply")
    execution.add_argument("--artifact-dir", type=Path, required=True)
    execution.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args()
    prior_logging = logging.root.manager.disable
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
                    "status": "stopped_unverified",
                    "exception_type": type(error).__name__,
                    "reason": str(error) if isinstance(error, RefusalError) else "Details withheld",
                    "recovery": "Read-only inspection; no replay or rollback",
                }
            )
        )
        return 2
    finally:
        logging.disable(prior_logging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
