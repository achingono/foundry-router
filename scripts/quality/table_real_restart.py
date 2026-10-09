"""Explicit isolated test restart; compare settled estimates without more inference."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

import httpx
from azure_cost_acceptance import bounded_metadata
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_credential
from table_real_binding import bind_live
from table_real_prepare import PARAMETER_PATH, PRIVATE_PATH
from table_real_verify import (
    CASE_COUNT,
    DIRECTORY,
    bounded_get,
    snapshot,
    validate_ledger,
    validate_private,
)

from foundry_router.api.adapters.google_schema import load_bounded_json

MAX_BYTES = 65536
RESTART_SECONDS = 120


def replica_generation(replicas):
    if not isinstance(replicas, list) or len(replicas) != 1:
        return None
    replica = replicas[0]
    containers = replica.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        return None
    container = containers[0]
    if container.get("ready") is not True or container.get("started") is not True:
        return None
    if (
        not isinstance(replica.get("name"), str)
        or not replica["name"]
        or not isinstance(container.get("containerId"), str)
        or not container["containerId"]
        or type(container.get("restartCount")) is not int
        or container["restartCount"] < 0
    ):
        return None
    return (
        replica["name"],
        container["containerId"],
        container["restartCount"],
    )


def fresh_generation(before, after):
    return after is not None and (
        after[0] != before[0] or after[1] != before[1] or after[2] > before[2]
    )


def get_generation(subscription, resource_group, app, revision):
    return replica_generation(
        bounded_metadata(
            [
                "az",
                "containerapp",
                "replica",
                "list",
                "--subscription",
                subscription,
                "-g",
                resource_group,
                "-n",
                app,
                "--revision",
                revision,
                "--query",
                "[].{name:name,containers:properties.containers}",
                "-o",
                "json",
            ]
        )
    )


async def verify_restart(private, parameters, admin_key):
    origin = private["origin"]
    bind_live(private, origin)
    ledger = validate_ledger(
        load_bounded_json((DIRECTORY / "ledger.json").read_text(), max_bytes=MAX_BYTES), private
    )
    if len(ledger["cases"]) != CASE_COUNT or any(
        item["result"] is None or item["result"]["status"] != "passed"
        for item in ledger["cases"].values()
    ):
        raise ValueError("All four passing cases required before restart")
    identity = parameters["identityResourceId"]["value"]
    subscription, resource_group = identity.split("/")[2], identity.split("/")[4]
    app = parameters["config"]["value"]["name"]
    headers = {"x-admin-key": admin_key}
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5) as client:
        before = snapshot(
            await bounded_get(client, origin + "/admin/status", headers), private["models"]
        )
        revision = bounded_metadata(
            [
                "az",
                "containerapp",
                "revision",
                "list",
                "--subscription",
                subscription,
                "-g",
                resource_group,
                "-n",
                app,
                "--query",
                "[?properties.active].{name:name}",
                "-o",
                "json",
            ]
        )
        if len(revision) != 1:
            raise ValueError("One active isolated revision required")
        generation = get_generation(subscription, resource_group, app, revision[0]["name"])
        if generation is None:
            raise ValueError("Ready original test process required")
        # Restart only the verified test revision, not the app environment or any baseline.
        bounded_metadata(
            [
                "az",
                "containerapp",
                "revision",
                "restart",
                "--subscription",
                subscription,
                "-g",
                resource_group,
                "-n",
                app,
                "--revision",
                revision[0]["name"],
                "-o",
                "json",
            ]
        )
        deadline = time.monotonic() + RESTART_SECONDS
        recovered = False
        while time.monotonic() < deadline:
            current_generation = get_generation(
                subscription, resource_group, app, revision[0]["name"]
            )
            if not fresh_generation(generation, current_generation):
                await asyncio.sleep(2)
                continue
            try:
                await bounded_get(client, origin + "/health/ready", {})
                after = snapshot(
                    await bounded_get(client, origin + "/admin/status", headers), private["models"]
                )
            except (httpx.HTTPError, TimeoutError, ValueError):
                await asyncio.sleep(2)
                continue
            if before != after:
                raise ValueError("Settled Table estimates changed")
            recovered = True
            break
        if not recovered:
            raise ValueError("Readiness did not recover")
        bind_live(private, origin)
    return {
        "status": "passed",
        "settled_estimates_preserved": True,
        "reservations_cleared": True,
        "inference_requests": 0,
        "fresh_process_confirmed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        with locked(DIRECTORY / "ledger.json"):
            private = load_bounded_json(PRIVATE_PATH.read_text(), max_bytes=MAX_BYTES)
            validate_private(private, private["origin"])
            parameters = load_bounded_json(PARAMETER_PATH.read_text(), max_bytes=MAX_BYTES)[
                "parameters"
            ]
            admin_key = json.loads(fetch_credential(private["admin_secret_ref"]))[0]
            result = asyncio.run(verify_restart(private, parameters, admin_key))
            write_atomic(DIRECTORY / "restart-results.json", result)
            print(json.dumps(result))
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        print(json.dumps({"status": "restart_unverified"}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
