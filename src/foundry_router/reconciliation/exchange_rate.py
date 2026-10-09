"""Bounded public daily CAD-per-USD rate evidence; no authenticated transport."""

# ruff: noqa: TRY301 -- parser guards share one sanitized failure boundary

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.reconciliation.cost_types import CostEvidenceError

RATE_URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=10"
RATE_SOURCE = "Bank of Canada FXUSDCAD daily average"
RATE_METHOD = "latest_daily_average_cycle_to_date_estimate"
MAX_RATE_BYTES = 65536
MAX_OBSERVATIONS = 10
MAX_AGE_DAYS = 4
RATE_SECONDS = 5
HTTP_OK = 200


@dataclass(frozen=True)
class DailyExchangeRate:
    observation_date: date
    cad_per_usd: Decimal
    source: str = RATE_SOURCE
    method: str = RATE_METHOD

    def __post_init__(self) -> None:
        if (
            type(self.observation_date) is not date
            or not isinstance(self.cad_per_usd, Decimal)
            or not self.cad_per_usd.is_finite()
            or not Decimal("0.1") <= self.cad_per_usd <= Decimal(10)
            or self.source != RATE_SOURCE
            or self.method != RATE_METHOD
        ):
            raise CostEvidenceError("cost_exchange_rate_invalid")


def parse_daily_rate(payload: bytes, now: datetime) -> DailyExchangeRate:
    try:
        if now.tzinfo is None:
            raise ValueError("Aware date required")
        data = load_bounded_json(payload.decode(), max_bytes=MAX_RATE_BYTES)
        series = data["seriesDetail"]["FXUSDCAD"]
        if (
            series["label"] != "USD/CAD"
            or series["description"]
            != "Daily average exchange rate of the US dollar in Canadian dollars."
            or series["dimension"] != {"key": "d", "name": "Date"}
        ):
            raise ValueError("Invalid series")
        observations = data["observations"]
        if not isinstance(observations, list) or not 1 <= len(observations) <= MAX_OBSERVATIONS:
            raise ValueError("Invalid observation count")
        today = now.astimezone(ZoneInfo("America/Toronto")).date()
        rates = {}
        for item in observations:
            if not isinstance(item, dict) or set(item) != {"d", "FXUSDCAD"}:
                raise ValueError("Invalid observation")
            raw_date, quote = item["d"], item["FXUSDCAD"]
            if not isinstance(raw_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
                raise ValueError("Invalid rate date")
            day = date.fromisoformat(raw_date)
            if day > today or day in rates or not isinstance(quote, dict) or set(quote) != {"v"}:
                raise ValueError("Invalid rate date or quote")
            value = quote["v"]
            if not isinstance(value, str) or not re.fullmatch(r"\d{1,2}(?:\.\d{1,12})?", value):
                raise ValueError("Invalid rate")
            rate = Decimal(value)
            if not Decimal("0.1") <= rate <= Decimal(10):
                raise ValueError("Invalid rate bounds")
            rates[day] = rate
        latest = max(rates)
        if (today - latest).days > MAX_AGE_DAYS:
            raise ValueError("Stale rate")
        return DailyExchangeRate(latest, rates[latest])
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise CostEvidenceError("cost_exchange_rate_invalid") from exc


class DailyExchangeRateClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=RATE_SECONDS,
        )

    async def fetch(self, now: datetime) -> DailyExchangeRate:
        try:
            async with asyncio.timeout(RATE_SECONDS):
                async with self._client.stream("GET", RATE_URL) as response:
                    if response.status_code != HTTP_OK:
                        raise CostEvidenceError("cost_exchange_rate_unavailable")
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(payload) + len(chunk) > MAX_RATE_BYTES:
                            raise CostEvidenceError("cost_exchange_rate_invalid")
                        payload.extend(chunk)
                return parse_daily_rate(bytes(payload), now)
        except (httpx.HTTPError, TimeoutError) as exc:
            raise CostEvidenceError("cost_exchange_rate_unavailable") from exc

    async def aclose(self) -> None:
        await self._client.aclose()


def rate_metadata(rate: Any) -> dict[str, str] | None:
    if rate is None:
        return None
    return {
        "source": rate.source,
        "method": rate.method,
        "observation_date": rate.observation_date.isoformat(),
        "cad_per_usd": str(rate.cad_per_usd),
    }
