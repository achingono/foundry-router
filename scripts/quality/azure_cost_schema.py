"""Verifier-only cost response observer; raw billing bodies never enter evidence."""

from __future__ import annotations

import argparse
import json
import logging
from decimal import Decimal
from pathlib import Path

import httpx
from azure.identity.aio import AzureCliCredential
from azure_cost_acceptance import METADATA_SECONDS, load_inputs, prepare_settings, verify_cost
from azure_cost_diagnostic import execute

from foundry_router.reconciliation.azure_cost import MAX_PAGE_BYTES, AzureCostManagementProvider
from foundry_router.reconciliation.cost_types import CostEvidenceError

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/plans/azure-cost-schema-diagnosis"
MAX_COLUMNS = 32
MAX_SAFE_ROWS = 10001
REQUIRED = {"PreTaxCost": "Number", "Currency": "String", "ResourceId": "String"}
HTTP_OK = 200
MAX_PAGES = 10
MAX_OBSERVATIONS = 20
FLAGS = {
    "valid_json",
    "properties_object",
    "columns_list",
    "rows_list",
    "row_widths_match",
    "amounts_missing_or_invalid",
    "amounts_negative",
    "resource_membership_matches",
    "duplicate_columns",
    "body_rejected",
}
COUNTS = {"column_count", "row_count", "unknown_column_count"}


def observe(payload, resources):
    result = dict.fromkeys(FLAGS, False)
    result.update(dict.fromkeys(COUNTS, 0))
    result.update(
        currency="missing_or_invalid", required_columns=dict.fromkeys(REQUIRED, "missing")
    )
    if len(payload) > MAX_PAGE_BYTES:
        result["body_rejected"] = True
        return result
    try:
        data = AzureCostManagementProvider._decode_page(payload)
    except CostEvidenceError:
        result["body_rejected"] = True
        return result
    result["valid_json"] = True
    properties = data.get("properties") if isinstance(data, dict) else None
    result["properties_object"] = isinstance(properties, dict)
    if not isinstance(properties, dict):
        return result
    columns, rows = properties.get("columns"), properties.get("rows")
    result["columns_list"], result["rows_list"] = isinstance(columns, list), isinstance(rows, list)
    columns = columns if isinstance(columns, list) else []
    rows = rows if isinstance(rows, list) else []
    result["column_count"] = min(len(columns), MAX_COLUMNS)
    result["row_count"] = min(len(rows), MAX_SAFE_ROWS)
    indices = {}
    unknown = 0
    for index, column in enumerate(columns):
        name = column.get("name") if isinstance(column, dict) else None
        if isinstance(name, str) and name in REQUIRED:
            if name in indices:
                result["duplicate_columns"] = True
            indices[name] = index
            result["required_columns"][name] = (
                "valid" if column.get("type") == REQUIRED[name] else "invalid"
            )
        else:
            unknown += 1
    result["unknown_column_count"] = min(unknown, MAX_COLUMNS)
    result["row_widths_match"] = all(
        isinstance(row, list) and len(row) == len(columns) for row in rows
    )
    currency = set()
    membership = bool(rows)
    for row in rows[:MAX_SAFE_ROWS]:
        if not isinstance(row, list) or len(row) != len(columns):
            result["amounts_missing_or_invalid"] = True
            currency.add("missing_or_invalid")
            membership = False
            continue
        amount = row[indices["PreTaxCost"]] if "PreTaxCost" in indices else None
        result["amounts_missing_or_invalid"] |= (
            not isinstance(amount, Decimal) or not amount.is_finite()
        )
        result["amounts_negative"] |= (
            isinstance(amount, Decimal) and amount.is_finite() and amount < 0
        )
        unit = row[indices["Currency"]] if "Currency" in indices else None
        currency.add(
            "USD"
            if unit == "USD"
            else "non_USD"
            if isinstance(unit, str) and unit
            else "missing_or_invalid"
        )
        resource = row[indices["ResourceId"]] if "ResourceId" in indices else None
        membership &= isinstance(resource, str) and resource.casefold() in resources
    result["currency"] = (
        "USD"
        if currency == {"USD"}
        else "non_USD"
        if "non_USD" in currency
        else "missing_or_invalid"
    )
    result["resource_membership_matches"] = membership
    return result


