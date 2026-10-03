"""Azure Table Storage adapters for cross-replica state.

The client is injected deliberately so the domain package does not require an
Azure SDK at import time. An application integration can wrap the Azure Tables
client with the small async protocol below, typically using ``to_thread`` for
the SDK's synchronous calls.
"""

from __future__ import annotations

import asyncio
import math
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from foundry_router.credit import (
    BackendCreditLiveSnapshot,
    CreditAssessment,
    CreditAssessmentContext,
    CreditReservePolicy,
    CreditState,
    calculate_cycle_window,
)
from foundry_router.health import (
    COOLDOWN_STATES,
    BackendHealthSnapshot,
    BackendHealthState,
)

# Conservation thresholds govern when a USABLE backend is downgraded to CONSERVATION
# to bias traffic toward capacity that would otherwise go unused at cycle end.
# - CONSERVATION_DAYS_REMAINING_THRESHOLD (days): how close to reset to trigger; 3 days
#   is tuned for typical ~30-day monthly cycles—small enough to avoid premature throttling
#   yet early enough to drain ~5%+ projected waste. Unit: calendar days remaining (inclusive).
# - CONSERVATION_UNUSED_RATIO (fraction of cycle_allowance_usd): what counts as
#   "significant" projected unused credit (0.05 = 5%). Ratio keeps policy scale-invariant
#   across different allowance sizes.
# Both are hard-coded policy constants for now; promote to Settings (e.g.,
# FOUNDRY_CONSERVATION_* env vars) only if operational tuning demonstrates a need,
# to avoid accidental policy drift across replicas.
CONSERVATION_DAYS_REMAINING_THRESHOLD = 3
CONSERVATION_UNUSED_RATIO = 0.05

_logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class _TransactionEntity:
    """An entity operation (Create, Update, Delete) for batch transaction."""

    partition_key: str
    row_key: str
    operation: str  # "Create", "Update", "Delete", "UpdateMerge"
    entity: dict[str, Any] | None = None
    etag: str | None = None  # If not None, use conditional update


class TableEntityClient(Protocol):
    """Minimal entity operations required by the state adapters."""

    async def get_entity(self, partition_key: str, row_key: str) -> Mapping[str, object] | None: ...

    async def upsert_entity(self, entity: Mapping[str, object]) -> None: ...

    async def try_create_entity(self, entity: Mapping[str, object]) -> bool:
        """Create an entity only if absent.

        Returns True when created, False when the row already exists.
        Used for create-if-absent balance sync so a restarting replica never
        resets shared reservations or spend.
        """
        ...

    async def try_batch_transaction(self, operations: list[_TransactionEntity]) -> bool:
        """Attempt a transactional batch within one partition.

        Returns True if successful, False if ETag conflict or other recoverable error.
        """
        ...

    async def query_entities(
        self, partition_key: str, row_key_prefix: str | None = None
    ) -> list[Mapping[str, object]]:
        """List entities in a partition, optionally filtered by RowKey prefix.

        Implementations return the partition's reservation rows for the prefix;
        used for reaping and diagnostics (N2/N4).
        """
        ...


class TableEntityWriteError(RuntimeError):
    """A best-effort health-state write failed."""


