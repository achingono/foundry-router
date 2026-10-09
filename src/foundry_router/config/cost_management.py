"""Validated public Azure billing scope and resource membership."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from foundry_router.credit_groups import metered_credit_groups

MAX_COST_GROUPS = 64
MAX_COST_RESOURCES = 32
MAX_RESOURCE_ID_CHARS = 2048
SUBSCRIPTION_SEGMENTS = 3
MAX_RESOURCE_GROUP_CHARS = 90
PAIR_FIELDS = 2
MAX_CURRENCY_JSON_BYTES = 65536
_SEGMENT = r"[^/]+"
_SUBSCRIPTION = r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}"
_SCOPE = re.compile(
    rf"^/subscriptions/{_SUBSCRIPTION}(?:/resourceGroups/{_SEGMENT})?$", re.IGNORECASE
)
_RESOURCE = re.compile(
    rf"^/subscriptions/{_SUBSCRIPTION}/resourceGroups/{_SEGMENT}"
    rf"/providers/Microsoft\.CognitiveServices/accounts/{_SEGMENT}$",
    re.IGNORECASE,
)


def _valid_group_segment(scope: str) -> bool:
    parts = scope.split("/")
    if len(parts) == SUBSCRIPTION_SEGMENTS:
        return True
    name = parts[4]
    return (
        bool(name)
        and len(name) <= MAX_RESOURCE_GROUP_CHARS
        and not name.endswith(".")
        and all(char in "_-.()" or unicodedata.category(char)[0] in {"L", "N"} for char in name)
    )


class CostGroupConfig(BaseModel):
    """Explicit one-account cost query; no endpoint-derived membership."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    scope: str = Field(max_length=1024)
    resource_ids: tuple[str, ...] = Field(min_length=1, max_length=MAX_COST_RESOURCES)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        if not _SCOPE.fullmatch(value) or not _valid_group_segment(value):
            raise ValueError("Cost scope must be an exact public subscription/resource-group path")
        return value

    @field_validator("resource_ids")
    @classmethod
    def validate_resources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            len(value) > MAX_RESOURCE_ID_CHARS
            or not _RESOURCE.fullmatch(value)
            or not _valid_group_segment(value)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", value.rsplit("/", 1)[-1])
            for value in values
        ):
            raise ValueError("Cost resource must be an exact Cognitive Services account path")
        if len({value.casefold() for value in values}) != len(values):
            raise ValueError("Cost resource membership must be unique")
        return values


def parse_cost_groups(settings: Any) -> dict[str, CostGroupConfig]:
    """Validate the entire mapping before constructing outbound clients."""
    try:
        data = json.loads(settings.cost_management_groups_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("Cost groups must be a JSON object") from exc
    if not isinstance(data, dict) or not data or len(data) > MAX_COST_GROUPS:
        raise ValueError("Cost groups must contain 1-64 canonical account mappings")
    if settings.reconciliation_overrides_usd:
        raise ValueError("Cost provider cannot be combined with static replacement overrides")
    groups = metered_credit_groups(settings)
    resources: set[str] = set()
    result: dict[str, CostGroupConfig] = {}
    for group, raw in data.items():
        if (
            group not in groups
            or group not in settings.backend_cycle_allowance_usd
            or group not in settings.backend_cycle_start_day
        ):
            raise ValueError("Cost group needs a known metered account and explicit cycle policy")
        config = CostGroupConfig.model_validate(raw)
        prefix = config.scope.casefold() + "/"
        for resource in config.resource_ids:
            identifier = resource.casefold()
            if not identifier.startswith(prefix) or identifier in resources:
                raise ValueError("Cost resource must be within scope and belong to one account")
            resources.add(identifier)
        result[group] = config
    return result


def parse_subscription_currencies(raw: str, groups: dict[str, CostGroupConfig]) -> dict[str, str]:
    """Currency belongs to billing subscription; unmapped scopes retain USD behavior."""
    if not isinstance(raw, str) or len(raw.encode()) > MAX_CURRENCY_JSON_BYTES:
        raise ValueError("Subscription currencies must be a bounded object")
    try:
        pairs = json.loads(raw, object_pairs_hook=list)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Subscription currencies must be an object") from exc
    if not isinstance(pairs, list) or len(pairs) > MAX_COST_GROUPS:
        raise ValueError("Subscription currencies must be a bounded object")
    used = {config.scope.split("/")[2].casefold() for config in groups.values()}
    result = {}
    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != PAIR_FIELDS:
            raise ValueError("Subscription currencies must be an object")
        subscription, currency = pair
        if not isinstance(subscription, str) or not re.fullmatch(_SUBSCRIPTION, subscription):
            raise ValueError("Subscription currency needs an exact UUID")
        key = str(UUID(subscription))
        if (
            key in result
            or key not in used
            or not isinstance(currency, str)
            or currency not in {"USD", "CAD"}
        ):
            raise ValueError("Subscription currency must be unique, used and USD or CAD")
        result[key] = currency
    # JSON [] is distinct from {}; the pairs decoder maps both to [], so check the root.
    if not raw.lstrip().startswith("{"):
        raise ValueError("Subscription currencies must be an object")
    return result


def billing_currency(settings: Any, config: CostGroupConfig) -> str:
    value = getattr(settings, "cost_management_subscription_currencies", {}).get(
        config.scope.split("/")[2].casefold(), "USD"
    )
    if not isinstance(value, str) or value not in {"USD", "CAD"}:
        raise ValueError("Unsupported subscription billing currency")
    return value
