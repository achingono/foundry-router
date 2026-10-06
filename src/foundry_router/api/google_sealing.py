"""Request-owned sealing context and complete configured backend identity."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from foundry_router.api.google_history import project_context
from foundry_router.api.google_state import (
    StateBinding,
    StateCodec,
    check_state_deadline,
    credential_scope,
    framed_digest,
)

if TYPE_CHECKING:
    from foundry_router.api.google_work import SignedWorkLease
    from foundry_router.config import BackendConfig, Settings
from foundry_router.config.google_state import GoogleStateKeys, decode_state_key


@dataclass(frozen=True, repr=False)
class SealContext:
    """Per-request keys and caller binding; never serialized or retained globally."""

    codec: StateCodec
    bindings: tuple[tuple[str, StateBinding], ...]
    key_configuration: GoogleStateKeys
    request_digest: str
    work_lease: SignedWorkLease | None = None

    def validate(self, body: dict[str, Any]) -> None:
        if framed_digest("context", body) != self.request_digest:
            raise ValueError("Invalid provider state")

    def validate_dispatch(
        self, settings: Settings, backend_client: Any, backend: str, model: str
    ) -> None:
        if (
            backend not in settings.backends
            or model not in settings.models
            or settings.google_state_keys is not self.key_configuration
            or getattr(backend_client, "_settings", None) is not settings
            or backend_fingerprint(settings, backend, model) != self.binding(backend).configuration
        ):
            raise ValueError("Provider state is unavailable")

    def binding(self, backend: str) -> StateBinding:
        return dict(self.bindings)[backend]


def backend_fingerprint(settings: Settings, backend_id: str, model: str) -> str:
    """Bind every dispatch/admission/pricing setting without serializing credentials."""
    backend = settings.backends[backend_id]
    keys = settings.google_state_keys
    if keys is None:
        raise ValueError("Provider-state keys are unavailable")
    value = backend.model_dump(mode="json", exclude={"credential"})
    value["native_generation"] = {
        "thinkingConfig": {
            "thinkingBudget": backend.google_features.native_thinking_budget
            if backend.google_features.continuation_policy == "sealed_native"
            else 0
        },
        "responseModalities": ["TEXT"],
    }
    value["credential_binding"] = credential_scope(
        decode_state_key(keys.scope_key), backend.credential, domain="backend"
    )
    pricing = settings.pricing.get(model)
    value["pricing"] = pricing.model_dump(mode="json") if pricing is not None else None
    value["quota_limits"] = settings.quota_group_rate_limits.get(backend.quota_group or "", {})
    value["quota_replica_share"] = settings.rate_limit_replica_share
    value["credit_policy"] = {
        "cycle_start": settings.backend_cycle_start_day.get(backend.credit_group or ""),
        "cycle_allowance": settings.backend_cycle_allowance_usd.get(backend.credit_group or ""),
        "reserve_usd": settings.min_credit_reserve_usd,
        "reserve_percent": settings.min_credit_reserve_percent,
    }
    return framed_digest("context", value, max_bytes=131072)


def build_seal_context(
    settings: Settings,
    model: str,
    body: dict[str, Any],
    *,
    caller_scope: str,
    deadline: float | None = None,
    work_lease: SignedWorkLease | None = None,
) -> SealContext:
    keys = settings.google_state_keys
    if keys is None:
        raise ValueError("Provider-state keys are unavailable")
    codec = StateCodec(
        {
            name: base64.urlsafe_b64encode(decode_state_key(value))
            for name, value in keys.keys.items()
        },
        active=keys.active,
        ttl=keys.ttl_seconds,
    )
    bindings = []
    profiles = [settings.backends[name].google_features for name in settings.models[model].backends]
    if not 1 <= len(profiles) <= 256 or any(profile != profiles[0] for profile in profiles):
        raise ValueError("Signed pools require one common feature contract")
    context_digest = framed_digest("context", project_context(body, profiles[0]), max_bytes=131072)
    for backend_id in settings.models[model].backends:
        check_state_deadline(deadline)
        backend: BackendConfig = settings.backends[backend_id]
        bindings.append(
            (
                backend_id,
                StateBinding(
                    caller=caller_scope,
                    model=model,
                    backend=backend_id,
                    deployment=backend.deployment or "",
                    surface=backend.api_surface,
                    generation=keys.generation,
                    configuration=backend_fingerprint(settings, backend_id, model),
                    context=context_digest,
                ),
            )
        )
    return SealContext(codec, tuple(bindings), keys, framed_digest("context", body), work_lease)
