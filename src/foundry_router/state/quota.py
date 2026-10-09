"""Bounded, conditional Table quota accounting independent of credit balances."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, NoReturn
from zoneinfo import ZoneInfo

import structlog

from foundry_router.ratelimit import QuotaGroupSnapshot, QuotaStoreError
from foundry_router.state.table import TableEntityClient, _TransactionEntity

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

MAX_RECORDS = 256
MAX_OWNERS = 4096
MAX_ATTEMPT_BYTES = 128
MAX_DAYS = 2
MAX_STORAGE_BYTES = 48 * 1024
MAX_RESERVATION_AGE = 3600.0
WINDOW_SECONDS = 70.0
CLOCK_GUARD_SECONDS = 5.0
MAX_CONFLICTS = 8
ROW_KEY = "quota"
_logger = structlog.get_logger(__name__)


def _invalid(message: str) -> NoReturn:
    raise ValueError(message)


def _unavailable(message: str) -> NoReturn:
    raise QuotaStoreError(message)


_PACIFIC = ZoneInfo("America/Los_Angeles")


def _partition(group: str) -> str:
    return "quota-" + hashlib.sha256(group.encode()).hexdigest()


def _date(now: float) -> str:
    return datetime.fromtimestamp(now, UTC).astimezone(_PACIFIC).date().isoformat()


class AzureTableRateLimitStore:
    """One ETag-guarded state property per quota group; no process-local admission cap."""

    def __init__(self, client: TableEntityClient, *, now_fn: Callable[[], datetime] | None = None):
        self._client = client
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._quota_limits: dict[str, dict[str, int]] = {}
        self._fingerprints: dict[str, str] = {}
        self._reservation_max_age_seconds = 900.0
        self._owners: dict[str, str] = {}
        self._lock = asyncio.Lock()

    @property
    def quota_limits(self) -> dict[str, dict[str, int]]:
        return {group: dict(limits) for group, limits in self._quota_limits.items()}

    @property
    def reservation_max_age_seconds(self) -> float:
        return self._reservation_max_age_seconds

    def _now(self) -> float:
        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            _unavailable("Quota clock must be timezone-aware")
        result = now.timestamp()
        if not math.isfinite(result):
            _unavailable("Quota clock must be finite")
        return result

    @staticmethod
    def _boundary(now: float) -> bool:
        return _date(now - CLOCK_GUARD_SECONDS) != _date(now + CLOCK_GUARD_SECONDS)

    def _fresh(self, group: str, now: float) -> dict[str, Any]:
        return {
            "group": group,
            "fingerprint": self._fingerprints[group],
            "watermark": now,
            "day": _date(now),
            "age": self._reservation_max_age_seconds,
            "daily": {},
            "records": [],
        }

    def _decode(self, group: str, entity: Mapping[str, object]) -> dict[str, Any]:
        try:
            raw = entity["state"]
            if not isinstance(raw, str) or len(raw.encode("utf-16-le")) > MAX_STORAGE_BYTES:
                _invalid("state size")
            state = json.loads(raw)
            if (
                not isinstance(state, dict)
                or set(state)
                != {"group", "fingerprint", "watermark", "day", "age", "daily", "records"}
                or state["group"] != group
                or not isinstance(state["fingerprint"], str)
                or not isinstance(state["watermark"], (int, float))
                or isinstance(state["watermark"], bool)
                or not math.isfinite(state["watermark"])
                or not isinstance(state["age"], (int, float))
                or isinstance(state["age"], bool)
                or not 0 < state["age"] <= MAX_RESERVATION_AGE
                or not isinstance(state["day"], str)
                or not isinstance(state["daily"], dict)
                or len(state["daily"]) > MAX_DAYS
                or not isinstance(state["records"], list)
                or len(state["records"]) > MAX_RECORDS
            ):
                _invalid("state shape")
            date.fromisoformat(state["day"])
            for day, count in state["daily"].items():
                date.fromisoformat(day)
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    _invalid("daily count")
            seen = set()
            for record in state["records"]:
                if (
                    not isinstance(record, dict)
                    or set(record) != {"id", "at", "tokens", "pending", "day"}
                    or not isinstance(record["id"], str)
                    or not record["id"]
                    or len(record["id"].encode()) > MAX_ATTEMPT_BYTES
                    or record["id"] in seen
                    or not isinstance(record["pending"], bool)
                    or isinstance(record["tokens"], bool)
                    or not isinstance(record["tokens"], int)
                    or record["tokens"] < 0
                    or isinstance(record["at"], bool)
                    or not isinstance(record["at"], (int, float))
                    or not math.isfinite(record["at"])
                    or record["at"] > state["watermark"]
                    or record["day"] not in state["daily"]
                ):
                    _invalid("record shape")
                seen.add(record["id"])
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise QuotaStoreError("Quota state is invalid") from exc
        else:
            return state

    def _prune(self, state: dict[str, Any], now: float) -> None:
        if now < state["watermark"]:
            _unavailable("Quota clock regressed")
        for record in state["records"]:
            if now - record["at"] > state["age"]:
                record["pending"] = False
        state["records"] = [
            r for r in state["records"] if r["pending"] or now - r["at"] <= WINDOW_SECONDS
        ]
        day = _date(now)
        previous = (
            datetime.fromtimestamp(now, UTC).astimezone(_PACIFIC).date() - timedelta(days=1)
        ).isoformat()
        state["daily"] = {d: n for d, n in state["daily"].items() if d in {day, previous}}
        state["watermark"] = now

    def _entity(self, group: str, state: dict[str, Any]) -> dict[str, object]:
        raw = json.dumps(state, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        if len(raw.encode("utf-16-le")) > MAX_STORAGE_BYTES:
            _unavailable("Quota state storage capacity reached")
        return {"PartitionKey": _partition(group), "RowKey": ROW_KEY, "state": raw}

    async def _read(self, group: str, now: float) -> tuple[Mapping[str, object], dict[str, Any]]:
        entity = await self._client.get_entity(_partition(group), ROW_KEY)
        if entity is None:
            # Create-if-absent; lost acknowledgement is an error, never a fresh quota reset.
            await self._client.try_create_entity(self._entity(group, self._fresh(group, now)))
            entity = await self._client.get_entity(_partition(group), ROW_KEY)
            if entity is None:
                _unavailable("Quota initialization could not be confirmed")
        state = self._decode(group, entity)
        prior_day = state["day"]
        self._prune(state, now)
        if state["fingerprint"] != self._fingerprints[group]:
            if self._boundary(now) or state["records"] or prior_day >= _date(now):
                _unavailable("Quota policy change requires drained day rollover")
            state["fingerprint"] = self._fingerprints[group]
            state["age"] = self._reservation_max_age_seconds
            state["day"] = _date(now)
        return entity, state

    async def _write(self, group: str, entity: Mapping[str, object], state: dict[str, Any]) -> bool:
        etag = entity.get("odata.etag")
        if not isinstance(etag, str) or not etag:
            _unavailable("Quota write requires an ETag")
        return await self._client.try_batch_transaction(
            [
                _TransactionEntity(
                    _partition(group), ROW_KEY, "Update", self._entity(group, state), etag
                )
            ]
        )

    async def _reconcile_owners(self) -> None:
        """Retire only owners proven absent/finalized across every known group."""
        if not self._owners:
            return
        pending: set[str] = set()
        now = self._now()
        for group in self._quota_limits:
            entity = await self._client.get_entity(_partition(group), ROW_KEY)
            if entity is not None:
                state = self._decode(group, entity)
                self._prune(state, now)
                pending.update(record["id"] for record in state["records"] if record["pending"])
        self._owners = {key: group for key, group in self._owners.items() if key in pending}

    async def sync_from_settings(self, settings: Any) -> None:
        limits = {
            group: dict(values)
            for group, values in settings.quota_group_rate_limits.items()
            if values
        }
        age = float(settings.reservation_max_age_seconds)
        if not math.isfinite(age) or not 0 < age <= MAX_RESERVATION_AGE:
            _unavailable("Table quota age must be positive and at most 3600 seconds")
        membership = sorted(
            (key, getattr(value, "quota_group", None) or key)
            for key, value in settings.backends.items()
        )
        fingerprints = {
            group: hashlib.sha256(
                json.dumps(
                    [1, group, values, WINDOW_SECONDS, CLOCK_GUARD_SECONDS, age, membership],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            for group, values in limits.items()
        }
        async with self._lock:
            try:
                await self._reconcile_owners()
            except Exception as exc:
                raise QuotaStoreError("Quota ownership could not be confirmed") from exc
            if self._owners and (
                limits != self._quota_limits or fingerprints != self._fingerprints
            ):
                _unavailable("Quota membership change requires drained owners")
            old = self._quota_limits, self._fingerprints, self._reservation_max_age_seconds
            self._quota_limits, self._fingerprints, self._reservation_max_age_seconds = (
                limits,
                fingerprints,
                age,
            )
            try:
                for group in limits:
                    for _ in range(MAX_CONFLICTS):
                        now = self._now()
                        entity, state = await self._read(group, now)
                        if await self._write(group, entity, state):
                            break
                    else:
                        _unavailable("Quota initialization contention exhausted")
            except Exception as exc:
                _logger.warning("quota_store_failed", error_type=type(exc).__name__)
                self._quota_limits, self._fingerprints, self._reservation_max_age_seconds = old
                raise QuotaStoreError("Quota configuration could not be confirmed") from exc

    async def try_reserve_estimate(
        self,
        request_id: str,
        quota_group: str,
        *,
        estimated_input_tokens: int,
        reservation_max_age_seconds: float = 900.0,
        allow_over_limit: bool = False,
    ) -> bool:
        if not request_id or len(request_id.encode()) > MAX_ATTEMPT_BYTES:
            _invalid("Quota attempt ID must be 1-128 UTF-8 bytes")
        if (
            isinstance(estimated_input_tokens, bool)
            or not isinstance(estimated_input_tokens, int)
            or estimated_input_tokens < 0
        ):
            _invalid("Quota input estimate must be non-negative")
        if reservation_max_age_seconds != self._reservation_max_age_seconds:
            _unavailable("Quota reservation age differs from policy")
        async with self._lock:
            try:
                await self._reconcile_owners()
            except Exception as exc:
                raise QuotaStoreError("Quota ownership could not be confirmed") from exc
            if quota_group not in self._quota_limits:
                _unavailable("Quota group has no configured shared limits")
            if len(self._owners) >= MAX_OWNERS or request_id in self._owners:
                _unavailable("Quota attempt ownership unavailable or capacity reached")
            self._owners[request_id] = quota_group  # Before uncertain transaction dispatch.
            try:
                for _ in range(MAX_CONFLICTS):
                    now = self._now()
                    if self._boundary(now):
                        self._owners.pop(request_id)
                        return False
                    entity, state = await self._read(quota_group, now)
                    if any(r["id"] == request_id for r in state["records"]):
                        _unavailable("Quota attempt already recorded")
                    recent = [r for r in state["records"] if now - r["at"] <= WINDOW_SECONDS]
                    limits = self._quota_limits[quota_group]
                    used = {
                        "rpm": len(recent),
                        "tpm": sum(r["tokens"] for r in recent),
                        "rpd": state["daily"].get(_date(now), 0),
                    }
                    needed = {"rpm": 1, "tpm": estimated_input_tokens, "rpd": 1}
                    if len(state["records"]) >= MAX_RECORDS or (
                        not allow_over_limit
                        and any(used[d] + needed[d] > cap for d, cap in limits.items())
                    ):
                        self._owners.pop(request_id)
                        return False
                    state["day"] = _date(now)
                    state["daily"][_date(now)] = used["rpd"] + 1
                    state["records"].append(
                        {
                            "id": request_id,
                            "at": now,
                            "tokens": estimated_input_tokens,
                            "pending": True,
                            "day": _date(now),
                        }
                    )
                    if await self._write(quota_group, entity, state):
                        return True
                _unavailable("Quota admission contention exhausted")
            except Exception as exc:
                _logger.warning("quota_store_failed", error_type=type(exc).__name__)
                raise QuotaStoreError("Quota admission could not be confirmed") from exc

    async def _settle(
        self, request_id: str, *, release: bool, actual_input_tokens: int | None
    ) -> None:
        async with self._lock:
            try:
                owners = []
                now = self._now()
                for group in self._quota_limits:
                    entity = await self._client.get_entity(_partition(group), ROW_KEY)
                    if entity is not None and any(
                        r["id"] == request_id for r in self._decode(group, entity)["records"]
                    ):
                        owners.append(group)
                if len(owners) > 1:
                    _unavailable("Quota ownership is ambiguous")
                if not owners:
                    self._owners.pop(request_id, None)
                    return
                group = owners[0]
                self._owners[request_id] = group
                for _ in range(MAX_CONFLICTS):
                    entity, state = await self._read(group, now)
                    record = next((r for r in state["records"] if r["id"] == request_id), None)
                    if record is not None and record["pending"]:
                        if release:
                            state["records"].remove(record)
                            state["daily"][record["day"]] -= 1
                        else:
                            record["pending"] = False
                            if actual_input_tokens is not None:
                                record["tokens"] = actual_input_tokens
                    if await self._write(group, entity, state):
                        self._owners.pop(request_id, None)
                        return
                    now = self._now()
                _unavailable("Quota settlement contention exhausted")
            except Exception as exc:
                _logger.warning("quota_store_failed", error_type=type(exc).__name__)
                raise QuotaStoreError("Quota settlement could not be confirmed") from exc

    async def finalize_request(
        self, request_id: str, *, actual_input_tokens: int | None = None
    ) -> None:
        if actual_input_tokens is not None and (
            isinstance(actual_input_tokens, bool)
            or not isinstance(actual_input_tokens, int)
            or actual_input_tokens < 0
        ):
            _invalid("Actual quota input tokens must be non-negative")
        await self._settle(request_id, release=False, actual_input_tokens=actual_input_tokens)

    async def release_request(self, request_id: str) -> None:
        await self._settle(request_id, release=True, actual_input_tokens=None)

    async def snapshot_quota_groups(self, quota_groups: list[str]) -> dict[str, QuotaGroupSnapshot]:
        snapshots = {}
        async with self._lock:
            try:
                for group in quota_groups:
                    if group not in self._quota_limits:
                        _unavailable("Shared quota group is not configured")
                    for _ in range(MAX_CONFLICTS):
                        now = self._now()
                        entity, state = await self._read(group, now)
                        if await self._write(group, entity, state):
                            break
                    else:
                        _unavailable("Quota snapshot contention exhausted")
                    recent = [r for r in state["records"] if now - r["at"] <= WINDOW_SECONDS]
                    used = {
                        "rpm": len(recent),
                        "tpm": sum(r["tokens"] for r in recent),
                        "rpd": state["daily"].get(_date(now), 0),
                    }
                    limits = self._quota_limits[group]
                    exhausted = (
                        self._boundary(now)
                        or len(state["records"]) >= MAX_RECORDS
                        or any(used[d] >= limit for d, limit in limits.items())
                    )
                    snapshots[group] = QuotaGroupSnapshot(
                        group,
                        used["rpm"],
                        used["tpm"],
                        used["rpd"],
                        max(0, limits.get("rpm", 0) - used["rpm"]),
                        max(0, limits.get("tpm", 0) - used["tpm"]),
                        max(0, limits.get("rpd", 0) - used["rpd"]),
                        exhausted,
                        10.0 if exhausted else None,
                        tuple(sorted(limits)),
                    )
            except Exception as exc:
                _logger.warning("quota_store_failed", error_type=type(exc).__name__)
                raise QuotaStoreError("Quota snapshot could not be confirmed") from exc
            else:
                return snapshots

    async def reset(self) -> None:
        """Never erase shared usage or uncertain ownership during local reset."""
        return
