"""Schema observations expose no provider values and preserve the normal billing parser."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import azure_cost_schema as schema

from foundry_router.reconciliation.azure_cost import AzureCostManagementProvider
from foundry_router.reconciliation.cost_types import CostEvidenceError

RESOURCE = "/subscriptions/11111111-2222-3333-4444-555555555555/resourceGroups/synthetic/providers/Microsoft.CognitiveServices/accounts/account"


def payload(currency="USD"):
    return {
        "properties": {
            "columns": [
                {"name": "PreTaxCost", "type": "Number"},
                {"name": "Currency", "type": "String"},
                {"name": "ResourceId", "type": "String"},
            ],
            "rows": [[1.25, currency, RESOURCE]],
        }
    }


def test_exact_observation_contains_no_billing_values():
    result = schema.observe(json.dumps(payload()).encode(), {RESOURCE.casefold()})
    schema.validate_observation(result)
    assert result["currency"] == "USD" and result["resource_membership_matches"]
    assert "1.25" not in json.dumps(result) and RESOURCE not in json.dumps(result)


def test_non_usd_unknown_names_and_values_are_only_fixed_flags():
    data = payload("private-currency")
    data["properties"]["columns"].append({"name": "private-column", "type": "private-type"})
    data["properties"]["rows"][0].append("private-row")
    result = schema.observe(json.dumps(data).encode(), {RESOURCE.casefold()})
    assert result["currency"] == "non_USD" and result["unknown_column_count"] == 1
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "change,flag",
    [
        (lambda data: data["properties"]["rows"][0].__setitem__(0, -1), "amounts_negative"),
        (
            lambda data: data["properties"]["rows"][0].__setitem__(0, "private"),
            "amounts_missing_or_invalid",
        ),
    ],
)
def test_amount_flags_without_values(change, flag):
    data = payload()
    change(data)
    result = schema.observe(json.dumps(data).encode(), {RESOURCE.casefold()})
    assert result[flag] and "private" not in json.dumps(result)


def test_malformed_unknown_name_type_and_deep_bound():
    data = payload()
    data["properties"]["columns"].append({"name": {"private": "value"}})
    result = schema.observe(json.dumps(data).encode(), set())
    assert result["unknown_column_count"] == 1
    assert schema.observe(b"[" * 30 + b"0" + b"]" * 30, set())["body_rejected"]
    assert schema.observe(b"x" * (schema.MAX_PAGE_BYTES + 1), set())["body_rejected"]


def test_arbitrary_safe_observation_fields_rejected():
    result = schema.observe(json.dumps(payload()).encode(), set())
    result["private"] = "value"
    with pytest.raises(ValueError):
        schema.validate_observation(result)


@pytest.mark.asyncio
async def test_transport_forwards_once_and_preserves_parser_rejection():
    observations = []
    settings = SimpleNamespace(
        cost_management_groups={"safe-group": SimpleNamespace(resource_ids=(RESOURCE,))}
    )
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=payload("private-unit"))

    transport = schema.ObserverTransport(settings, observations, httpx.MockTransport(handle))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(
            "https://management.azure.com/synthetic/query",
            json={"dataset": {"filter": {"dimensions": {"values": [RESOURCE]}}}},
        )
        data = AzureCostManagementProvider._decode_page(response.content)
        with pytest.raises(CostEvidenceError):
            AzureCostManagementProvider._parse_rows(
                data["properties"], SimpleNamespace(resource_ids=(RESOURCE,))
            )
    assert len(calls) == 1 and len(observations) == 1
    assert observations[0]["schema"]["currency"] == "non_USD"
    assert "private-unit" not in json.dumps(observations)


@pytest.mark.asyncio
async def test_stream_closed_on_cancellation():
    import asyncio

    class Stream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b"first"
            await asyncio.sleep(1)

        async def aclose(self):
            self.closed = True

    inner = Stream()
    response = httpx.Response(200, stream=inner)
    stream = schema.ObservedStream(response, lambda _: None)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.02):
            async for _ in stream:
                pass
    assert inner.closed


@pytest.mark.asyncio
async def test_same_scope_groups_and_pagination_bound_to_resource_filter():
    other = RESOURCE + "-other"
    settings = SimpleNamespace(
        cost_management_groups={
            "safe-1": SimpleNamespace(resource_ids=(RESOURCE,)),
            "safe-2": SimpleNamespace(resource_ids=(other,)),
        }
    )
    observations = []

    def handle(request):
        data = payload()
        resource = json.loads(request.content)["dataset"]["filter"]["dimensions"]["values"][0]
        data["properties"]["rows"][0][2] = resource
        return httpx.Response(200, json=data)

    transport = schema.ObserverTransport(settings, observations, httpx.MockTransport(handle))
    async with httpx.AsyncClient(transport=transport) as client:
        for resource in (RESOURCE, RESOURCE, other):
            await client.post(
                "https://management.azure.com/same-scope/query",
                json={"dataset": {"filter": {"dimensions": {"values": [resource]}}}},
            )
    assert [(item["group"], item["page"]) for item in observations] == [
        ("safe-1", 1),
        ("safe-1", 2),
        ("safe-2", 1),
    ]
    assert all(item["schema"]["resource_membership_matches"] for item in observations)
