"""Fixed read-only billing acceptance; never applies ceilings to router balances."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import selectors
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from azure.core.exceptions import AzureError
from azure.identity.aio import AzureCliCredential

from foundry_router.config.cost_management import CostGroupConfig
from foundry_router.reconciliation.azure_cost import AzureCostManagementProvider
from foundry_router.reconciliation.cost_types import CostEvidenceError
from foundry_router.reconciliation.exchange_rate import rate_metadata

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "infra/production-inputs.local.json"
RESULTS = ROOT / "docs/plans/azure-cost-live-verification/results.json"
GROUPS = ("fs-openclaw", "fs-swarm")
MAX_BYTES = 65536
METADATA_SECONDS = 15
MAX_CYCLE_DAY = 28
MAX_ALLOWANCE_USD = 1_000_000


def bounded_metadata(command):
    """Read a capped pipe; terminate and reap on timeout, oversize or read failure."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + METADATA_SECONDS
        payload = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise CostEvidenceError("metadata_unavailable")
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > MAX_BYTES:
                    raise CostEvidenceError("metadata_unavailable")
        if process.wait(timeout=max(0.001, deadline - time.monotonic())):
            raise CostEvidenceError("metadata_unavailable")
        return json.loads(payload)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise CostEvidenceError("metadata_unavailable") from exc
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if process.stdout is not None:
            process.stdout.close()


def prepare_settings(inputs, discover=bounded_metadata):
    resources = inputs.get("resources") if isinstance(inputs, dict) else None
    if not isinstance(resources, dict) or len(resources) != len(GROUPS):
        raise CostEvidenceError("operator_mapping_invalid")
    by_group = {}
    for name, item in resources.items():
        if (
            not isinstance(name, str)
            or not isinstance(item, dict)
            or item.get("credit_group") not in GROUPS
            or item["credit_group"] in by_group
        ):
            raise CostEvidenceError("operator_mapping_invalid")
        by_group[item["credit_group"]] = (name, item)
    configs, days, allowances = {}, {}, {}
    # Validate every supplied scope and policy before any external discovery.
    for group in GROUPS:
        name, item = by_group[group]
        if not isinstance(item, dict) or item.get("credit_group") != group:
            raise CostEvidenceError("operator_mapping_invalid")
        day, allowance = item.get("cycle_start_day"), item.get("cycle_allowance_usd")
        if (
            type(day) is not int
            or not 1 <= day <= MAX_CYCLE_DAY
            or type(allowance) not in {int, float}
            or not 0 <= allowance <= MAX_ALLOWANCE_USD
        ):
            raise CostEvidenceError("operator_mapping_invalid")
        subscription, resource_group = item.get("subscriptionId"), item.get("resourceGroup")
        if not isinstance(subscription, str) or not isinstance(resource_group, str):
            raise CostEvidenceError("operator_mapping_invalid")
        scope = f"/subscriptions/{subscription}/resourceGroups/{resource_group}"
        resource = scope + "/providers/Microsoft.CognitiveServices/accounts/" + name
        configs[group] = CostGroupConfig(scope=scope, resource_ids=(resource,))
        days[group], allowances[group] = day, float(allowance)
    for group in GROUPS:
        name, item = by_group[group]
        metadata = discover(
            [
                "az",
                "cognitiveservices",
                "account",
                "show",
                "--subscription",
                item["subscriptionId"],
                "--resource-group",
                item["resourceGroup"],
                "--name",
                name,
                "--query",
                "{id:id,name:name,type:type,kind:kind}",
                "-o",
                "json",
            ]
        )
        expected = configs[group]
        if (
            not isinstance(metadata, dict)
            or set(metadata) != {"id", "name", "type", "kind"}
            or not isinstance(metadata["id"], str)
            or metadata["id"].casefold() != expected.resource_ids[0].casefold()
            or metadata["name"] != name
            or metadata["type"] != "Microsoft.CognitiveServices/accounts"
            or metadata["kind"] not in {"AIServices", "OpenAI"}
        ):
            raise CostEvidenceError("metadata_mismatch")
        configs[group] = CostGroupConfig(scope=expected.scope, resource_ids=(metadata["id"],))
    return SimpleNamespace(
        reconciliation_provider="azure_cost_management",
        cost_management_groups=configs,
        backend_cycle_start_day=days,
        backend_cycle_allowance_usd=allowances,
    )


async def verify_cost(settings, provider=None):
    provider = provider or AzureCostManagementProvider(
        credential=AzureCliCredential(process_timeout=METADATA_SECONDS)
    )
    try:
        batch = await provider.fetch_remaining_credit(settings)
        return {
            "status": "passed",
            "permission_status": "query_succeeded",
            "balance_applied": False,
            "fetched_at_utc": batch.fetched_at_utc.isoformat(),
            "groups": [
                {
                    "credit_group": ceiling.credit_group,
                    "cycle_start_utc": ceiling.cycle_start_utc.isoformat(),
                    "estimated_ceiling_usd": ceiling.remaining_usd,
                    "allowance_usd": ceiling.allowance_usd,
                }
                for ceiling in batch.ceilings
            ],
            "exchange_rate": rate_metadata(getattr(batch, "exchange_rate", None)),
        }
    finally:
        await provider.close()


def load_inputs():
    if INPUTS.stat().st_size > MAX_BYTES:
        raise CostEvidenceError("operator_mapping_invalid")
    return json.loads(INPUTS.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        return 2
    logging.disable(logging.CRITICAL)
    started = time.monotonic()
    try:
        settings = prepare_settings(load_inputs())
        result = asyncio.run(verify_cost(settings))
    except (OSError, ValueError, AzureError, CostEvidenceError):
        result = {
            "status": "unverified",
            "error_category": "metadata_identity_or_billing_unavailable",
            "permission_status": "unverified",
            "balance_applied": False,
            "groups": [],
        }
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    RESULTS.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
