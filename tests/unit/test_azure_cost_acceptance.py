"""Read-only acceptance validates membership and emits only labeled ceilings."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))

import azure_cost_acceptance as runner
import pytest

from foundry_router.reconciliation.cost_types import CostEvidenceError


def inputs():
    return {
        "resources": {
            group: {
                "subscriptionId": "11111111-2222-3333-4444-555555555555",
                "resourceGroup": "synthetic",
                "credit_group": group,
                "cycle_start_day": 2,
                "cycle_allowance_usd": 210,
            }
            for group in runner.GROUPS
        }
    }


def discover(command):
    group = command[command.index("--name") + 1]
    return {
        "id": "/subscriptions/11111111-2222-3333-4444-555555555555/resourceGroups/synthetic"
        "/providers/Microsoft.CognitiveServices/accounts/" + group,
        "name": group,
        "type": "Microsoft.CognitiveServices/accounts",
        "kind": "AIServices",
    }


def test_exact_two_discoveries_preserve_returned_membership():
    calls = []

    def record(command):
        calls.append(command)
        return discover(command)

    settings = runner.prepare_settings(inputs(), record)
    assert len(calls) == 2 and set(settings.cost_management_groups) == set(runner.GROUPS)
    assert all("account" in command and "show" in command for command in calls)
    assert settings.backend_cycle_allowance_usd == dict.fromkeys(runner.GROUPS, 210.0)


@pytest.mark.parametrize("field,value", [("id", "wrong"), ("kind", "Storage"), ("name", "other")])
def test_wrong_metadata_rejects_before_billing(field, value):
    def wrong(command):
        result = discover(command)
        result[field] = value
        return result

    with pytest.raises(CostEvidenceError):
        runner.prepare_settings(inputs(), wrong)


def test_second_invalid_scope_prevents_all_metadata():
    data = inputs()
    data["resources"]["fs-swarm"]["resourceGroup"] = "invalid/path"
    calls = []
    with pytest.raises(ValueError):
        runner.prepare_settings(data, calls.append)
    assert not calls


def test_operator_account_name_is_independent_of_safe_credit_label():
    data = inputs()
    item = data["resources"].pop("fs-openclaw")
    data["resources"]["operator-account"] = item
    calls = []

    def record(command):
        calls.append(command)
        return discover(command)

    settings = runner.prepare_settings(data, record)
    assert calls[0][calls[0].index("--name") + 1] == "operator-account"
    assert (
        settings.cost_management_groups["fs-openclaw"].resource_ids[0].endswith("/operator-account")
    )


@pytest.mark.parametrize("allowance", [float("nan"), float("inf"), -1, True])
def test_invalid_allowance_rejects(allowance):
    data = inputs()
    data["resources"]["fs-openclaw"]["cycle_allowance_usd"] = allowance
    with pytest.raises(CostEvidenceError):
        runner.prepare_settings(data, discover)


@pytest.mark.asyncio
async def test_clamped_ceiling_is_not_reconstructed_as_reported_cost():
    now = datetime(2026, 10, 2, tzinfo=UTC)

    class Provider:
        closed = False

        async def fetch_remaining_credit(self, settings):
            return SimpleNamespace(
                fetched_at_utc=now,
                ceilings=[
                    SimpleNamespace(
                        credit_group="fs-openclaw",
                        cycle_start_utc=now,
                        remaining_usd=0.0,
                        allowance_usd=210.0,
                    )
                ],
            )

        async def close(self):
            self.closed = True

    provider = Provider()
    result = await runner.verify_cost(None, provider)
    assert provider.closed and result["balance_applied"] is False
    assert result["groups"][0]["estimated_ceiling_usd"] == 0
    assert set(result["groups"][0]) == {
        "credit_group",
        "cycle_start_utc",
        "estimated_ceiling_usd",
        "allowance_usd",
    }


def test_metadata_pipe_enforces_cap_and_reaps():
    import sys

    with pytest.raises(CostEvidenceError):
        runner.bounded_metadata([sys.executable, "-c", "print('x' * 70000)"])


def test_metadata_timeout_reaps(monkeypatch):
    import sys

    monkeypatch.setattr(runner, "METADATA_SECONDS", 0.02)
    with pytest.raises(CostEvidenceError):
        runner.bounded_metadata([sys.executable, "-c", "import time; time.sleep(10)"])
