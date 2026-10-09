"""One immutable read-only acceptance using operator-confirmed CAD subscriptions."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from azure_cost_acceptance import load_inputs, prepare_settings
from azure_cost_diagnostic import execute

from foundry_router.config.cost_management import parse_subscription_currencies

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/plans/azure-cost-currency"


def prepare():
    settings = prepare_settings(load_inputs())
    # Operator confirmed CAD for all current subscriptions; IDs remain private.
    mapping = {
        config.scope.split("/")[2]: "CAD" for config in settings.cost_management_groups.values()
    }
    settings.cost_management_subscription_currencies = parse_subscription_currencies(
        json.dumps(mapping), settings.cost_management_groups
    )
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = execute(directory=DIRECTORY, prepare=prepare)
    except (ValueError, OSError):
        print(json.dumps({"status": "refused"}))
        return 2
    print(json.dumps(result, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
