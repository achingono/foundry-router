"""Project quota and pool pricing prerequisites for gated generated image output."""

from __future__ import annotations

from typing import Any


def validate_image_output_pools(settings: Any, explicit_backends: dict[str, Any]) -> None:
    enabled = {
        name: backend
        for name, backend in settings.backends.items()
        if "image_output" in backend.google_features.features
    }
    if not enabled:
        return
    if settings.protected_emergency_fallback:
        raise ValueError("Generated image quota cannot use emergency fallback")
    for name, backend in enabled.items():
        group = backend.quota_group
        if not explicit_backends.get(name, {}).get("quota_group"):
            raise ValueError("Generated image requires an explicit project quota group")
        limits = settings.quota_group_rate_limits.get(group, {})
        ipm = backend.google_features.image_output_ipm
        if ipm is None or not 0 < limits.get("rpm", 0) <= ipm or limits.get("tpm", 0) <= 0:
            raise ValueError("Generated image requires RPM within IPM and input TPM")
        # Exact same credentials cannot escape a project budget through a different
        # model/key entry. Distinct keys' project membership remains operator owned.
        if any(
            other.provider == "google_ai_studio"
            and other.credential == backend.credential
            and other.quota_group != group
            for other in settings.backends.values()
        ):
            raise ValueError("Shared Google credential requires one project quota group")
    for model, pool in settings.models.items():
        profiles = [settings.backends[name].google_features for name in pool.backends]
        if not any("image_output" in p.features for p in profiles):
            continue
        if any(
            settings.backends[name].provider != "google_ai_studio"
            or settings.backends[name].api_surface != "native"
            or "image_output" not in settings.backends[name].google_features.features
            for name in pool.backends
        ) or any(p != profiles[0] for p in profiles):
            raise ValueError(
                "Generated image requires identical native output profiles in its pool"
            )
        pricing = settings.pricing.get(model)
        if (
            pricing is None
            or pricing.image_output_per_image != profiles[0].image_output_price_ceiling_usd
        ):
            raise ValueError("Generated image requires matching separate image price")
