"""Finite generated-audio pool/project quota and separate pricing prerequisites."""

from typing import Any


def validate_audio_output_pools(settings: Any, explicit_backends: dict[str, Any]) -> None:
    enabled = {
        name: backend
        for name, backend in settings.backends.items()
        if "audio_output" in backend.google_features.features
    }
    if not enabled:
        return
    if settings.protected_emergency_fallback:
        raise ValueError("Generated audio quota cannot use emergency fallback")
    for name, backend in enabled.items():
        if not explicit_backends.get(name, {}).get("quota_group"):
            raise ValueError("Generated audio requires an explicit project quota group")
        limits = settings.quota_group_rate_limits.get(backend.quota_group, {})
        ceiling = backend.google_features.audio_output_rpm
        if ceiling is None or not 0 < limits.get("rpm", 0) <= ceiling or limits.get("tpm", 0) <= 0:
            raise ValueError("Generated audio requires RPM within ceiling and input TPM")
        if any(
            other.provider == "google_ai_studio"
            and other.credential == backend.credential
            and other.quota_group != backend.quota_group
            for other in settings.backends.values()
        ):
            raise ValueError("Shared Google credential requires one project quota group")
    for model, pool in settings.models.items():
        profiles = [settings.backends[name].google_features for name in pool.backends]
        if not any("audio_output" in profile.features for profile in profiles):
            continue
        if any(
            settings.backends[name].provider != "google_ai_studio"
            or settings.backends[name].api_surface != "native"
            for name in pool.backends
        ) or any(p != profiles[0] for p in profiles):
            raise ValueError("Generated audio requires identical native profiles in its pool")
        price = settings.pricing.get(model)
        if (
            price is None
            or price.audio_output_per_second
            != profiles[0].audio_output_price_ceiling_usd_per_second
        ):
            raise ValueError("Generated audio requires matching separate seconds price")