def validate_observation(result):
    if not isinstance(result, dict) or set(result) != FLAGS | COUNTS | {
        "currency",
        "required_columns",
    }:
        raise ValueError("Invalid safe observation")
    if any(type(result[name]) is not bool for name in FLAGS):
        raise ValueError("Invalid observation flags")
    for name in COUNTS:
        maximum = MAX_SAFE_ROWS if name == "row_count" else MAX_COLUMNS
        if type(result[name]) is not int or not 0 <= result[name] <= maximum:
            raise ValueError("Invalid observation count")
    if result["currency"] not in {"USD", "non_USD", "missing_or_invalid"}:
        raise ValueError("Invalid currency classification")
    if not isinstance(result["required_columns"], dict) or set(result["required_columns"]) != set(
        REQUIRED
    ):
        raise ValueError("Invalid required columns")
    if any(
        value not in {"valid", "invalid", "missing"}
        for value in result["required_columns"].values()
    ):
        raise ValueError("Invalid column classification")


def validate_records(observations, groups):
    if not isinstance(observations, list) or len(observations) > MAX_OBSERVATIONS:
        raise ValueError("Observation bound exceeded")
    pages = dict.fromkeys(groups, 0)
    for observation in observations:
        if not isinstance(observation, dict) or set(observation) != {
            "group",
            "page",
            "http_category",
            "schema",
        }:
            raise ValueError("Invalid observation envelope")
        if observation["group"] not in pages or observation["http_category"] not in {
            "success",
            "auth",
            "other",
        }:
            raise ValueError("Invalid observation binding")
        group = observation["group"]
        pages[group] += 1
        if (
            type(observation["page"]) is not int
            or observation["page"] != pages[group]
            or pages[group] > MAX_PAGES
        ):
            raise ValueError("Invalid observation page")
        validate_observation(observation["schema"])


class ObservedStream(httpx.AsyncByteStream):
    def __init__(self, response, callback):
        self.response = response
        self.callback = callback
        self.payload = bytearray()
        self.finished = False

    async def __aiter__(self):
        try:
            async for chunk in self.response.aiter_bytes():
                if len(self.payload) + len(chunk) > MAX_PAGE_BYTES:
                    self.callback(b" " * (MAX_PAGE_BYTES + 1))
                    self.finished = True
                    raise CostEvidenceError("cost_response_bound")
                self.payload.extend(chunk)
                yield chunk
            self.callback(self.payload)
            self.finished = True
        finally:
            await self.response.aclose()

    async def aclose(self):
        self.payload.clear()
        await self.response.aclose()


class ObserverTransport(httpx.AsyncBaseTransport):
    def __init__(self, settings, observations, inner=None):
        self.inner = inner or httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        self.observations = observations
        self.groups = list(settings.cost_management_groups)
        self.resources = {
            group: {resource.casefold() for resource in config.resource_ids}
            for group, config in settings.cost_management_groups.items()
        }
        self.pages = dict.fromkeys(self.groups, 0)

    async def handle_async_request(self, request):
        if len(request.content) > MAX_PAGE_BYTES:
            raise ValueError("Bounded query required")
        body = json.loads(request.content)
        values = body["dataset"]["filter"]["dimensions"]["values"]
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError("Exact resource filter required")
        requested = {value.casefold() for value in values}
        matches = [group for group in self.groups if requested == self.resources[group]]
        if len(matches) != 1:
            raise ValueError("Unique query group required")
        group = matches[0]
        self.pages[group] += 1
        page = self.pages[group]
        if page > MAX_PAGES:
            raise ValueError("Page bound exceeded")
        response = await self.inner.handle_async_request(request)
        status = (
            "success"
            if response.status_code == HTTP_OK
            else "auth"
            if response.status_code in {401, 403}
            else "other"
        )

        def callback(payload):
            result = observe(payload, self.resources[group])
            validate_observation(result)
            self.observations.append(
                {"group": group, "page": page, "http_category": status, "schema": result}
            )

        # Yield decoded bytes once; prevent the outer client from decoding a second time.
        headers = [
            (key, value)
            for key, value in response.headers.raw
            if key.lower() not in {b"content-encoding", b"content-length"}
        ]
        return httpx.Response(
            response.status_code, headers=headers, stream=ObservedStream(response, callback)
        )

    async def aclose(self):
        await self.inner.aclose()


def run():
    observations = []
    groups = []

    async def verify(settings):
        groups.extend(settings.cost_management_groups)
        transport = ObserverTransport(settings, observations)
        provider = AzureCostManagementProvider(
            credential=AzureCliCredential(process_timeout=METADATA_SECONDS), transport=transport
        )
        return await verify_cost(settings, provider)

    def finalize(result):
        validate_records(observations, groups)
        return {**result, "observations": observations}

    return execute(
        directory=DIRECTORY,
        prepare=lambda: prepare_settings(load_inputs()),
        verify=verify,
        finalize=finalize,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = run()
    except (ValueError, OSError, IndexError):
        print(json.dumps({"status": "refused"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
