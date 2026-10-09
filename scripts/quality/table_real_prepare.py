"""Read-only discovery and private pinned inputs for the isolated Table test."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

from azure_cost_acceptance import bounded_metadata
from google_live_budget import write_atomic

from foundry_router.config import Settings
from foundry_router.reconciliation.cost_types import CostEvidenceError

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PATH = ROOT / "infra/table-real-inputs.local.json"
PARAMETER_PATH = ROOT / "infra/table-real-parameters.local.json"
SECRET_FIELDS = {
    "clientKeys": ("FOUNDRY_CLIENT_API_KEYS_JSON", "client_api_keys_json"),
    "adminKeys": ("FOUNDRY_ADMIN_API_KEYS_JSON", "admin_api_keys_json"),
    "backends": ("FOUNDRY_BACKENDS_JSON", "backends_json"),
    "models": ("FOUNDRY_MODELS_JSON", "models_json"),
    "pricing": ("FOUNDRY_PRICING_JSON", "pricing_json"),
    "cycleStartDay": ("FOUNDRY_BACKEND_CYCLE_START_DAY_JSON", "backend_cycle_start_day_json"),
    "cycleAllowance": (
        "FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON",
        "backend_cycle_allowance_usd_json",
    ),
    "initialRemaining": (
        "FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON",
        "backend_initial_estimated_remaining_usd_json",
    ),
}
MAX_ESTIMATE_USD = 0.15
INPUT_BOUND = 64
OUTPUT_BOUND = 1024
MODEL_COUNT = 2
VERSIONED_SECRET_SEGMENTS = 4
MAX_TABLE_PREFIX_CHARS = 40


class IsolatedSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        _ = settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


def validate_model_contract(values):
    settings = IsolatedSettings(**values)
    if len(settings.models) != MODEL_COUNT or settings.model_aliases:
        raise ValueError("Exact two-model test contract required")
    models = []
    for number, (model, pool) in enumerate(settings.models.items(), 1):
        if len(pool.backends) != 1 or model not in settings.pricing:
            raise ValueError("Single backend and explicit pricing required")
        backend_id = next(iter(pool.backends))
        backend = settings.backends[backend_id]
        if backend.provider != "azure_foundry" or not backend.deployment:
            raise ValueError("Azure deployed model required")
        host = backend.endpoint.host or ""
        if not host.endswith((".openai.azure.com", ".services.ai.azure.com")):
            raise ValueError("Exact public Azure inference host required")
        endpoint = urlsplit(str(backend.endpoint))
        if (
            endpoint.scheme != "https"
            or endpoint.port not in {None, 443}
            or endpoint.path not in {"", "/"}
        ):
            raise ValueError("Public Azure root required")
        if (
            backend.supported_operations is not None
            and "responses" not in backend.supported_operations
        ):
            raise ValueError("Responses backend required")
        price = settings.pricing[model]
        reserve = (
            INPUT_BOUND * price.input_per_million + OUTPUT_BOUND * price.output_per_million
        ) / 1_000_000
        models.append(
            {
                "label": f"model-{number}",
                "model": model,
                "backend": backend_id,
                "reserve_usd": reserve,
                "input_per_million": price.input_per_million,
                "output_per_million": price.output_per_million,
            }
        )
    if sum(model["reserve_usd"] * 2 for model in models) > MAX_ESTIMATE_USD:
        raise ValueError("Four maximum reservations exceed authorization")
    return models


def prepare(  # noqa: PLR0913 -- independent validated metadata and target configuration
    app, storage, identity, pinned, values, *, test_name, table_prefix, image
):
    if app["properties"]["template"]["scale"]["maxReplicas"] != 1:
        raise ValueError("Single-replica source required")
    if (
        storage.get("allowSharedKeyAccess") is not False
        or storage.get("enableHttpsTrafficOnly") is not True
        or storage.get("minimumTlsVersion") != "TLS1_2"
    ):
        raise ValueError("Hardened existing account required")
    if test_name == app["name"] or not test_name.startswith("foundry-router-table-real-"):
        raise ValueError("Separate test app required")
    if not table_prefix.isalnum() or not table_prefix.startswith("frTableReal"):
        raise ValueError("Separate table prefix required")
    if len(table_prefix) > MAX_TABLE_PREFIX_CHARS:
        raise ValueError("Bounded table prefix required")
    for key in SECRET_FIELDS:
        validate_pinned(pinned[key], {"id": pinned[key]})
    models = validate_model_contract(values)
    source = app["properties"]
    registry = source["configuration"]["registries"]
    if (
        len(registry) != 1
        or not isinstance(registry[0].get("identity"), str)
        or registry[0]["identity"].casefold() != identity["id"].casefold()
    ):
        raise ValueError("Existing identity registry pull required")
    if not re.fullmatch(
        re.escape(registry[0]["server"]) + r"/foundry-router@sha256:[a-f0-9]{64}", image
    ):
        raise ValueError("Existing registry test image required")
    config = {
        "name": test_name,
        "containerName": "router",
        "location": app["location"],
        "tags": {"purpose": "isolated-table-real-inference"},
        "environmentId": source.get("environmentId") or source["managedEnvironmentId"],
        "image": image,
        "clientId": identity["clientId"],
        "containerPort": 8000,
        "minReplicas": 1,
        "maxReplicas": 1,
        "secretNamePrefix": table_prefix.lower(),
        "secretUrls": pinned,
        "registry": {
            "authMode": "managedIdentity",
            "server": registry[0]["server"],
            "username": "",
            "isExternalRegistry": False,
        },
        "state": {
            "backend": "table",
            "endpoint": storage["primaryEndpoints"]["table"],
            "healthTableName": table_prefix + "health",
            "creditTableName": table_prefix + "credit",
        },
        "modelAliases": {},
        "ingressIpSecurityRestrictions": source["configuration"]["ingress"].get(
            "ipSecurityRestrictions"
        )
        or [],
        "retryAttempts": 0,
        "reservationMaxAgeSeconds": 30,
    }
    parameters = {
        "config": {"value": config},
        "identityResourceId": {"value": identity["id"]},
        "identityPrincipalId": {"value": identity["principalId"]},
        "storageResourceGroupName": {"value": storage["id"].split("/")[4]},
        "storageAccountName": {"value": storage["name"]},
    }
    fingerprint = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
    return parameters, {
        "config_fingerprint": fingerprint,
        "models": models,
        "client_secret_ref": pinned["clientKeys"],
        "admin_secret_ref": pinned["adminKeys"],
    }


def one_identity(app):
    identities = app["identity"]["userAssignedIdentities"]
    if len(identities) != 1:
        raise ValueError("One existing runtime identity required")
    identity_id, identity_values = next(iter(identities.items()))
    return {"id": identity_id, **identity_values}


def validate_pinned(reference, metadata):
    before, after = urlsplit(reference), urlsplit(metadata["id"])
    pattern = r"/secrets/[A-Za-z0-9-]+(?:/[a-fA-F0-9]{32})?"
    if (
        before.scheme != "https"
        or not before.hostname
        or not before.hostname.endswith(".vault.azure.net")
        or before.username
        or before.password
        or before.port
        or before.query
        or before.fragment
        or not re.fullmatch(pattern, before.path)
        or after.scheme != "https"
        or after.netloc.casefold() != before.netloc.casefold()
        or after.query
        or after.fragment
        or not re.fullmatch(r"/secrets/[A-Za-z0-9-]+/[a-fA-F0-9]{32}", after.path)
        or after.path.split("/")[2] != before.path.split("/")[2]
        or (len(before.path.split("/")) == VERSIONED_SECRET_SEGMENTS and before.path != after.path)
    ):
        raise ValueError("Pinned secret version required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-app", required=True)
    parser.add_argument("--source-rg", required=True)
    parser.add_argument("--storage-account", required=True)
    parser.add_argument("--storage-rg", required=True)
    parser.add_argument("--test-app", required=True)
    parser.add_argument("--table-prefix", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        app = bounded_metadata(
            [
                "az",
                "containerapp",
                "show",
                "-g",
                args.source_rg,
                "-n",
                args.source_app,
                "-o",
                "json",
            ]
        )
        identity = one_identity(app)
        storage = bounded_metadata(
            [
                "az",
                "storage",
                "account",
                "show",
                "-g",
                args.storage_rg,
                "-n",
                args.storage_account,
                "-o",
                "json",
            ]
        )
        secrets = {item["name"]: item for item in app["properties"]["configuration"]["secrets"]}
        env = {item["name"]: item for item in app["properties"]["template"]["containers"][0]["env"]}
        pinned, values = {}, {}
        for key, (environment, setting) in SECRET_FIELDS.items():
            reference = secrets[env[environment]["secretRef"]]["keyVaultUrl"]
            metadata = bounded_metadata(
                [
                    "az",
                    "keyvault",
                    "secret",
                    "show",
                    "--id",
                    reference,
                    "--query",
                    "{id:id,value:value}",
                    "-o",
                    "json",
                ]
            )
            validate_pinned(reference, metadata)
            pinned[key], values[setting] = metadata["id"], metadata["value"]
        parameters, private = prepare(
            app,
            storage,
            identity,
            pinned,
            values,
            test_name=args.test_app,
            table_prefix=args.table_prefix,
            image=args.image,
        )
        write_atomic(
            PARAMETER_PATH,
            {
                "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
                "contentVersion": "1.0.0.0",
                "parameters": parameters,
            },
        )
        write_atomic(PRIVATE_PATH, private)
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "models": len(private["models"]),
                    "estimated_maximum_usd": sum(
                        model["reserve_usd"] * 2 for model in private["models"]
                    ),
                    "credential_values_written": False,
                }
            )
        )
    except (OSError, ValueError, KeyError, CostEvidenceError):
        print(json.dumps({"status": "preparation_unverified"}))
        return 2
    else:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
