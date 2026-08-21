"""Credit reconciliation loop and status tracking."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog


class ReconciliationProvider(Protocol):
    """Fetches authoritative remaining credit snapshots."""

    async def fetch_remaining_credit(self, settings: Any) -> dict[str, float]:
        """Return backend_id -> authoritative remaining credit in USD."""


class StaticSettingsReconciliationProvider:
    """Reads reconciliation snapshots from settings for local testing and mocks."""

    async def fetch_remaining_credit(self, settings: Any) -> dict[str, float]:
        return dict(getattr(settings, "reconciliation_overrides_usd", {}))


@dataclass
class ReconciliationStatus:
    """Last reconciliation state exposed via admin diagnostics."""

    last_attempt_utc: str | None = None
    last_success_utc: str | None = None
    last_error: str | None = None
    last_updated_backends: int = 0
    consecutive_failures: int = 0


class ReconciliationLoop:
    """Periodic reconciliation coordinator.

    The loop is best-effort and never blocks request handling.
    """

    def __init__(
        self,
        *,
        provider: ReconciliationProvider,
        credit_store: Any,
        settings: Any,
        logger: Any | None = None,
    ) -> None:
        self._provider = provider
        self._credit_store = credit_store
        self._settings = settings
        self._logger = logger or structlog.get_logger(__name__)
        self._status = ReconciliationStatus()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "last_attempt_utc": self._status.last_attempt_utc,
            "last_success_utc": self._status.last_success_utc,
            "last_error": self._status.last_error,
            "last_updated_backends": self._status.last_updated_backends,
            "consecutive_failures": self._status.consecutive_failures,
            "stale": self._is_stale(),
        }

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="credit-reconciliation")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def run_once(self) -> None:
        now = datetime.now(UTC)
        self._status.last_attempt_utc = now.isoformat()
        try:
            balances = await self._provider.fetch_remaining_credit(self._settings)
            updated_count = await self._credit_store.apply_reconciled_remaining(balances)
        except Exception as exc:  # pragma: no cover - defensive boundary
            self._status.consecutive_failures += 1
            self._status.last_error = type(exc).__name__
            self._status.last_updated_backends = 0
            self._logger.warning(
                "credit_reconciliation_unavailable",
                error_type=type(exc).__name__,
                consecutive_failures=self._status.consecutive_failures,
            )
            return

        self._status.last_success_utc = now.isoformat()
        self._status.last_error = None
        self._status.last_updated_backends = updated_count
        self._status.consecutive_failures = 0
        self._logger.info(
            "credit_reconciliation_applied",
            updated_backends=updated_count,
        )

    async def _run(self) -> None:
        interval_seconds = max(1, int(self._settings.reconciliation_interval_minutes) * 60)
        await self.run_once()
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:
                await self.run_once()

    def _is_stale(self) -> bool:
        stale_after = max(1, int(self._settings.reconciliation_interval_minutes) * 60 * 2)
        if self._status.last_success_utc is None:
            if self._status.last_attempt_utc is None:
                return False
            return self._status.consecutive_failures > 0
        try:
            last_success = datetime.fromisoformat(self._status.last_success_utc)
        except ValueError:
            return True
        age_seconds = (datetime.now(UTC) - last_success).total_seconds()
        return age_seconds > stale_after
