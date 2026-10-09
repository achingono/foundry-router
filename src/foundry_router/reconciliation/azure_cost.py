"""Confined public ARM billing queries with downward-only estimate results."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation, localcontext
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, quote, urlsplit

import httpx

from foundry_router.config.cost_management import billing_currency
from foundry_router.credit import calculate_cycle_window
from foundry_router.reconciliation.cost_types import (
    CostCeiling,
    CostCeilingBatch,
    CostEvidenceError,
    cost_policy_fingerprint,
    downward_float,
)
from foundry_router.reconciliation.exchange_rate import DailyExchangeRateClient
from foundry_router.state.azure import select_credential

if TYPE_CHECKING:
    from foundry_router.config.cost_management import CostGroupConfig

MAX_JSON_DEPTH = 16
MAX_PAGE_BYTES = 1024 * 1024
MAX_PAGES = 10
MAX_ROWS = 10_000
API_VERSION = "2025-03-01"
ARM_ORIGIN = "https://management.azure.com"
REFRESH_SECONDS = 30
HTTP_OK = 200
MAX_NEXT_LINK_CHARS = 8192
CONTROL_LIMIT = 32
PAGINATION_FIELDS = 2
MAX_AMOUNT_EXPONENT = 12
MIN_AMOUNT_EXPONENT = -18
MAX_AMOUNT_DIGITS = 64
DECIMAL_PRECISION = 1200


class AzureCostManagementProvider:
    """Lifespan-owned identity/client; no billing I/O on inference paths."""

    kind = "azure_cost_management"

    def __init__(
        self,
        *,
        credential: Any = None,
        transport: httpx.AsyncBaseTransport | None = None,
        rate_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if credential is None:
            credential = select_credential()
        self._credential = credential
        self._client = httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=10,
        )
        self._closed = False
        self._client_closed = False
        self._credential_closed = False
        self._rate_transport = rate_transport
        self._rate_client: DailyExchangeRateClient | None = None
        self._rate_closed = True
        self._close_task: asyncio.Task[None] | None = None

    async def close(self) -> None:
        """Finish bounded independent cleanup despite repeated caller cancellation."""
        self._closed = True
        if self._client_closed and self._credential_closed and self._rate_closed:
            return
        if self._close_task is None or self._close_task.done():
            self._close_task = asyncio.create_task(self._close_resources())
        cancelled = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            # Consume any failure so no detached task retains an unobserved exception.
            self._close_task.exception()
            raise asyncio.CancelledError
        self._close_task.result()

    async def _close_resources(self) -> None:
        failures = False
        for resource, flag, method in (
            (self._client, "_client_closed", "aclose"),
            (self._credential, "_credential_closed", "close"),
            (self._rate_client, "_rate_closed", "aclose"),
        ):
            if getattr(self, flag):
                continue
            for _attempt in range(2):
                try:
                    async with asyncio.timeout(2):
                        await getattr(resource, method)()
                    setattr(self, flag, True)
                    break
                except Exception:
                    # No raw transport/identity error may enter application logs.
                    continue
            if not getattr(self, flag):
                failures = True
        if failures:
            raise CostEvidenceError("cost_cleanup_unavailable")

    async def fetch_remaining_credit(self, settings: Any) -> CostCeilingBatch:
        """Complete cost fetch; an incomplete group prevents the whole batch."""
        if self._closed:
            raise CostEvidenceError("cost_provider_closed")
        try:
            async with asyncio.timeout(REFRESH_SECONDS):
                now = datetime.now(UTC)
                # Bind every policy field before the first await. A configuration change
                # during FX/token/billing I/O must invalidate the fetched batch.
                policies = tuple(
                    (
                        group,
                        config,
                        billing_currency(settings, config),
                        settings.backend_cycle_start_day[group],
                        settings.backend_cycle_allowance_usd[group],
                        cost_policy_fingerprint(settings, group),
                    )
                    for group, config in settings.cost_management_groups.items()
                )
                rate = None
                if any(policy[2] == "CAD" for policy in policies):
                    # Acquire only after the provider has an owner that can close its
                    # existing ARM client/credential if public transport setup fails.
                    if self._rate_client is None:
                        self._rate_client = DailyExchangeRateClient(transport=self._rate_transport)
                        self._rate_closed = False
                    rate = await self._rate_client.fetch(now)
                token = await self._credential.get_token("https://management.azure.com/.default")
                ceilings = []
                for group, config, currency, day, allowance, fingerprint in policies:
                    cycle = calculate_cycle_window(now, day)
                    cost = await self._query_group(
                        config,
                        cycle.current_cycle_start_utc,
                        now,
                        token.token,
                        currency=currency,
                    )
                    if currency == "CAD":
                        if rate is None:
                            raise CostEvidenceError("cost_exchange_rate_unavailable")
                        with localcontext() as context:
                            context.prec = DECIMAL_PRECISION
                            context.rounding = ROUND_CEILING
                            cost = cost / rate.cad_per_usd
                    # All validated values are bounded decimal numbers; do not round a ceiling up.
                    with localcontext() as context:
                        context.prec = DECIMAL_PRECISION
                        context.rounding = ROUND_FLOOR
                        remaining = max(Decimal(0), Decimal(allowance) - cost)
                    if fingerprint is None:
                        raise CostEvidenceError("cost_policy_unavailable")
                    ceilings.append(
                        CostCeiling(
                            group,
                            downward_float(remaining),
                            cycle.current_cycle_start_utc,
                            day,
                            allowance,
                            fingerprint,
                        )
                    )
                return CostCeilingBatch(tuple(ceilings), now, rate)
        except (TimeoutError, httpx.HTTPError) as exc:
            raise CostEvidenceError("cost_transport_unavailable") from exc

    async def _query_group(
        self,
        config: CostGroupConfig,
        start: datetime,
        end: datetime,
        token: str,
        *,
        currency: str = "USD",
    ) -> Decimal:
        path = quote(config.scope, safe="/()-._") + "/providers/Microsoft.CostManagement/query"
        url = ARM_ORIGIN + path + "?api-version=" + API_VERSION
        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
            "dataset": {
                "granularity": "None",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "filter": {
                    "dimensions": {
                        "name": "ResourceId",
                        "operator": "In",
                        "values": list(config.resource_ids),
                    }
                },
                "grouping": [{"type": "Dimension", "name": "ResourceId"}],
            },
        }
        seen: set[str] = set()
        row_count = 0
        total = Decimal(0)
        for _page in range(MAX_PAGES):
            if url in seen:
                raise CostEvidenceError("cost_pagination_repeated")
            seen.add(url)
            async with self._client.stream(
                "POST", url, headers={"Authorization": "Bearer " + token}, json=body
            ) as response:
                if response.status_code != HTTP_OK:
                    raise CostEvidenceError("cost_http_unavailable")
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(payload) + len(chunk) > MAX_PAGE_BYTES:
                        raise CostEvidenceError("cost_response_bound")
                    payload.extend(chunk)
            data = self._decode_page(payload)
            if not isinstance(data, dict) or not isinstance(data.get("properties"), dict):
                raise CostEvidenceError("cost_response_invalid")
            properties = data["properties"]
            subtotal, rows = self._parse_rows(properties, config, currency=currency)
            row_count += rows
            if row_count > MAX_ROWS:
                raise CostEvidenceError("cost_row_bound")
            with localcontext() as context:
                context.prec = DECIMAL_PRECISION
                total += subtotal
            next_link = properties.get("nextLink")
            if next_link is None:
                return total
            url = self._pagination_url(next_link, path)
        raise CostEvidenceError("cost_page_bound")

    @staticmethod
    def _decode_page(payload: bytearray) -> Any:
        # Bound container depth before the recursive JSON decoder, ignoring escaped
        # structure inside strings. Every byte is visited once under the page bound.
        depth = 0
        in_string = False
        escaped = False
        for char in payload:
            if in_string:
                if escaped:
                    escaped = False
                elif char == ord("\\"):
                    escaped = True
                elif char == ord('"'):
                    in_string = False
            elif char == ord('"'):
                in_string = True
            elif char in (ord("["), ord("{")):
                depth += 1
                if depth > MAX_JSON_DEPTH:
                    raise CostEvidenceError("cost_json_depth_bound")
            elif char in (ord("]"), ord("}")):
                depth -= 1
        try:
            return json.loads(payload, parse_float=Decimal, parse_int=Decimal)
        except (ValueError, InvalidOperation, RecursionError) as exc:
            raise CostEvidenceError("cost_response_invalid") from exc

    @staticmethod
    def _pagination_url(link: Any, path: str) -> str:
        if (
            not isinstance(link, str)
            or len(link) > MAX_NEXT_LINK_CHARS
            or any(ord(char) < CONTROL_LIMIT for char in link)
        ):
            raise CostEvidenceError("cost_pagination_invalid")
        try:
            parsed = urlsplit(link)
        except ValueError as exc:
            raise CostEvidenceError("cost_pagination_invalid") from exc
        if (
            parsed.scheme != "https"
            or parsed.netloc != "management.azure.com"
            or parsed.path != path
            or parsed.fragment
        ):
            raise CostEvidenceError("cost_pagination_invalid")
        try:
            query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        except ValueError as exc:
            raise CostEvidenceError("cost_pagination_invalid") from exc
        if (
            len(query) != PAGINATION_FIELDS
            or len(dict(query)) != PAGINATION_FIELDS
            or dict(query).get("api-version") != API_VERSION
            or not dict(query).get("$skiptoken")
            or set(dict(query)) != {"api-version", "$skiptoken"}
        ):
            raise CostEvidenceError("cost_pagination_invalid")
        return link

    @staticmethod
    def _parse_rows(
        properties: dict[str, Any], config: CostGroupConfig, *, currency: str = "USD"
    ) -> tuple[Decimal, int]:
        columns, rows = properties.get("columns"), properties.get("rows")
        if (
            not isinstance(columns, list)
            or not isinstance(rows, list)
            or not rows
            or len(rows) > MAX_ROWS
        ):
            raise CostEvidenceError("cost_rows_unavailable")
        indices: dict[str, int] = {}
        required = {"PreTaxCost": "Number", "Currency": "String", "ResourceId": "String"}
        for index, column in enumerate(columns):
            if (
                not isinstance(column, dict)
                or not isinstance(column.get("name"), str)
                or column["name"] in indices
            ):
                raise CostEvidenceError("cost_columns_invalid")
            name = column["name"]
            if name in required and column.get("type") != required[name]:
                raise CostEvidenceError("cost_columns_invalid")
            indices[name] = index
        if not required.keys() <= indices.keys():
            raise CostEvidenceError("cost_columns_invalid")
        allowed = {value.casefold() for value in config.resource_ids}
        total = Decimal(0)
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise CostEvidenceError("cost_rows_invalid")
            amount, row_currency, resource = (row[indices[name]] for name in required)
            if (
                not isinstance(amount, Decimal)
                or not amount.is_finite()
                or amount < 0
                or len(amount.as_tuple().digits) > MAX_AMOUNT_DIGITS
                or amount.adjusted() > MAX_AMOUNT_EXPONENT
                or amount.adjusted() < MIN_AMOUNT_EXPONENT
                or row_currency != currency
                or not isinstance(resource, str)
                or resource.casefold() not in allowed
            ):
                raise CostEvidenceError("cost_rows_invalid")
            with localcontext() as context:
                context.prec = DECIMAL_PRECISION
                total += amount
        return total, len(rows)
