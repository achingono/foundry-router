"""One immutable read-only diagnostic refresh with fixed redacted categories."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

from azure.core.exceptions import AzureError
from azure_cost_acceptance import RESULTS, load_inputs, prepare_settings, verify_cost
from google_live_budget import locked, write_atomic

from foundry_router.reconciliation.cost_types import CostEvidenceError

DIRECTORY = RESULTS.parent
STARTED = DIRECTORY / "diagnostic-started.json"
DIAGNOSTIC_RESULTS = DIRECTORY / "diagnostic-results.json"
CATEGORIES = {
    "metadata_unavailable": "metadata",
    "metadata_mismatch": "metadata",
    "operator_mapping_invalid": "metadata",
    "cost_http_unavailable": "http_rejection",
    "cost_transport_unavailable": "transport",
    "cost_response_bound": "schema",
    "cost_response_invalid": "schema",
    "cost_json_depth_bound": "schema",
    "cost_row_bound": "schema",
    "cost_rows_unavailable": "schema",
    "cost_columns_invalid": "schema",
    "cost_rows_invalid": "schema",
    "cost_pagination_invalid": "pagination",
    "cost_pagination_repeated": "pagination",
    "cost_page_bound": "pagination",
    "cost_cleanup_unavailable": "cleanup",
}


def category(error):
    if isinstance(error, AzureError):
        return "identity"
    if isinstance(error, CostEvidenceError) and len(error.args) == 1:
        value = error.args[0]
        if isinstance(value, str):
            return CATEGORIES.get(value, "unknown")
    return "unknown"


def execute(*, directory=DIRECTORY, prepare=None, verify=None, finalize=None):
    started_path = directory / STARTED.name
    results_path = directory / DIAGNOSTIC_RESULTS.name
    with locked(started_path):
        if started_path.exists() or results_path.exists():
            raise ValueError("Diagnostic invocation already consumed")
        write_atomic(started_path, {"invocation": "cost-diagnostic-2026-10-08", "started": True})
        started = time.monotonic()
        boundary = "metadata"
        try:
            settings = (prepare or (lambda: prepare_settings(load_inputs())))()
            boundary = "provider"
            result = asyncio.run((verify or verify_cost)(settings))
        except (OSError, ValueError, AzureError, CostEvidenceError) as error:
            result = {
                "status": "unverified",
                "failure_boundary": boundary,
                "error_category": category(error),
                "permission_status": "unverified",
                "balance_applied": False,
                "groups": [],
            }
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        if finalize is not None:
            result = finalize(result)
        write_atomic(results_path, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = execute()
    except (ValueError, OSError):
        print(json.dumps({"status": "refused"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
