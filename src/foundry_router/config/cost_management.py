"""Validated public Azure billing scope and resource membership."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from foundry_router.credit_groups import metered_credit_groups

MAX_COST_GROUPS = 64
MAX_COST_RESOURCES = 32
MAX_RESOURCE_ID_CHARS = 2048
SUBSCRIPTION_SEGMENTS = 3
MAX_RESOURCE_GROUP_CHARS = 90
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