class AzureTableHealthStore:
    """Health store backed by timestamped Azure Table entities.

    Health is intentionally eventually consistent per ADR-005. Each backend
    has one entity in the backend partition, and cooldown expiry is represented
    as a UTC epoch timestamp rather than a process-local monotonic clock.
    Timestamped upserts use last-write-wins semantics in the Azure client
    integration; credit state must use a separate conditional transaction path.
    """

    _ROW_KEY = "health"

    def __init__(self, client: TableEntityClient, *, cache_ttl_seconds: float = 1.0) -> None:
        if not math.isfinite(cache_ttl_seconds) or cache_ttl_seconds < 0.0:
            raise ValueError("cache_ttl_seconds must be finite and non-negative")
        self._client = client
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, BackendHealthSnapshot]] = {}

    async def set_backend_active(self, backend_id: str) -> None:
        cached = self._cache.get(backend_id)
        if cached is not None and time.monotonic() - cached[0] <= self._cache_ttl_seconds:
            if cached[1].state == BackendHealthState.ACTIVE:
                return
            if cached[1].state == BackendHealthState.DISABLED:
                return
            await self._write(backend_id, BackendHealthState.ACTIVE, 0.0)
            return
        existing = await self._client.get_entity(backend_id, self._ROW_KEY)
        if existing is not None:
            current_state = _parse_state(existing.get("state"))
            if current_state == BackendHealthState.DISABLED:
                return
            if current_state == BackendHealthState.ACTIVE:
                self._cache[backend_id] = (
                    time.monotonic(),
                    BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0),
                )
                return
        await self._write(backend_id, BackendHealthState.ACTIVE, 0.0)

    async def set_backend_cooldown(
        self,
        backend_id: str,
        *,
        state: BackendHealthState,
        cooldown_seconds: float,
    ) -> None:
        self._cache.pop(backend_id, None)
        if state not in COOLDOWN_STATES or not math.isfinite(cooldown_seconds):
            raise ValueError("cooldown state must be a cooldown state")
        duration = max(0.0, cooldown_seconds)
        existing = await self._client.get_entity(backend_id, self._ROW_KEY)
        if existing is not None:
            current_state = _parse_state(existing.get("state"))
            current_until = _parse_float(existing.get("cooldown_until"))
            if current_state == BackendHealthState.DISABLED:
                return
            if current_state in COOLDOWN_STATES and current_until >= time.time() + duration:
                return
        await self._write(backend_id, state, duration)

    async def snapshot_backend_health(
        self, backend_ids: list[str]
    ) -> dict[str, BackendHealthSnapshot]:
        snapshots = await asyncio.gather(
            *(self._snapshot_one(backend_id) for backend_id in backend_ids)
        )
        return dict(zip(backend_ids, snapshots, strict=True))

    async def reset(self) -> None:
        """Clear only local cache; never delete shared health state on shutdown."""
        self._cache.clear()

    async def _snapshot_one(self, backend_id: str) -> BackendHealthSnapshot:
        cached = self._cache.get(backend_id)
        if cached is not None and time.monotonic() - cached[0] <= self._cache_ttl_seconds:
            return cached[1]

        entity = await self._client.get_entity(backend_id, self._ROW_KEY)
        if entity is None:
            snapshot = BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0)
            self._cache[backend_id] = (time.monotonic(), snapshot)
            return snapshot

        state = _parse_state(entity.get("state"))
        cooldown_until = _parse_float(entity.get("cooldown_until"))
        now = time.time()
        if state in COOLDOWN_STATES and cooldown_until <= now:
            snapshot = BackendHealthSnapshot(BackendHealthState.ACTIVE, 0.0)
            self._cache[backend_id] = (time.monotonic(), snapshot)
            with suppress(TableEntityWriteError):
                await self._write(backend_id, BackendHealthState.ACTIVE, 0.0)
            return snapshot

        remaining = max(0.0, cooldown_until - now) if state in COOLDOWN_STATES else 0.0
        snapshot = BackendHealthSnapshot(state, remaining)
        if state in {BackendHealthState.ACTIVE, BackendHealthState.DISABLED}:
            self._cache[backend_id] = (time.monotonic(), snapshot)
        return snapshot

    async def _write(
        self, backend_id: str, state: BackendHealthState, cooldown_seconds: float
    ) -> None:
        self._cache.pop(backend_id, None)
        now = time.time()
        try:
            await self._client.upsert_entity(
                {
                    "PartitionKey": backend_id,
                    "RowKey": self._ROW_KEY,
                    "state": state.value,
                    "cooldown_until": now + cooldown_seconds,
                    "updated_at": now,
                }
            )
        except TableEntityWriteError:
            self._cache.pop(backend_id, None)
            raise
        except Exception as exc:
            self._cache.pop(backend_id, None)
            raise TableEntityWriteError("health state write failed") from exc
        if state in {BackendHealthState.ACTIVE, BackendHealthState.DISABLED}:
            self._cache[backend_id] = (
                time.monotonic(),
                BackendHealthSnapshot(state, 0.0),
            )


def _parse_state(value: object) -> BackendHealthState:
    try:
        return BackendHealthState(str(value))
    except ValueError:
        return BackendHealthState.ACTIVE


def _parse_float(value: object) -> float:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _parse_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _valid_non_negative_finite(value: float) -> bool:
    return math.isfinite(value) and value >= 0.0


@dataclass(frozen=True)
class _ReservationRow:
    """In-table representation of an inflight reservation."""

    request_id: str
    backend_id: str
    estimated_cost_usd: float
    created_at_utc: float
    state: str  # "pending", "settled", "released"


@dataclass
class _BalanceRow:
    """In-table representation of a backend's credit balance."""

    backend_id: str
    cycle_start_day: int
    cycle_allowance_usd: float
    estimated_remaining_usd: float
    reserved_inflight_usd: float
    cycle_start_utc: datetime
    etag: str | None = None


class TableEntityCreditStoreError(RuntimeError):
    """A credit store operation failed and cannot be retried safely."""


