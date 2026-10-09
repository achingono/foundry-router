"""Deployment mutations cannot substitute memory or altered modes for the Table test."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import table_real_binding as binding
from table_real_prepare import SECRET_FIELDS


def deployment():
    identity = "/subscriptions/11111111-2222-3333-4444-555555555555/resourceGroups/test/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test"
    secret_urls = {
        key: f"https://synthetic.vault.azure.net/secrets/{key}/" + "a" * 32 for key in SECRET_FIELDS
    }
    expected = {
        "name": "foundry-router-table-real-synthetic",
        "environmentId": "synthetic-environment",
        "image": "synthetic.azurecr.io/foundry-router@sha256:" + "b" * 64,
        "clientId": "synthetic-client",
        "state": {
            "endpoint": "https://synthetic.table.core.windows.net/",
            "healthTableName": "frTableRealhealth",
            "creditTableName": "frTableRealcredit",
        },
        "secretUrls": secret_urls,
        "ingressIpSecurityRestrictions": [],
    }
    values = {
        "FOUNDRY_STATE_BACKEND": "table",
        "FOUNDRY_TABLE_ENDPOINT": expected["state"]["endpoint"],
        "FOUNDRY_TABLE_HEALTH_NAME": expected["state"]["healthTableName"],
        "FOUNDRY_TABLE_CREDIT_NAME": expected["state"]["creditTableName"],
        "FOUNDRY_RETRY_ATTEMPTS": "0",
        "FOUNDRY_RESERVATION_MAX_AGE_SECONDS": "30",
        "FOUNDRY_MODEL_ALIASES_JSON": "{}",
        "FOUNDRY_AZURE_CLIENT_ID": "synthetic-client",
        "FOUNDRY_RATE_LIMIT_REPLICA_SHARE": "1",
    }
    env = [{"name": name, "value": value} for name, value in values.items()]
    secrets = []
    for key, (name, _) in SECRET_FIELDS.items():
        env.append({"name": name, "secretRef": key})
        secrets.append({"name": key, "identity": identity, "keyVaultUrl": secret_urls[key]})
    app = {
        "name": expected["name"],
        "identity": {"userAssignedIdentities": {identity: {}}},
        "properties": {
            "environmentId": expected["environmentId"],
            "template": {
                "scale": {"minReplicas": 1, "maxReplicas": 1},
                "containers": [{"image": expected["image"], "env": env}],
            },
            "configuration": {
                "secrets": secrets,
                "ingress": {"allowInsecure": False, "ipSecurityRestrictions": []},
            },
        },
    }
    parameters = {"config": {"value": expected}, "identityResourceId": {"value": identity}}
    return app, parameters


def test_exact_table_deployment_produces_bound_fingerprint():
    app, parameters = deployment()
    result = binding.deployment_fingerprint(app, parameters)
    assert result == hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize(
    "name,value",
    [
        ("FOUNDRY_STATE_BACKEND", "memory"),
        ("FOUNDRY_TABLE_CREDIT_NAME", "existingProductionCredit"),
        ("FOUNDRY_TABLE_HEALTH_NAME", "existingSyntheticHealth"),
        ("FOUNDRY_RETRY_ATTEMPTS", "2"),
        ("FOUNDRY_RESERVATION_MAX_AGE_SECONDS", "900"),
        ("FOUNDRY_RATE_LIMIT_BACKEND", "table"),
        ("FOUNDRY_TELEMETRY_ENABLED", "true"),
        ("FOUNDRY_RECONCILIATION_PROVIDER", "azure_cost_management"),
    ],
)
def test_altered_runtime_setting_rejects(name, value):
    app, parameters = deployment()
    env = app["properties"]["template"]["containers"][0]["env"]
    env[:] = [item for item in env if item["name"] != name]
    env.append({"name": name, "value": value})
    with pytest.raises(ValueError):
        binding.deployment_fingerprint(app, parameters)


@pytest.mark.parametrize("mutation", ["image", "identity", "secret", "ingress", "scale"])
def test_wrong_deployment_artifact_rejects(mutation):
    app, parameters = deployment()
    if mutation == "image":
        app["properties"]["template"]["containers"][0]["image"] = "synthetic:mutable"
    elif mutation == "identity":
        app["identity"]["userAssignedIdentities"] = {"another-identity": {}}
    elif mutation == "secret":
        app["properties"]["configuration"]["secrets"][0]["keyVaultUrl"] += "changed"
    elif mutation == "ingress":
        app["properties"]["configuration"]["ingress"]["allowInsecure"] = True
    else:
        app["properties"]["template"]["scale"]["maxReplicas"] = 2
    with pytest.raises(ValueError):
        binding.deployment_fingerprint(app, parameters)


def test_explicit_expected_optional_defaults_preserve_binding():
    app, parameters = deployment()
    altered = copy.deepcopy(app)
    altered["properties"]["template"]["containers"][0]["env"].extend(
        [
            {"name": "FOUNDRY_RATE_LIMIT_BACKEND", "value": "memory"},
            {"name": "FOUNDRY_TELEMETRY_ENABLED", "value": "false"},
        ]
    )
    assert binding.deployment_fingerprint(altered, parameters) == binding.deployment_fingerprint(
        app, parameters
    )
