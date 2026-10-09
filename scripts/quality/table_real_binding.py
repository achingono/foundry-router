"""Fail-closed Azure metadata binding before isolated Table inference traffic."""

from __future__ import annotations

import hashlib
import json
import re

from azure_cost_acceptance import bounded_metadata
from table_real_prepare import PARAMETER_PATH, SECRET_FIELDS, validate_model_contract

from foundry_router.api.adapters.google_schema import load_bounded_json

MAX_BYTES = 65536


def deployment_fingerprint(app, parameters):  # noqa: PLR0912 -- explicit deployment gates
    expected = parameters["config"]["value"]
    identity = parameters["identityResourceId"]["value"]
    properties = app["properties"]
    template = properties["template"]
    identities = app["identity"]["userAssignedIdentities"]
    if {value.casefold() for value in identities} != {identity.casefold()}:
        raise ValueError("Runtime identity mismatch")
    if app["name"] != expected["name"]:
        raise ValueError("Test app mismatch")
    if (
        properties.get("environmentId") or properties["managedEnvironmentId"]
    ).casefold() != expected["environmentId"].casefold():
        raise ValueError("Environment mismatch")
    if template["scale"]["maxReplicas"] != 1 or template["scale"]["minReplicas"] != 1:
        raise ValueError("Replica count mismatch")
    if len(template["containers"]) != 1:
        raise ValueError("One test container required")
    container = template["containers"][0]
    if container["image"] != expected["image"] or not re.fullmatch(
        r"[^@]+@sha256:[a-f0-9]{64}", expected["image"]
    ):
        raise ValueError("Immutable image mismatch")
    env = {item["name"]: item for item in container["env"]}
    for name, value in {
        "FOUNDRY_STATE_BACKEND": "table",
        "FOUNDRY_TABLE_ENDPOINT": expected["state"]["endpoint"],
        "FOUNDRY_TABLE_HEALTH_NAME": expected["state"]["healthTableName"],
        "FOUNDRY_TABLE_CREDIT_NAME": expected["state"]["creditTableName"],
        "FOUNDRY_RETRY_ATTEMPTS": "0",
        "FOUNDRY_RESERVATION_MAX_AGE_SECONDS": "30",
        "FOUNDRY_MODEL_ALIASES_JSON": "{}",
        "FOUNDRY_AZURE_CLIENT_ID": expected["clientId"],
        "FOUNDRY_RATE_LIMIT_REPLICA_SHARE": "1",
    }.items():
        if env.get(name, {}).get("value") != value:
            raise ValueError("Test runtime setting mismatch")
    # Optional modes must remain disabled in this isolated deployment.
    for name, default in {
        "FOUNDRY_RECONCILIATION_PROVIDER": "static",
        "FOUNDRY_QUOTA_BACKEND": "memory",
        "FOUNDRY_TELEMETRY_EXPORTER": "none",
    }.items():
        if name in env and env[name].get("value") != default:
            raise ValueError("Unexpected runtime mode")
    secrets = {item["name"]: item for item in properties["configuration"]["secrets"]}
    for key, (name, _) in SECRET_FIELDS.items():
        secret = secrets[env[name]["secretRef"]]
        if (
            secret["keyVaultUrl"] != expected["secretUrls"][key]
            or secret["identity"].casefold() != identity.casefold()
        ):
            raise ValueError("Pinned secret mismatch")
    ingress = properties["configuration"]["ingress"]
    if (ingress.get("ipSecurityRestrictions") or []) != expected["ingressIpSecurityRestrictions"]:
        raise ValueError("Ingress policy mismatch")
    if ingress.get("allowInsecure") is True:
        raise ValueError("HTTPS ingress required")
    # Bind to immutable approved parameters and live runtime equivalence checked above.
    return hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()


def bind_live(private, origin):
    data = load_bounded_json(PARAMETER_PATH.read_text(), max_bytes=MAX_BYTES)
    parameters = data["parameters"]
    expected = parameters["config"]["value"]
    identity = parameters["identityResourceId"]["value"]
    subscription, resource_group = identity.split("/")[2], identity.split("/")[4]
    app = bounded_metadata(
        [
            "az",
            "containerapp",
            "show",
            "--subscription",
            subscription,
            "-g",
            resource_group,
            "-n",
            expected["name"],
            "-o",
            "json",
        ]
    )
    fingerprint = deployment_fingerprint(app, parameters)
    actual_origin = "https://" + app["properties"]["configuration"]["ingress"]["fqdn"]
    if origin != actual_origin or private["deployment_fingerprint"] != fingerprint:
        raise ValueError("Approved live deployment mismatch")
    values = {}
    for key, (_, field) in SECRET_FIELDS.items():
        if key not in {
            "backends",
            "models",
            "pricing",
            "cycleStartDay",
            "cycleAllowance",
            "initialRemaining",
        }:
            continue
        metadata = bounded_metadata(
            [
                "az",
                "keyvault",
                "secret",
                "show",
                "--id",
                expected["secretUrls"][key],
                "--query",
                "{id:id,value:value}",
                "-o",
                "json",
            ]
        )
        if metadata["id"] != expected["secretUrls"][key]:
            raise ValueError("Pinned configuration changed")
        values[field] = metadata["value"]
    values["client_api_keys_json"] = '["validation-only"]'
    values["admin_api_keys_json"] = '["other-validation-only"]'
    if validate_model_contract(values) != private["models"]:
        raise ValueError("Pinned model/pricing contract mismatch")
    return fingerprint
