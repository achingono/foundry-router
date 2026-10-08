"""Two-slot signed preparation with shielded ownership across caller cancellation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from foundry_router.api.adapters.google_native import (
    GoogleNativeAdapter,
    unsigned_ordinary_profile,
)
from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_continuation import prepare_continuation
from foundry_router.api.google_history import STATE_FIELD, carrier_tokens, project_history
from foundry_router.api.google_sealing import build_seal_context
from foundry_router.api.google_state import canonical_wire_bytes
from foundry_router.config.google_state import MAX_SIGNED_REQUEST_BYTES

if TYPE_CHECKING:
    from foundry_router.api.google_continuation import PreparedContinuation
    from foundry_router.api.google_pdf import PreparedGoogleMedia
    from foundry_router.api.google_sealing import SealContext
    from foundry_router.config import Settings

from foundry_router.api.google_work import (
    SignedIntakeError,
    SignedWorkLease,
    bounded_signed_work,
    check_deadline,
)


def _prepare(
    settings: Settings,
    model: str,
    body: dict[str, Any],
    *,
    caller: str,
    media: PreparedGoogleMedia | None,
    deadline: float,
    lease: SignedWorkLease | None = None,
) -> tuple[SealContext, PreparedContinuation | None]:
    check_deadline(deadline)
    carrier_tokens(body)
    projected, _ = project_history(body, deadline=deadline)
    ordinary_body = {
        **{key: value for key, value in body.items() if key != STATE_FIELD},
        "input": list(projected),
    }
    profile = settings.backends[next(iter(settings.models[model].backends))].google_features
    ordinary = GoogleNativeAdapter(profile=unsigned_ordinary_profile(profile))
    rejection = ordinary.check_request(
        "responses",
        ordinary_body,
        deadline_monotonic=deadline,
        prepared_media=media,
    )
    if rejection is not None:
        raise SignedIntakeError(rejection.status_code, rejection.code, rejection.message)
    check_deadline(deadline)
    context = build_seal_context(
        settings, model, body, caller_scope=caller, deadline=deadline, work_lease=lease
    )
    check_deadline(deadline)
    prepared = prepare_continuation(
        body, context.codec, dict(context.bindings), now=int(time.time()), deadline=deadline
    )
    check_deadline(deadline)
    return context, prepared


async def prepare_signed_request(
    settings: Settings,
    model: str,
    body: dict[str, Any],
    *,
    caller: str,
    media: PreparedGoogleMedia | None,
    deadline: float,
    lease: SignedWorkLease | None = None,
) -> tuple[SealContext, PreparedContinuation | None]:
    snapshot_wire = b""

    def capture() -> None:
        nonlocal snapshot_wire
        # Acquire resource ownership before copying nested content. Snapshot is
        # synchronous, before submission/first await; third callers allocate none.
        snapshot_wire = canonical_wire_bytes(body, max_bytes=MAX_SIGNED_REQUEST_BYTES)

    def work() -> tuple[SealContext, PreparedContinuation | None]:
        snapshot = load_bounded_json(snapshot_wire.decode(), max_bytes=MAX_SIGNED_REQUEST_BYTES)
        return _prepare(
            settings, model, snapshot, caller=caller, media=media, deadline=deadline, lease=lease
        )

    return await bounded_signed_work(work, deadline=deadline, before_submit=capture, lease=lease)
