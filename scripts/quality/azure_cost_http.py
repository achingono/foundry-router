"""Single-use header-only observation of the existing CAD billing queries."""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import httpx
from azure.identity.aio import AzureCliCredential
from azure_cost_acceptance import METADATA_SECONDS, verify_cost
from azure_cost_currency import prepare
from azure_cost_diagnostic import execute

from foundry_router.reconciliation.azure_cost import MAX_PAGE_BYTES, AzureCostManagementProvider

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/plans/azure-cost-http-diagnosis"
MAX_PAGES = 10
MAX_GROUPS = 2
MAX_RETRY_SECONDS = 86400
MIN_HTTP_STATUS = 100
MAX_HTTP_STATUS = 599


def retry_after(headers):
    values = headers.get_list("retry-after")
    if not values:
        return {"retry_after": "absent", "retry_after_seconds": None}
    if len(values) == 1 and re.fullmatch(r"[0-9]{1,6}", values[0]):
        seconds = int(values[0])
        if seconds <= MAX_RETRY_SECONDS:
            return {"retry_after": "seconds", "retry_after_seconds": seconds}
    return {"retry_after": "invalid", "retry_after_seconds": None}


def validate_records(records, groups):
    if not isinstance(records, list) or len(records) > MAX_GROUPS * MAX_PAGES:
        raise ValueError("Invalid HTTP record bound")
    pages = dict.fromkeys(groups, 0)
    for item in records:
        if not isinstance(item, dict) or set(item) != {
            "group",
            "page",
            "status",
            "retry_after",
            "retry_after_seconds",
        }:
            raise ValueError("Invalid HTTP record fields")
        if not isinstance(item["group"], str) or item["group"] not in pages:
            raise ValueError("Invalid HTTP group")
        group = item["group"]
        pages[group] += 1
        if (
            type(item["page"]) is not int
            or item["page"] != pages[group]
            or pages[group] > MAX_PAGES
        ):
            raise ValueError("Invalid HTTP page")
        if (
            type(item["status"]) is not int
            or not MIN_HTTP_STATUS <= item["status"] <= MAX_HTTP_STATUS
        ):
            raise ValueError("Invalid HTTP status")
        kind, seconds = item["retry_after"], item["retry_after_seconds"]
        if kind == "seconds":
            if type(seconds) is not int or not 0 <= seconds <= MAX_RETRY_SECONDS:
                raise ValueError("Invalid Retry-After seconds")
        elif kind not in {"absent", "invalid"} or seconds is not None:
            raise ValueError("Invalid Retry-After classification")


class HeaderTransport(httpx.AsyncBaseTransport):
    def __init__(self, settings, records, inner=None):
        self.inner = inner or httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        self.records = records
        self.resources = {
            group: {value.casefold() for value in config.resource_ids}
            for group, config in settings.cost_management_groups.items()
        }
        if not 1 <= len(self.resources) <= MAX_GROUPS:
            raise ValueError("Invalid HTTP group bound")
        self.pages = dict.fromkeys(self.resources, 0)

    async def handle_async_request(self, request):
        if len(request.content) > MAX_PAGE_BYTES:
            raise ValueError("Invalid HTTP query bound")
        body = json.loads(request.content)
        values = body["dataset"]["filter"]["dimensions"]["values"]
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError("Invalid HTTP resource filter")
        requested = {value.casefold() for value in values}
        matches = [group for group, resources in self.resources.items() if requested == resources]
        if len(matches) != 1 or len(requested) != len(values):
            raise ValueError("Invalid HTTP query binding")
        group = matches[0]
        self.pages[group] += 1
        if self.pages[group] > MAX_PAGES:
            raise ValueError("Invalid HTTP page bound")
        response = await self.inner.handle_async_request(request)
        self.records.append(
            {
                "group": group,
                "page": self.pages[group],
                "status": response.status_code,
                **retry_after(response.headers),
            }
        )
        # The normal provider owns body consumption and response closure unchanged.
        return response

    async def aclose(self):
        await self.inner.aclose()


def run():
    records, groups = [], []

    async def verify(settings):
        groups.extend(settings.cost_management_groups)
        provider = AzureCostManagementProvider(
            credential=AzureCliCredential(process_timeout=METADATA_SECONDS),
            transport=HeaderTransport(settings, records),
        )
        return await verify_cost(settings, provider)

    def finalize(result):
        validate_records(records, groups)
        return {**result, "http_observations": records}

    return execute(directory=DIRECTORY, prepare=prepare, verify=verify, finalize=finalize)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = run()
    except (ValueError, OSError):
        print(json.dumps({"status": "refused"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
