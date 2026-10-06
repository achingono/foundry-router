"""Actual ASGI send owns generated-output capacity through bounded downstream delivery."""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING, Any

import anyio

from foundry_router.cleanup import protected_cleanup

if TYPE_CHECKING:
    from foundry_router.api.google_output_work import OutputInspectionLease

_STATE_KEY = "_foundry_generated_output_delivery"


class OutputDeliveryOwner:
    def __init__(self) -> None:
        self.lease: OutputInspectionLease | None = None
        self.deadline: float | None = None
        self._drain_cleanup: Any = None
        self._closed = False

    def transfer(self, lease: OutputInspectionLease, deadline: float) -> None:
        if (
            self._closed
            or self.lease is not None
            or type(deadline) not in (int, float)
            or not math.isfinite(deadline)
        ):
            raise ValueError("Invalid generated output delivery ownership")
        self.lease = lease
        self.deadline = deadline

    def close(self) -> None:
        self._closed = True
        if self.lease is not None:
            self.lease.close()
            self.lease = None

    def attach_drain_cleanup(self, callback: Any) -> None:
        if self._closed or self.lease is None or self._drain_cleanup is not None:
            raise ValueError("Invalid generated output drain ownership")
        self._drain_cleanup = callback

    async def finalize(self) -> None:
        callback, self._drain_cleanup = self._drain_cleanup, None
        try:
            self.close()
        finally:
            if callback is not None:
                with anyio.CancelScope(shield=True):
                    await protected_cleanup([callback])


class GeneratedOutputDeliveryMiddleware:
    """Outermost user middleware; HTTP middleware buffers cannot release the lease early."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        owner = OutputDeliveryOwner()
        scope.setdefault("state", {})[_STATE_KEY] = owner

        async def bounded_send(message: Any) -> None:
            if owner.lease is None:
                await send(message)
            else:
                async with asyncio.timeout_at(owner.deadline):
                    await send(message)

        try:
            await self.app(scope, receive, bounded_send)
        finally:
            await owner.finalize()


def delivery_owner(state: Any) -> OutputDeliveryOwner | None:
    owner = getattr(state, _STATE_KEY, None)
    return owner if isinstance(owner, OutputDeliveryOwner) else None