class AzureTableCreditStore:
    """Multi-replica credit store backed by Azure Table Storage with same-partition transactions.

    Each backend occupies one partition with a balance row (RowKey="balance") and per-request
    reservation rows (RowKey="req-{request_id}"). Reservation creation/release and balance
    updates are coordinated in a single transactional batch within the partition, using ETag
    guards to detect concurrent modifications. Per ADR-005, this fails closed when storage
    is unavailable; no replica-local fallback is used.
    """

    _BALANCE_ROW_KEY = "balance"
    _RESERVATION_ROW_PREFIX = "req-"

    def __init__(
        self,
        client: TableEntityClient,
        *,
        cache_ttl_seconds: float = 1.0,
        max_retries: int = 3,
        retry_backoff_ms: int = 50,
        logger: Any | None = None,
    ) -> None:
        if not math.isfinite(cache_ttl_seconds) or cache_ttl_seconds < 0.0:
            raise ValueError("cache_ttl_seconds must be finite and non-negative")
        self._client = client
        self._cache_ttl_seconds = cache_ttl_seconds
        self._max_retries = max_retries
        self._retry_backoff_ms = retry_backoff_ms
        self._lock = asyncio.Lock()
        self._partition_locks: dict[str, asyncio.Lock] = {}
        self._balance_cache: dict[str, tuple[float, _BalanceRow]] = {}
        self._configured_backend_ids: set[str] = set()
        self._last_synced_settings_id: int | None = None
        self._logger = logger or _logger

    def _partition_lock(self, backend_id: str) -> asyncio.Lock:
        return self._partition_locks.setdefault(backend_id, asyncio.Lock())

    async def sync_from_settings(self, settings: Any) -> None:
        """Initialize balance rows for all configured backends from settings.

        Create-if-absent: a starting or restarting replica never resets shared
        reservations or spend. If the row exists and the configured allowance or
        cycle-start day differs, only those configuration fields are merged via
        an ETag-guarded write, preserving ``reserved_inflight_usd`` and
        ``estimated_remaining_usd``.
        """
        if id(settings) == self._last_synced_settings_id:
            return
        now = datetime.now(UTC)
        async with self._lock:
            self._configured_backend_ids = set(settings.backends)
            sync_complete = True
            for backend_id in settings.backends:
                allowance = settings.backend_cycle_allowance_usd.get(backend_id)
                remaining = settings.backend_initial_estimated_remaining_usd.get(backend_id)
                cycle_start_day = settings.backend_cycle_start_day.get(backend_id)
                if allowance is None or remaining is None or cycle_start_day is None:
                    sync_complete = False
                    continue
                if not _valid_non_negative_finite(allowance) or not _valid_non_negative_finite(
                    remaining
                ):
                    sync_complete = False
                    continue
                cycle = calculate_cycle_window(now, cycle_start_day)
                desired = _BalanceRow(
                    backend_id=backend_id,
                    cycle_start_day=cycle_start_day,
                    cycle_allowance_usd=allowance,
                    estimated_remaining_usd=min(remaining, allowance),
                    reserved_inflight_usd=0.0,
                    cycle_start_utc=cycle.current_cycle_start_utc,
                )
                async with self._partition_lock(backend_id):
                    try:
                        stored = await self._create_balance_if_absent(backend_id, desired)
                    except Exception as exc:
                        sync_complete = False
                        self._logger.warning(
                            "credit_balance_sync_failed",
                            backend_id=backend_id,
                            error_type=type(exc).__name__,
                        )
                        continue
                    if stored is not None:
                        self._balance_cache[backend_id] = (time.monotonic(), stored)
                    else:
                        sync_complete = False
            if sync_complete:
                self._last_synced_settings_id = id(settings)

    async def _create_balance_if_absent(  # noqa: PLR0911, PLR0912
        self, backend_id: str, desired: _BalanceRow
    ) -> _BalanceRow | None:
        """Create the balance row if absent, else merge config drift. Returns cached row."""
        existing = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
        if existing is None:
            create = getattr(self._client, "try_create_entity", None)
            if create is None:
                raise TableEntityCreditStoreError(
                    "Table client must support create-if-absent balance initialization"
                )
            try:
                if await create(self._balance_to_entity(desired)):
                    # Re-read to get the ETag assigned by the service.
                    fresh = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
                    if fresh is not None:
                        return self._entity_to_balance(fresh)
                    return desired
            except TableEntityCreditStoreError:
                raise
            except Exception as exc:
                raise TableEntityCreditStoreError(
                    f"failed to sync balance for {backend_id}"
                ) from exc
            # Lost a create race: fall through and read the winner's row.
            existing = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
            if existing is None:
                return None
        stored = self._entity_to_balance(existing)
        if stored is None:
            return None
        if (
            stored.cycle_allowance_usd == desired.cycle_allowance_usd
            and stored.cycle_start_day == desired.cycle_start_day
        ):
            return stored
        # Config drift: merge only allowance/cycle-start, preserving live credit.
        merged = _BalanceRow(
            backend_id=stored.backend_id,
            cycle_start_day=desired.cycle_start_day,
            cycle_allowance_usd=desired.cycle_allowance_usd,
            estimated_remaining_usd=min(
                stored.estimated_remaining_usd, desired.cycle_allowance_usd
            ),
            reserved_inflight_usd=stored.reserved_inflight_usd,
            cycle_start_utc=stored.cycle_start_utc,
            etag=stored.etag,
        )
        ops = [
            _TransactionEntity(
                partition_key=backend_id,
                row_key=self._BALANCE_ROW_KEY,
                operation="Update",
                entity=self._balance_to_entity(merged),
                etag=stored.etag,
            ),
        ]
        for attempt in range(self._max_retries):
            try:
                if await self._client.try_batch_transaction(ops):
                    return merged
            except Exception as exc:
                self._invalidate_balance_locked(backend_id)
                raise TableEntityCreditStoreError(
                    f"failed to merge balance config for {backend_id}"
                ) from exc
            # Conflict: re-read fresh state and recompute the merge.
            self._invalidate_balance_locked(backend_id)
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_backoff_ms * (2**attempt) / 1000.0)
            fresh = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
            fresh_row = self._entity_to_balance(fresh) if fresh is not None else None
            if fresh_row is None:
                return None
            if (
                fresh_row.cycle_allowance_usd == desired.cycle_allowance_usd
                and fresh_row.cycle_start_day == desired.cycle_start_day
            ):
                return fresh_row
            merged = _BalanceRow(
                backend_id=fresh_row.backend_id,
                cycle_start_day=desired.cycle_start_day,
                cycle_allowance_usd=desired.cycle_allowance_usd,
                estimated_remaining_usd=min(
                    fresh_row.estimated_remaining_usd, desired.cycle_allowance_usd
                ),
                reserved_inflight_usd=fresh_row.reserved_inflight_usd,
                cycle_start_utc=fresh_row.cycle_start_utc,
                etag=fresh_row.etag,
            )
            ops = [
                _TransactionEntity(
                    partition_key=backend_id,
                    row_key=self._BALANCE_ROW_KEY,
                    operation="Update",
                    entity=self._balance_to_entity(merged),
                    etag=fresh_row.etag,
                ),
            ]
        self._logger.warning(
            "credit_config_merge_failed",
            backend_id=backend_id,
            error_type="batch_exhausted",
        )
        return None

    async def assess_with_context(
        self,
        backend_id: str,
        estimated_request_cost_usd: float,
        context: CreditAssessmentContext,
    ) -> CreditAssessment:
        """Context-based assess bundled via CreditAssessmentContext.

        ``reservation_max_age_seconds`` inside ``context`` is intentionally not
        piggybacked for the Table store (see ``assess`` docstring for rationale);
        parameter is retained for Protocol compatibility and acknowledged via
        ``_ = context.reservation_max_age_seconds``.
        """
        _ = context.reservation_max_age_seconds
        now = context.now_utc or datetime.now(UTC)
        async with self._partition_lock(backend_id):
            balance = await self._get_balance_locked(backend_id, now)
            if balance is None:
                return CreditAssessment(
                    state=CreditState.INSUFFICIENT_CAPACITY,
                    available_credit_usd=0.0,
                    projected_unused_credit_usd=0.0,
                    estimated_request_cost_usd=estimated_request_cost_usd,
                    cycle_allowance_usd=0.0,
                )
            return self._compute_assessment(
                balance,
                estimated_request_cost_usd,
                context.reserve_policy.min_credit_reserve_usd,
                context.reserve_policy.min_credit_reserve_percent,
                now,
            )

    async def assess(  # noqa: PLR0913 - scalar Protocol args retained for backward compat; delegates via CreditAssessmentContext
        self,
        backend_id: str,
        estimated_request_cost_usd: float,
        *,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime | None = None,
        reservation_max_age_seconds: float = math.inf,
    ) -> CreditAssessment:
        """Assess credit suitability for a backend without reserving.

        Note: ``reservation_max_age_seconds`` is intentionally not used by the
        Table-backed store. ``InMemoryCreditStore`` piggybacks a bounded sweep of
        expired reservations on ``assess``/``try_assign`` because it can iterate
        an in-process dict. ``AzureTableCreditStore`` reaps through the explicit
        ``reap_expired_reservations`` operation (partition-scoped
        ``TableEntityClient.query_entities``), invoked from the reconciliation
        loop, rather than piggybacking scans on the request path. The parameter
        is retained in the signature for ``CreditStore`` Protocol
        compatibility and to avoid implying unsupported inline semantics.
        Delegates to ``assess_with_context`` via ``CreditAssessmentContext``.
        """
        context = CreditAssessmentContext(
            reserve_policy=CreditReservePolicy(
                min_credit_reserve_usd=min_credit_reserve_usd,
                min_credit_reserve_percent=min_credit_reserve_percent,
            ),
            now_utc=now_utc,
            reservation_max_age_seconds=reservation_max_age_seconds,
        )
        return await self.assess_with_context(backend_id, estimated_request_cost_usd, context)

    async def try_assign_with_context(
        self,
        request_id: str,
        backend_id: str,
        estimated_request_cost_usd: float,
        context: CreditAssessmentContext,
    ) -> bool:
        """Context-based reservation bundled via CreditAssessmentContext."""
        _ = context.reservation_max_age_seconds
        now = context.now_utc or datetime.now(UTC)
        for attempt in range(self._max_retries):
            try:
                async with self._partition_lock(backend_id):
                    # Fresh read per attempt: a conflict invalidates the cache so
                    # retries recompute from another replica's committed state.
                    balance = await self._get_balance_fresh_locked(backend_id, now)
                    if balance is None:
                        return False

                    assessment = self._compute_assessment(
                        balance,
                        estimated_request_cost_usd,
                        context.reserve_policy.min_credit_reserve_usd,
                        context.reserve_policy.min_credit_reserve_percent,
                        now,
                    )
                    if assessment.state not in {CreditState.USABLE, CreditState.CONSERVATION}:
                        return False

                    new_balance = _BalanceRow(
                        backend_id=balance.backend_id,
                        cycle_start_day=balance.cycle_start_day,
                        cycle_allowance_usd=balance.cycle_allowance_usd,
                        estimated_remaining_usd=balance.estimated_remaining_usd,
                        reserved_inflight_usd=balance.reserved_inflight_usd
                        + estimated_request_cost_usd,
                        cycle_start_utc=balance.cycle_start_utc,
                        etag=balance.etag,
                    )
                    reservation = _ReservationRow(
                        request_id=request_id,
                        backend_id=backend_id,
                        estimated_cost_usd=estimated_request_cost_usd,
                        created_at_utc=now.timestamp(),
                        state="pending",
                    )

                    ops = [
                        _TransactionEntity(
                            partition_key=backend_id,
                            row_key=self._BALANCE_ROW_KEY,
                            operation="Update",
                            entity=self._balance_to_entity(new_balance),
                            etag=balance.etag,
                        ),
                        _TransactionEntity(
                            partition_key=backend_id,
                            row_key=f"{self._RESERVATION_ROW_PREFIX}{request_id}",
                            operation="Create",
                            entity=self._reservation_to_entity(reservation),
                        ),
                    ]

                    if await self._client.try_batch_transaction(ops):
                        self._balance_cache[backend_id] = (time.monotonic(), new_balance)
                        return True
                    self._invalidate_balance_locked(backend_id)
            except TableEntityCreditStoreError:
                async with self._partition_lock(backend_id):
                    self._invalidate_balance_locked(backend_id)
                return False
            except Exception as exc:
                async with self._partition_lock(backend_id):
                    self._invalidate_balance_locked(backend_id)
                self._logger.warning(
                    "table_reserve_transient_error",
                    backend_id=backend_id,
                    request_id=request_id,
                    error_type=type(exc).__name__,
                    attempt=attempt + 1,
                )
                return False

            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_backoff_ms * (2**attempt) / 1000.0)

        return False

    async def try_assign_reservation(  # noqa: PLR0913 - scalar Protocol args retained; delegates via CreditAssessmentContext
        self,
        request_id: str,
        backend_id: str,
        estimated_request_cost_usd: float,
        *,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime | None = None,
        reservation_max_age_seconds: float = math.inf,
    ) -> bool:
        """Attempt to reserve credit for a request. Returns True if successful.

        ``reservation_max_age_seconds`` is intentionally not piggybacked here for
        the same reason as in :meth:`assess` (no efficient Table scan via the
        injected ``TableEntityClient``). See :meth:`assess` docstring for the
        expected external reaper/TTL semantics. Parameter retained for
        ``CreditStore`` Protocol compatibility. Delegates to
        ``try_assign_with_context`` via ``CreditAssessmentContext``.
        """
        context = CreditAssessmentContext(
            reserve_policy=CreditReservePolicy(
                min_credit_reserve_usd=min_credit_reserve_usd,
                min_credit_reserve_percent=min_credit_reserve_percent,
            ),
            now_utc=now_utc,
            reservation_max_age_seconds=reservation_max_age_seconds,
        )
        return await self.try_assign_with_context(
            request_id, backend_id, estimated_request_cost_usd, context
        )

    async def finalize_request(  # noqa: PLR0912
        self,
        request_id: str,
        *,
        backend_id: str | None = None,
        charge_reserved: bool,
        charged_cost_usd: float | None,
    ) -> None:
        """Finalize a reservation by settling or releasing it.

        N3: Accepts optional ``backend_id`` to avoid N+1 scan. When provided
        by routing/streaming (which already knows the selected backend), the
        finalize is a single-partition transaction without iterating
        ``_balance_cache``.

        Every conflict retry re-reads the balance and reservation rows from
        storage and recomputes the delta from those fresh values, so a settle
        can never overwrite another replica's reservation or debit.
        """
        resolved_backend_id = backend_id
        if resolved_backend_id is None:
            async with self._lock:
                # Prefer configured partitions over the TTL cache: a replica
                # may have evicted the backend from cache while the shared
                # reservation row still exists.
                configured_backend_ids = list(self._configured_backend_ids)
                cached_backend_ids = list(self._balance_cache)
            candidates: list[str] = []
            for candidate_id in configured_backend_ids:
                if candidate_id not in candidates:
                    candidates.append(candidate_id)
            for candidate_id in cached_backend_ids:
                if candidate_id not in candidates:
                    candidates.append(candidate_id)
            for cached_backend_id in candidates:
                entity = await self._client.get_entity(
                    cached_backend_id, f"{self._RESERVATION_ROW_PREFIX}{request_id}"
                )
                if entity is not None:
                    resolved_backend_id = cached_backend_id
                    break
            if resolved_backend_id is None:
                return

        async with self._partition_lock(resolved_backend_id):
            for attempt in range(self._max_retries):
                reservation_entity = await self._client.get_entity(
                    resolved_backend_id, f"{self._RESERVATION_ROW_PREFIX}{request_id}"
                )
                if reservation_entity is None:
                    return
                reservation = self._entity_to_reservation(reservation_entity)
                if reservation is None or reservation.state != "pending":
                    return

                balance = await self._get_balance_fresh_locked(
                    resolved_backend_id, datetime.now(UTC)
                )
                if balance is None:
                    return

                charge = 0.0
                if charged_cost_usd is not None and _valid_non_negative_finite(charged_cost_usd):
                    charge = charged_cost_usd
                elif charge_reserved:
                    charge = reservation.estimated_cost_usd

                new_balance = _BalanceRow(
                    backend_id=balance.backend_id,
                    cycle_start_day=balance.cycle_start_day,
                    cycle_allowance_usd=balance.cycle_allowance_usd,
                    estimated_remaining_usd=max(0.0, balance.estimated_remaining_usd - charge),
                    reserved_inflight_usd=max(
                        0.0, balance.reserved_inflight_usd - reservation.estimated_cost_usd
                    ),
                    cycle_start_utc=balance.cycle_start_utc,
                    etag=balance.etag,
                )
                ops = [
                    _TransactionEntity(
                        partition_key=resolved_backend_id,
                        row_key=self._BALANCE_ROW_KEY,
                        operation="Update",
                        entity=self._balance_to_entity(new_balance),
                        etag=balance.etag,
                    ),
                    _TransactionEntity(
                        partition_key=resolved_backend_id,
                        row_key=f"{self._RESERVATION_ROW_PREFIX}{request_id}",
                        operation="Delete",
                    ),
                ]

                try:
                    if await self._client.try_batch_transaction(ops):
                        self._balance_cache[resolved_backend_id] = (
                            time.monotonic(),
                            new_balance,
                        )
                        return
                except Exception as exc:
                    self._invalidate_balance_locked(resolved_backend_id)
                    self._logger.warning(
                        "credit_finalize_failed",
                        backend_id=resolved_backend_id,
                        request_id=request_id,
                        error_type=type(exc).__name__,
                    )
                    return
                self._invalidate_balance_locked(resolved_backend_id)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_backoff_ms * (2**attempt) / 1000.0)
            self._logger.warning(
                "credit_finalize_failed",
                backend_id=resolved_backend_id,
                request_id=request_id,
                error_type="batch_exhausted",
            )

    async def reset(self) -> None:
        """Clear only local cache; never delete shared state on shutdown."""
        async with self._lock:
            self._balance_cache.clear()
            self._configured_backend_ids.clear()
            self._last_synced_settings_id = None

    async def apply_reconciled_remaining(
        self,
        authoritative_remaining_usd: dict[str, float],
        *,
        now_utc: datetime | None = None,
    ) -> int:
        """Apply authoritative credit updates from reconciliation."""
        now = now_utc or datetime.now(UTC)
        updated = 0
        for backend_id, amount in authoritative_remaining_usd.items():
            if isinstance(amount, bool):
                continue
            try:
                amount_float = float(amount)
            except (TypeError, ValueError):
                continue
            if not _valid_non_negative_finite(amount_float):
                continue

            async with self._partition_lock(backend_id):
                for attempt in range(self._max_retries):
                    balance = await self._get_balance_fresh_locked(backend_id, now)
                    if balance is None:
                        break

                    new_balance = _BalanceRow(
                        backend_id=balance.backend_id,
                        cycle_start_day=balance.cycle_start_day,
                        cycle_allowance_usd=balance.cycle_allowance_usd,
                        estimated_remaining_usd=min(balance.cycle_allowance_usd, amount_float),
                        reserved_inflight_usd=balance.reserved_inflight_usd,
                        cycle_start_utc=balance.cycle_start_utc,
                        etag=balance.etag,
                    )

                    ops = [
                        _TransactionEntity(
                            partition_key=backend_id,
                            row_key=self._BALANCE_ROW_KEY,
                            operation="Update",
                            entity=self._balance_to_entity(new_balance),
                            etag=balance.etag,
                        ),
                    ]

                    try:
                        if await self._client.try_batch_transaction(ops):
                            self._balance_cache[backend_id] = (time.monotonic(), new_balance)
                            updated += 1
                            break
                    except Exception:
                        self._invalidate_balance_locked(backend_id)
                        break
                    self._invalidate_balance_locked(backend_id)
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(self._retry_backoff_ms * (2**attempt) / 1000.0)

        return updated

    async def live_snapshot(
        self,
        backend_ids: list[str],
        *,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime | None = None,
    ) -> dict[str, BackendCreditLiveSnapshot]:
        """Return live per-backend credit diagnostics.

        N4: Uses partition-scoped query to compute real reservation counts/age
        when the client supports ``query_entities``; otherwise falls back to
        unknown (0/None) with documented limitation until N2 is fully wired.
        """
        now = now_utc or datetime.now(UTC)
        now_ts = now.timestamp()
        snapshots: dict[str, BackendCreditLiveSnapshot] = {}
        # Fetch balances with only short cache-lock holds so network I/O in
        # query_entities below never blocks sync/reset on the global lock.
        balances: dict[str, _BalanceRow] = {}
        for backend_id in backend_ids:
            async with self._lock:
                cached = self._balance_cache.get(backend_id)
                if cached is not None and time.monotonic() - cached[0] <= self._cache_ttl_seconds:
                    self._rollover_if_needed(cached[1], now)
                    balances[backend_id] = cached[1]
                    continue
            entity = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
            if entity is None:
                continue
            fetched = self._entity_to_balance(entity)
            if fetched is None:
                continue
            self._rollover_if_needed(fetched, now)
            async with self._lock:
                self._balance_cache[backend_id] = (time.monotonic(), fetched)
            balances[backend_id] = fetched
        for backend_id, balance in balances.items():
            cycle = calculate_cycle_window(now, balance.cycle_start_day)
            assessment = self._compute_assessment(
                balance, 0.0, min_credit_reserve_usd, min_credit_reserve_percent, now
            )

            # N4: real counts via query when available
            active_reservations = 0
            oldest_age: float | None = None
            if hasattr(self._client, "query_entities"):
                try:
                    entities = await self._client.query_entities(
                        backend_id, self._RESERVATION_ROW_PREFIX
                    )
                except Exception:
                    entities = []
                pending = []
                for ent in entities:
                    res = self._entity_to_reservation(ent)
                    if res is not None and res.state == "pending":
                        pending.append(res)
                active_reservations = len(pending)
                if pending:
                    oldest_created = min(r.created_at_utc for r in pending)
                    oldest_age = max(0.0, now_ts - oldest_created)
            else:
                # No query support - cannot determine; surface as 0/None with limitation
                active_reservations = 0
                oldest_age = None

            snapshots[backend_id] = BackendCreditLiveSnapshot(
                state=assessment.state,
                available_credit_usd=assessment.available_credit_usd,
                reserved_inflight_usd=balance.reserved_inflight_usd,
                estimated_remaining_usd=balance.estimated_remaining_usd,
                cycle_allowance_usd=balance.cycle_allowance_usd,
                current_cycle_start_utc=cycle.current_cycle_start_utc,
                next_reset_utc=cycle.next_reset_utc,
                active_reservations=active_reservations,
                oldest_reservation_age_seconds=oldest_age,
            )

        return snapshots

    async def reap_expired_reservations(  # noqa: PLR0912, PLR0915
        self,
        max_age_seconds: float,
        now_utc: datetime | None = None,
        backend_ids: list[str] | None = None,
    ) -> int:
        """Reap expired pending reservations (N2) and release inflight credit.

        Scans each partition via ``query_entities`` and transactionally deletes
        expired ``req-*`` rows while decrementing ``reserved_inflight_usd``.
        Requires ``TableEntityClient.query_entities``; otherwise no-op with
        warning. Invoked from reconciliation or periodic background task.
        Returns number of reaped reservations.
        """
        if not math.isfinite(max_age_seconds):
            return 0
        now = now_utc or datetime.now(UTC)
        cutoff = now.timestamp() - max_age_seconds
        if backend_ids is None:
            # Reap configured partitions even if initial sync has not completed.
            async with self._lock:
                backend_ids = list(self._configured_backend_ids)
        if not hasattr(self._client, "query_entities"):
            self._logger.warning("reaper_query_unsupported", error_type="missing_query")
            return 0
        reaped = 0
        for backend_id in backend_ids:
            try:
                entities = await self._client.query_entities(
                    backend_id, self._RESERVATION_ROW_PREFIX
                )
            except Exception as exc:
                self._logger.warning(
                    "reaper_query_failed",
                    backend_id=backend_id,
                    error_type=type(exc).__name__,
                )
                continue
            for ent in entities:
                reservation = self._entity_to_reservation(ent)
                if reservation is None or reservation.state != "pending":
                    continue
                if reservation.created_at_utc >= cutoff:
                    continue
                # Transactionally delete expired reservation and adjust balance.
                # Retries re-read fresh balance state and recompute the delta.
                async with self._partition_lock(backend_id):
                    success = False
                    for attempt in range(self._max_retries):
                        balance = await self._get_balance_fresh_locked(backend_id, now)
                        if balance is None:
                            break
                        # Verify still exists and still expired (race)
                        fresh = await self._client.get_entity(
                            backend_id,
                            f"{self._RESERVATION_ROW_PREFIX}{reservation.request_id}",
                        )
                        if fresh is None:
                            success = True
                            break
                        fresh_res = self._entity_to_reservation(fresh)
                        if fresh_res is None or fresh_res.state != "pending":
                            success = True
                            break
                        if fresh_res.created_at_utc >= cutoff:
                            success = True
                            break
                        new_balance = _BalanceRow(
                            backend_id=balance.backend_id,
                            cycle_start_day=balance.cycle_start_day,
                            cycle_allowance_usd=balance.cycle_allowance_usd,
                            estimated_remaining_usd=balance.estimated_remaining_usd,
                            reserved_inflight_usd=max(
                                0.0,
                                balance.reserved_inflight_usd - fresh_res.estimated_cost_usd,
                            ),
                            cycle_start_utc=balance.cycle_start_utc,
                            etag=balance.etag,
                        )
                        ops = [
                            _TransactionEntity(
                                partition_key=backend_id,
                                row_key=self._BALANCE_ROW_KEY,
                                operation="Update",
                                entity=self._balance_to_entity(new_balance),
                                etag=balance.etag,
                            ),
                            _TransactionEntity(
                                partition_key=backend_id,
                                row_key=f"{self._RESERVATION_ROW_PREFIX}{fresh_res.request_id}",
                                operation="Delete",
                            ),
                        ]
                        try:
                            if await self._client.try_batch_transaction(ops):
                                self._balance_cache[backend_id] = (
                                    time.monotonic(),
                                    new_balance,
                                )
                                reaped += 1
                                success = True
                                break
                        except Exception:
                            self._invalidate_balance_locked(backend_id)
                            break
                        self._invalidate_balance_locked(backend_id)
                        if attempt < self._max_retries - 1:
                            await asyncio.sleep(self._retry_backoff_ms * (2**attempt) / 1000.0)
                    if not success:
                        self._logger.warning(
                            "reaper_finalize_failed",
                            backend_id=backend_id,
                            request_id=reservation.request_id,
                            error_type="batch_exhausted",
                        )
        if reaped:
            self._logger.info("credit_reaper_reaped", reaped_count=reaped)
        return reaped

    def _invalidate_balance_locked(self, backend_id: str) -> None:
        """Drop the cached balance so the next read fetches fresh storage state."""
        self._balance_cache.pop(backend_id, None)

    async def _get_balance_fresh_locked(
        self, backend_id: str, now_utc: datetime
    ) -> _BalanceRow | None:
        """Fetch balance straight from storage, bypassing the read-only cache.

        Every read that feeds a write uses this path; the short-TTL cache serves
        read-only assessment and diagnostics only, so retries can never resend a
        pre-conflict balance computed from stale state.
        """
        entity = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
        if entity is None:
            self._invalidate_balance_locked(backend_id)
            return None
        fetched_balance = self._entity_to_balance(entity)
        if fetched_balance is None:
            self._invalidate_balance_locked(backend_id)
            return None
        self._rollover_if_needed(fetched_balance, now_utc)
        self._balance_cache[backend_id] = (time.monotonic(), fetched_balance)
        return fetched_balance

    async def _get_balance_locked(self, backend_id: str, now_utc: datetime) -> _BalanceRow | None:
        """Fetch or cache a balance row, handling cycle rollover. Must be called with lock held."""
        cached = self._balance_cache.get(backend_id)
        if cached is not None and time.monotonic() - cached[0] <= self._cache_ttl_seconds:
            balance = cached[1]
            self._rollover_if_needed(balance, now_utc)
            return balance

        entity = await self._client.get_entity(backend_id, self._BALANCE_ROW_KEY)
        if entity is None:
            return None

        fetched_balance = self._entity_to_balance(entity)
        if fetched_balance is None:
            return None

        self._rollover_if_needed(fetched_balance, now_utc)
        self._balance_cache[backend_id] = (time.monotonic(), fetched_balance)
        return fetched_balance

    def _rollover_if_needed(self, balance: _BalanceRow, now_utc: datetime) -> None:
        """Reset remaining credit if a new cycle has started."""
        cycle = calculate_cycle_window(now_utc, balance.cycle_start_day)
        if cycle.current_cycle_start_utc > balance.cycle_start_utc:
            balance.cycle_start_utc = cycle.current_cycle_start_utc
            balance.estimated_remaining_usd = balance.cycle_allowance_usd

    def _compute_assessment(
        self,
        balance: _BalanceRow,
        estimated_request_cost_usd: float,
        min_credit_reserve_usd: float,
        min_credit_reserve_percent: float,
        now_utc: datetime,
    ) -> CreditAssessment:
        """Compute credit assessment from balance."""
        cycle = calculate_cycle_window(now_utc, balance.cycle_start_day)
        safety_reserve = max(
            min_credit_reserve_usd,
            balance.cycle_allowance_usd * (min_credit_reserve_percent / 100.0),
        )
        available_credit = max(
            0.0,
            balance.estimated_remaining_usd - balance.reserved_inflight_usd - safety_reserve,
        )
        estimated_daily_burn = max(
            0.0,
            (balance.cycle_allowance_usd - balance.estimated_remaining_usd)
            / max(1, cycle.days_elapsed),
        )
        projected_unused = max(
            0.0,
            balance.estimated_remaining_usd - (estimated_daily_burn * cycle.days_remaining),
        )

        if available_credit <= 0:
            state = CreditState.PROTECTED
        elif estimated_request_cost_usd > available_credit:
            state = CreditState.INSUFFICIENT_CAPACITY
        elif cycle.days_remaining <= CONSERVATION_DAYS_REMAINING_THRESHOLD and projected_unused > (
            balance.cycle_allowance_usd * CONSERVATION_UNUSED_RATIO
        ):
            state = CreditState.CONSERVATION
        else:
            state = CreditState.USABLE

        return CreditAssessment(
            state=state,
            available_credit_usd=available_credit,
            projected_unused_credit_usd=projected_unused,
            estimated_request_cost_usd=estimated_request_cost_usd,
            cycle_allowance_usd=balance.cycle_allowance_usd,
        )

    def _balance_to_entity(self, balance: _BalanceRow) -> dict[str, Any]:
        """Convert balance to table entity."""
        return {
            "PartitionKey": balance.backend_id,
            "RowKey": self._BALANCE_ROW_KEY,
            "cycle_start_day": balance.cycle_start_day,
            "cycle_allowance_usd": balance.cycle_allowance_usd,
            "estimated_remaining_usd": balance.estimated_remaining_usd,
            "reserved_inflight_usd": balance.reserved_inflight_usd,
            "cycle_start_utc_timestamp": balance.cycle_start_utc.timestamp(),
            "updated_at": time.time(),
        }

    def _entity_to_balance(self, entity: Mapping[str, Any]) -> _BalanceRow | None:
        """Convert table entity to balance."""
        try:
            backend_id = str(entity.get("PartitionKey", ""))
            if not backend_id:
                return None
            cycle_start_day = _parse_int(entity.get("cycle_start_day"))
            cycle_allowance = _parse_float(entity.get("cycle_allowance_usd"))
            remaining = _parse_float(entity.get("estimated_remaining_usd"))
            reserved = _parse_float(entity.get("reserved_inflight_usd"))
            cycle_start_ts = _parse_float(entity.get("cycle_start_utc_timestamp"))

            if not _valid_non_negative_finite(cycle_allowance) or not _valid_non_negative_finite(
                remaining
            ):
                return None

            cycle_start_utc = datetime.fromtimestamp(cycle_start_ts, tz=UTC)
            etag = entity.get("odata.etag")  # Standard Azure Table Storage field

            return _BalanceRow(
                backend_id=backend_id,
                cycle_start_day=cycle_start_day,
                cycle_allowance_usd=cycle_allowance,
                estimated_remaining_usd=remaining,
                reserved_inflight_usd=reserved,
                cycle_start_utc=cycle_start_utc,
                etag=etag,
            )
        except Exception:
            return None

    def _reservation_to_entity(self, reservation: _ReservationRow) -> dict[str, Any]:
        """Convert reservation to table entity."""
        return {
            "PartitionKey": reservation.backend_id,
            "RowKey": f"{self._RESERVATION_ROW_PREFIX}{reservation.request_id}",
            "request_id": reservation.request_id,
            "backend_id": reservation.backend_id,
            "estimated_cost_usd": reservation.estimated_cost_usd,
            "created_at_utc": reservation.created_at_utc,
            "state": reservation.state,
        }

    def _entity_to_reservation(self, entity: Mapping[str, Any]) -> _ReservationRow | None:
        """Convert table entity to reservation."""
        try:
            row_key = str(entity.get("RowKey", ""))
            if not row_key.startswith(self._RESERVATION_ROW_PREFIX):
                return None
            request_id = row_key[len(self._RESERVATION_ROW_PREFIX) :]
            stored_request_id = str(entity.get("request_id", request_id))
            backend_id = str(entity.get("backend_id", ""))
            if not request_id or not backend_id or stored_request_id != request_id:
                return None
            estimated_cost = _parse_float(entity.get("estimated_cost_usd"))
            created_at = _parse_float(entity.get("created_at_utc"))
            state = str(entity.get("state", "pending"))

            if not _valid_non_negative_finite(estimated_cost):
                return None

            return _ReservationRow(
                request_id=request_id,
                backend_id=backend_id,
                estimated_cost_usd=estimated_cost,
                created_at_utc=created_at,
                state=state,
            )
        except Exception:
            return None
