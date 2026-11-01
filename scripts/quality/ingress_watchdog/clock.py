"""Fail-closed clocks for lease and absolute-deadline checks."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from .errors import ClockError

MAX_CLOCK_UNCERTAINTY_NS = 2_000_000_000


@dataclass(frozen=True, slots=True)
class ClockSample:
    utc_ns: int
    boottime_ns: int
    monotonic_ns: int
    uncertainty_ns: int
    trusted: bool


class Clock(Protocol):
    def sample(self) -> ClockSample: ...


class TrustedTimeStatus(Protocol):
    def __call__(self) -> tuple[bool, int]: ...


class SystemClock:
    """Linux clock requiring an external authenticated time-health provider."""

    def __init__(self, trusted_time_status: TrustedTimeStatus) -> None:
        boottime_clock_id = getattr(time, "CLOCK_BOOTTIME", None)
        if boottime_clock_id is None:
            raise ClockError("CLOCK_BOOTTIME is unavailable on this host")
        self._boottime_clock_id = boottime_clock_id
        self._trusted_time_status = trusted_time_status

    def sample(self) -> ClockSample:
        trusted, uncertainty_ns = self._trusted_time_status()
        if uncertainty_ns < 0 or uncertainty_ns > MAX_CLOCK_UNCERTAINTY_NS:
            raise ClockError("trusted time uncertainty exceeds the approved bound")
        return ClockSample(
            utc_ns=time.time_ns(),
            boottime_ns=time.clock_gettime_ns(self._boottime_clock_id),
            monotonic_ns=time.monotonic_ns(),
            uncertainty_ns=uncertainty_ns,
            trusted=trusted,
        )


class FakeClock:
    """Deterministic clock for local tests; never use for live authorization."""

    def __init__(
        self,
        *,
        utc_ns: int = 1_800_000_000_000_000_000,
        boottime_ns: int = 10_000_000_000,
        monotonic_ns: int = 9_000_000_000,
        uncertainty_ns: int = 10_000_000,
        trusted: bool = True,
    ) -> None:
        self.utc_ns = utc_ns
        self.boottime_ns = boottime_ns
        self.monotonic_ns = monotonic_ns
        self.uncertainty_ns = uncertainty_ns
        self.trusted = trusted

    def sample(self) -> ClockSample:
        return ClockSample(
            utc_ns=self.utc_ns,
            boottime_ns=self.boottime_ns,
            monotonic_ns=self.monotonic_ns,
            uncertainty_ns=self.uncertainty_ns,
            trusted=self.trusted,
        )

    def advance(self, nanoseconds: int) -> None:
        if nanoseconds < 0:
            raise ValueError("clock cannot be advanced by a negative duration")
        self.utc_ns += nanoseconds
        self.boottime_ns += nanoseconds
        self.monotonic_ns += nanoseconds

    def suspend(self, nanoseconds: int) -> None:
        """Advance wall/boot clocks without advancing monotonic time."""
        if nanoseconds < 0:
            raise ValueError("clock cannot be advanced by a negative duration")
        self.utc_ns += nanoseconds
        self.boottime_ns += nanoseconds
