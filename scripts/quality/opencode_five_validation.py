# ruff: noqa: TRY301 -- setup refusals are converted to redacted consumed-slot outcomes
"""Fixed eighteen-slot OpenCode rollout checks; durable no-replay evidence."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import httpx
import staging_validation as sv
from google_live_budget import locked, write_atomic

RUN = "opencode-zen-five-20261013"
GROUP = "opencode-account"
REPLACEMENT_RUN = "opencode-zen-five-20261013-model-status"
VERTEX_RUN = "opencode-zen-five-20261013-vertex-time"
NONSTREAM_RUN = "opencode-zen-five-20261013-gemini-nonstream"
ANTHROPIC_RUN = "opencode-zen-five-20261013-anthropic-nullable"
STREAMING_RUN = "opencode-zen-five-gemini-streaming-v1"
SUBSET_RUN = "opencode-zen-five-subset-20261014"
SUBSET2_RUN = "opencode-zen-five-subset2-20261014"
SUBSET_POOLS = frozenset({"gemini-3.8-flash-zen", "gemini-4-argon-zen", "claude-sonnet-5.5-zen"})
STAGE_SEEDS = {
    RUN: 0.1,
    REPLACEMENT_RUN: 0.095982,
    VERTEX_RUN: 0.095514,
    NONSTREAM_RUN: 0.09,
    ANTHROPIC_RUN: 0.088,
    STREAMING_RUN: 0.10,
    SUBSET_RUN: 0.09,
    SUBSET2_RUN: 0.085,
}
BOUND = 256 * 1024
HTTP_OK = 200
DIGEST_LENGTH = 64
IMAGE_LENGTH = 71
STAGING_SLOTS = 9
ROSTER = (
    ("gemini-3.8-flash-zen", "gemini-3.8-flash", "opencode_google", 1.5, 7.5, True),
    ("gemini-4-argon-zen", "gemini-4-argon", "opencode_google", 4.0, 20.0, True),
    ("claude-sonnet-5.5-zen", "claude-sonnet-5-5", "opencode_anthropic", 4.0, 10.0, False),
    ("grok-4.7-zen", "grok-4.7", "opencode_zen", 4.0, 12.0, True),
    ("muse-spark-1.3-zen", "muse-spark-1.3", "opencode_zen", 1.25, 4.25, True),
)
CASES = tuple(
    {
        "id": f"{env}-{index}-{'stream' if stream else 'nonstream'}",
        "environment": env,
        "pool": pool,
        "deployment": deployment,
        "provider": provider,
        "stream": stream,
        "input_per_million": pin,
        "output_per_million": pout,
        "streaming_enabled": enabled,
        "request": {
            "model": pool,
            "input": "Reply with the single word OK.",
            "max_output_tokens": 128 if not enabled else 512,
            "stream": stream,
            "store": False,
        },
    }
    for env in ("staging", "production")
    for index, (pool, deployment, provider, pin, pout, enabled) in enumerate(ROSTER)
    for stream in ((False, True) if enabled else (False,))
)


def fingerprint(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def cases_for(run_id: str) -> list[dict]:
    cases = copy.deepcopy(list(CASES))
    if run_id in {NONSTREAM_RUN, ANTHROPIC_RUN}:
        cases = [
            case for case in cases if not (case["provider"] == "opencode_google" and case["stream"])
        ]
        for case in cases:
            if case["provider"] == "opencode_google":
                case["streaming_enabled"] = False
    if run_id in {SUBSET_RUN, SUBSET2_RUN}:
        cases = [case for case in cases if case["pool"] in SUBSET_POOLS]
    return cases


def manifest(image: str, configurations: dict[str, str], *, run_id: str = RUN) -> dict:
    if run_id not in STAGE_SEEDS:
        raise ValueError("Unreviewed run identity")
    if not image.startswith("sha256:") or len(image) != IMAGE_LENGTH:
        raise ValueError("Immutable image digest required")
    if set(configurations) != {"staging", "production"} or any(
        len(v) != DIGEST_LENGTH for v in configurations.values()
    ):
        raise ValueError("Both configuration fingerprints required")
    cases = cases_for(run_id)
    return {
        "run": run_id,
        "image_digest": image,
        "configuration_fingerprints": configurations,
        "cases": cases,
        "request_hashes": [fingerprint(c["request"]) for c in cases],
        "case_timeout_seconds": 120,
        "max_dispatches": len(cases),
        "account_allocation_usd": 10.0,
        "staging_allocation_usd": STAGE_SEEDS[run_id],
        "production_seed_usd": 9.9,
        "reserve": {"min_credit_reserve_usd": 0.05, "min_credit_reserve_percent": 5.0},
    }


def initialize(directory: Path, specification: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    ledger = directory / "ledger.json"
    with locked(ledger):
        if any((directory / n).exists() for n in ("ledger.json", "identity.json", "manifest.json")):
            raise ValueError("Run already initialized; cannot reset or replay")
        expected = manifest(
            specification["image_digest"],
            specification["configuration_fingerprints"],
            run_id=specification["run"],
        )
        if specification != expected:
            raise ValueError("Unauthorized manifest")
        write_atomic(directory / "identity.json", {"manifest_sha256": fingerprint(specification)})
        write_atomic(directory / "manifest.json", specification)
        write_atomic(
            ledger,
            {
                "manifest_sha256": fingerprint(specification),
                "entries": [{"reserved": False, "result": None} for _ in specification["cases"]],
            },
        )


def read_state(directory: Path) -> tuple[dict, dict]:
    data = []
    for name in ("identity.json", "manifest.json", "ledger.json"):
        path = directory / name
        if not path.exists() or path.stat().st_size > BOUND:
            raise ValueError("Durable validation state unavailable")
        data.append(json.loads(path.read_text()))
    identity, specification, state = data
    expected = manifest(
        specification["image_digest"],
        specification["configuration_fingerprints"],
        run_id=specification["run"],
    )
    digest = fingerprint(specification)
    if (
        specification != expected
        or identity != {"manifest_sha256": digest}
        or state.get("manifest_sha256") != digest
    ):
        raise ValueError("Validation binding changed")
    entries = state.get("entries")
    if not isinstance(entries, list) or len(entries) != len(specification["cases"]):
        raise ValueError("Invalid validation entries")
    gap = False
    for case, entry in zip(specification["cases"], entries, strict=True):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"reserved", "result"}
            or type(entry["reserved"]) is not bool
        ):
            raise ValueError("Invalid validation entry")
        if entry["reserved"]:
            result = entry["result"]
            if gap or not isinstance(result, dict) or result.get("status") != "passed":
                raise ValueError("Reserved, failed or ambiguous slot cannot resume")
            validate_passed_result(case, result)
        else:
            gap = True
            if entry["result"] is not None:
                raise ValueError("Unreserved outcome refused")
    return specification, state


def validate_passed_result(case: dict, result: dict) -> None:
    expected_keys = {
        "id",
        "status",
        "http_status",
        "input_tokens",
        "output_tokens",
        "estimated_debit_usd",
        "reservations_cleared",
        "error_category",
    }
    if (
        set(result) != expected_keys
        or result["id"] != case["id"]
        or result["http_status"] != HTTP_OK
        or result["reservations_cleared"] is not True
        or result["error_category"] is not None
    ):
        raise ValueError("Invalid prior acceptance flags")
    pin, pout, cost = result["input_tokens"], result["output_tokens"], result["estimated_debit_usd"]
    if (
        type(pin) is not int
        or pin < 0
        or type(pout) is not int
        or not 0 < pout <= case["request"]["max_output_tokens"]
        or type(cost) not in {int, float}
        or not math.isfinite(cost)
        or cost < 0
    ):
        raise ValueError("Invalid prior acceptance numerics")
    expected = (pin * case["input_per_million"] + pout * case["output_per_million"]) / 1_000_000
    if not math.isclose(cost, expected, rel_tol=1e-6, abs_tol=1e-9):
        raise ValueError("Invalid prior acceptance debit")


def policy_projection(admin: dict) -> dict:
    """Only configuration, not process counters or changing account estimates."""
    return {
        "models": admin["models"],
        "aliases": admin.get("model_aliases", {}),
        "backends": {
            k: {
                f: v.get(f)
                for f in (
                    "provider",
                    "api_surface",
                    "deployment",
                    "endpoint",
                    "supported_operations",
                    "google_features",
                    "credit_group",
                )
            }
            for k, v in admin["backends"].items()
        },
        "accounts": {
            k: {
                f: v[f]
                for f in (
                    (
                        "reserve_policy",
                        "cycle_start_day",
                        "cycle_allowance_usd",
                        "initial_estimated_remaining_usd",
                    )
                    if k == GROUP
                    else ("reserve_policy", "cycle_start_day", "cycle_allowance_usd")
                )
            }
            for k, v in admin["credit_groups"].items()
        },
    }


async def read_admin(client: httpx.AsyncClient, key: str) -> dict:
    status, data = await sv._read_bounded_json(
        client, "GET", "/admin/status", headers={"x-admin-key": key}, max_bytes=BOUND
    )
    if status != HTTP_OK or data is None:
        raise ValueError("Admin binding unavailable")
    for group in data["credit_groups"].values():
        live = group["live"]
        if live["active_reservations"] != 0 or live["reserved_inflight_usd"] != 0:
            raise ValueError("Writer is not drained")
    return data


async def run_case(  # noqa: PLR0913 -- explicit reviewed live inputs
    case: dict,
    specification: dict,
    *,
    base_url: str,
    caller: str,
    admin: str,
    transport: Any = None,
) -> dict:
    result = {
        "id": case["id"],
        "status": "failed",
        "http_status": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_debit_usd": None,
        "reservations_cleared": False,
        "error_category": "acceptance",
    }
    try:
        async with (
            asyncio.timeout(120),
            httpx.AsyncClient(
                base_url=base_url, timeout=30, trust_env=False, transport=transport
            ) as client,
        ):
            before = await read_admin(client, admin)
            if (
                fingerprint(policy_projection(before))
                != specification["configuration_fingerprints"][case["environment"]]
            ):
                raise ValueError("Configured deployment binding changed")
            pool = before["models"][case["pool"]]
            backend = before["backends"][next(iter(pool["backends"]))]
            if (
                len(pool["backends"]) != 1
                or backend["provider"] != case["provider"]
                or backend["deployment"] != case["deployment"]
                or backend["credit_group"] != GROUP
                or pool["streaming_enabled"] != case["streaming_enabled"]
            ):
                raise ValueError("Exact model binding changed")
            if case["stream"]:
                status, body = await sv._read_stream_terminal(client, caller, case["request"])
            else:
                status, body = await sv._read_bounded_json(
                    client,
                    "POST",
                    "/openai/v1/responses",
                    headers={"api-key": caller},
                    json_body=case["request"],
                    max_bytes=sv.MAX_RESPONSE_BYTES,
                )
            result["http_status"] = status
            after = await read_admin(client, admin)
            if fingerprint(policy_projection(after)) != fingerprint(policy_projection(before)):
                raise ValueError("Configuration changed during case")
            usage = sv._public_usage(body)
            first = before["credit_groups"][GROUP]["live"]["estimated_remaining_usd"]
            last = after["credit_groups"][GROUP]["live"]["estimated_remaining_usd"]
            result["estimated_debit_usd"] = first - last
            result["reservations_cleared"] = True
            if usage is not None:
                result["input_tokens"], result["output_tokens"] = usage
            if (
                status != HTTP_OK
                or usage is None
                or not sv._public_completed(body)
                or not sv._public_text_present(body)
            ):
                return result
            expected = (
                usage[0] * case["input_per_million"] + usage[1] * case["output_per_million"]
            ) / 1_000_000
            if not math.isclose(first - last, expected, rel_tol=1e-6, abs_tol=1e-9):
                return result
            result.update(status="passed", error_category=None)
            validate_passed_result(case, result)
    except (TimeoutError, ValueError, KeyError, TypeError, httpx.HTTPError):
        # Keep only redacted category; consumed slots remain durable and block replay.
        result["status"] = "failed"
        result["error_category"] = "setup_or_transport"
    return result


async def execute(  # noqa: PLR0913 -- explicit reviewed live inputs
    environment: str,
    *,
    directory: Path,
    image: str,
    base_url: str,
    caller: str,
    admin: str,
    transport: Any = None,
) -> dict:
    if environment not in {"staging", "production"}:
        raise ValueError("Unknown validation environment")
    ledger = directory / "ledger.json"
    with locked(ledger):
        specification, state = read_state(directory)
        if image != specification["image_digest"]:
            raise ValueError("Image digest binding changed")
        cases = specification["cases"]
        staging_slots = sum(c["environment"] == "staging" for c in cases)
        matching = [i for i, c in enumerate(cases) if c["environment"] == environment]
        if all(state["entries"][i]["reserved"] for i in matching):
            raise ValueError("Environment already consumed; no replay")
        if environment == "production" and not all(
            e["reserved"] for e in state["entries"][:staging_slots]
        ):
            raise ValueError("Staging acceptance is incomplete")
        for index in matching:
            entry = state["entries"][index]
            if entry["reserved"]:
                continue
            entry["reserved"] = True
            write_atomic(ledger, state)
            result = await run_case(
                cases[index],
                specification,
                base_url=base_url,
                caller=caller,
                admin=admin,
                transport=transport,
            )
            entry["result"] = result
            write_atomic(ledger, state)
            print(json.dumps({"case": cases[index]["id"], "status": result["status"]}), flush=True)
            if result["status"] != "passed":
                raise ValueError("Validation halted; consumed slot cannot replay")
        return state
