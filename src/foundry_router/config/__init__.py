"""Configuration management for Foundry Router."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from foundry_router.config.google_audio_output import validate_audio_output_pools
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.config.google_output import validate_image_output_pools
from foundry_router.config.google_state import (
    MAX_SIGNED_BACKENDS,
    MAX_SIGNED_REQUEST_BYTES,
    GoogleStateKeys,
    parse_state_keys,
)
from foundry_router.config.model_aliases import parse_model_aliases
from foundry_router.credit_groups import credit_membership, validate_credit_group

MAX_COMPATIBLE_MODEL_BYTES = 512
MAX_TABLE_QUOTA_AGE_SECONDS = 3600
ASCII_CONTROL_LIMIT = 32
ASCII_DELETE = 127


class BackendConfig(BaseModel):
    """Configuration for a single Foundry backend."""

    provider: Literal["azure_foundry", "google_ai_studio", "openai_compatible"] = "azure_foundry"
    api_surface: Literal["openai_compat", "native"] = "openai_compat"
    endpoint: HttpUrl
    credential: str = Field(min_length=1)
    region: str | None = None
    deployment: str | None = None
    api_version: str = "2025-04-01-preview"
    quota_group: str | None = None
    credit_metered: bool = True
    credit_group: str | None = None
    supported_operations: list[str] | None = None
    google_features: GoogleFeatureProfile = Field(default_factory=GoogleFeatureProfile)

    @model_validator(mode="before")
    @classmethod
    def validate_compatible_endpoint_input(cls, value: object) -> object:
        """Reject unsafe raw roots before URL coercion can erase dot segments."""
        if not isinstance(value, dict) or value.get("provider") != "openai_compatible":
            return value
        endpoint = value.get("endpoint")
        if endpoint is None:
            return value
        raw = str(endpoint)
        if (
            raw != raw.strip()
            or any(ord(char) < ASCII_CONTROL_LIMIT for char in raw)
            or "\\" in raw
        ):
            raise ValueError("Compatible endpoint must be a safe HTTPS API root")
        path = urlsplit(raw).path
        # This baseline accepts literal root segments, not encoded routing syntax.
        if "%" in path or any(segment in {".", ".."} for segment in path.split("/")):
            raise ValueError("Compatible endpoint cannot contain encoded or dot path segments")
        if "//" in path or unquote(path) != path:
            raise ValueError("Compatible endpoint must be a safe API root")
        if path.rstrip("/").endswith(("/chat/completions", "/embeddings", "/responses")):
            raise ValueError("Compatible endpoint must be an API root, not an operation path")
        return value

    @field_validator("credit_group")
    @classmethod
    def validate_credit_group_id(cls, v: str | None) -> str | None:
        return validate_credit_group(v) if v is not None else None

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme != "https" or v.username or v.password or v.query or v.fragment:
            raise ValueError("Backend endpoint must use HTTPS")
        return v

    @field_validator("credential")
    @classmethod
    def validate_credential(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Backend credential must not be blank")
        return v

    @field_validator("deployment")
    @classmethod
    def validate_deployment(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("Backend deployment must be a single non-empty path segment")
        return v

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        if not v.strip() or any(char in v for char in "&#?/"):
            raise ValueError("Backend API version must be a non-empty query value")
        return v

    @field_validator("quota_group")
    @classmethod
    def validate_quota_group(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Backend quota group must not be blank")
        return v

    @field_validator("supported_operations")
    @classmethod
    def validate_supported_operations(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("Backend supported_operations must not be empty")
        if len(v) != len(set(v)):
            raise ValueError("Backend supported_operations must not contain duplicates")
        allowed = {"responses", "embeddings"}
        for operation in v:
            if operation not in allowed:
                raise ValueError(
                    f"Backend supported_operations entry '{operation}' is not supported"
                )
        return list(v)

    @model_validator(mode="after")
    def validate_provider_specific_fields(self) -> BackendConfig:
        if (
            self.provider != "openai_compatible"
            and self.deployment is not None
            and ("/" in self.deployment or "\\" in self.deployment)
        ):
            raise ValueError("Backend deployment must be a single non-empty path segment")
        if self.provider == "openai_compatible":
            if (
                self.api_surface != "openai_compat"
                or self.google_features != GoogleFeatureProfile()
            ):
                raise ValueError("Compatible backends cannot use native or Google feature profiles")
            if (
                self.deployment is None
                or len(self.deployment.encode()) > MAX_COMPATIBLE_MODEL_BYTES
                or any(
                    ord(char) < ASCII_CONTROL_LIMIT or ord(char) == ASCII_DELETE
                    for char in self.deployment
                )
            ):
                raise ValueError("Compatible backend requires a bounded physical model identifier")
            if self.supported_operations is None:
                self.supported_operations = ["responses"]
            return self
        if self.provider == "azure_foundry":
            if self.api_surface != "openai_compat":
                raise ValueError("Native API surface requires a Google backend")
            if self.google_features.features:
                raise ValueError("Google feature profiles require a Google backend")
            if not self.deployment or not self.deployment.strip():
                raise ValueError("Backend deployment is required for azure_foundry backends")
            if not self.api_version or not self.api_version.strip():
                raise ValueError("Backend API version is required for azure_foundry backends")
            if self.supported_operations is None:
                self.supported_operations = ["responses", "embeddings"]
            return self

        if self.provider == "google_ai_studio":
            if (
                bool(
                    {"inline_pdfs", "inline_audio", "inline_video", "image_output", "audio_output"}
                    & set(self.google_features.features)
                )
                or self.google_features.continuation_policy == "sealed_native"
            ) and self.api_surface != "native":
                raise ValueError(
                    "File media and sealed continuation features require Google native surface"
                )
            if not self.deployment or not self.deployment.strip():
                raise ValueError(
                    "Google AI Studio model name is required for google_ai_studio backends"
                )
            endpoint_path = str(self.endpoint)
            for forbidden in ("/chat/completions", "/embeddings"):
                if forbidden in endpoint_path:
                    raise ValueError(
                        "Google AI Studio endpoint must be the service root or the "
                        f"'/v1beta/openai' compat root, not an operation path ('{forbidden}')"
                    )
            if self.supported_operations is None:
                self.supported_operations = ["responses"]
            if self.google_features.features and "responses" not in self.supported_operations:
                raise ValueError("Google features require Responses operation support")
            if self.api_surface == "native" and (
                self.supported_operations != ["responses"]
                or "/v1beta/openai" in endpoint_path
                or (
                    not self.google_features.native_thinking_disabled
                    and self.google_features.native_thinking_level is None
                    and self.google_features.continuation_policy != "sealed_native"
                    and "audio_output" not in self.google_features.features
                )
            ):
                raise ValueError(
                    "Native Google requires Responses-only, service root "
                    "and thinking-disable affirmation"
                )
            return self

        return self


class ModelBackendPool(BaseModel):
    """Backend pool configuration for a logical model."""

    backends: dict[str, float] = Field(default_factory=dict)
    continuation_policy: Literal["unsigned", "bound_history_required"] = "unsigned"

    @field_validator("backends")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("At least one backend must be configured for the model")
        for weight in v.values():
            if not math.isfinite(weight) or weight <= 0:
                raise ValueError("Backend weights must be positive")
        return v


class PricingConfig(BaseModel):
    """Token pricing for cost estimation."""

    input_per_million: float = Field(ge=0, allow_inf_nan=False)
    output_per_million: float = Field(ge=0, allow_inf_nan=False)
    image_input_tokens: int | None = Field(default=None, ge=258, exclude=True)
    pdf_document_tokens: int | None = Field(default=None, ge=258, exclude=True)
    audio_file_tokens: int | None = Field(default=None, ge=96, exclude=True)
    video_file_tokens: int | None = Field(default=None, ge=558, exclude=True)
    image_output_per_image: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    audio_output_per_second: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    # Backends configuration (JSON string)
    intake_timeout_seconds: float = Field(
        default=30.0, ge=0.1, le=120, validation_alias="FOUNDRY_INTAKE_TIMEOUT_SECONDS"
    )
    backends_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKENDS_JSON",
        description="JSON object mapping backend IDs to backend configurations",
    )

    # Models configuration (JSON string)
    models_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_MODELS_JSON",
        description="JSON object mapping logical model names to backend pools",
    )

    # Client authentication
    google_state_keys_json: SecretStr | None = Field(
        default=None,
        validation_alias="FOUNDRY_GOOGLE_STATE_KEYS_JSON",
        exclude=True,
        repr=False,
        description="Optional secret-only signed continuation key ring; enables no capability",
    )
    client_api_keys_json: str = Field(
        default="[]",
        validation_alias="FOUNDRY_CLIENT_API_KEYS_JSON",
        description="JSON array of valid client API keys",
    )

    # Admin authentication (separate from client)
    admin_api_keys_json: str = Field(
        default="[]",
        validation_alias="FOUNDRY_ADMIN_API_KEYS_JSON",
        description="JSON array of valid admin API keys",
    )

    # Cost reconciliation
    reconciliation_interval_minutes: Annotated[int, Field(ge=1, le=60)] = Field(
        default=10,
        validation_alias="FOUNDRY_RECONCILIATION_INTERVAL_MINUTES",
    )
    reconciliation_overrides_usd_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON",
        description=(
            "Optional JSON object mapping canonical credit groups to authoritative-or-mocked "
            "remaining USD values for reconciliation"
        ),
    )

    # Credit reserves
    min_credit_reserve_usd: Annotated[float, Field(ge=0, allow_inf_nan=False)] = Field(
        default=10.0,
        validation_alias="FOUNDRY_MIN_CREDIT_RESERVE_USD",
    )
    min_credit_reserve_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] = Field(
        default=5.0,
        validation_alias="FOUNDRY_MIN_CREDIT_RESERVE_PERCENT",
    )

    # Retry policy
    retry_attempts: Annotated[int, Field(ge=0, le=10)] = Field(
        default=2,
        validation_alias="FOUNDRY_RETRY_ATTEMPTS",
    )
    retry_max_delay_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = Field(
        default=30.0,
        validation_alias="FOUNDRY_RETRY_MAX_DELAY_SECONDS",
    )

    # HTTP connection pool (Phase 07)
    http_max_connections: Annotated[int, Field(ge=1, le=1000)] = Field(
        default=100,
        validation_alias="FOUNDRY_HTTP_MAX_CONNECTIONS",
        description="Maximum total HTTP connections in the pool for all backends",
    )
    http_max_keepalive_connections: Annotated[int, Field(ge=1, le=1000)] = Field(
        default=20,
        validation_alias="FOUNDRY_HTTP_MAX_KEEPALIVE_CONNECTIONS",
        description="Maximum HTTP keep-alive connections per endpoint",
    )
    http_keepalive_expiry_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = Field(
        default=30.0,
        validation_alias="FOUNDRY_HTTP_KEEPALIVE_EXPIRY_SECONDS",
        description="How long to keep idle HTTP connections alive",
    )
    http2_enabled: bool = Field(
        default=False,
        validation_alias="FOUNDRY_HTTP2_ENABLED",
        description="Enable HTTP/2 multiplexing for backend requests (requires h2 package)",
    )

    # Graceful shutdown (Phase 07)
    graceful_shutdown_timeout_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = Field(
        default=30.0,
        validation_alias="FOUNDRY_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS",
        description="Maximum time to wait for in-flight requests to complete during shutdown",
    )

    # Request intake bounds
    max_request_body_bytes: Annotated[int, Field(ge=1024, le=100_000_000)] = Field(
        default=2_097_152,
        validation_alias="FOUNDRY_MAX_REQUEST_BODY_BYTES",
        description="Maximum accepted request body size in bytes, enforced before JSON parsing",
    )

    # Reservation lifecycle safety
    reservation_max_age_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = Field(
        default=900.0,
        validation_alias="FOUNDRY_RESERVATION_MAX_AGE_SECONDS",
        description=(
            "Maximum age of an inflight credit reservation before it is reclaimed by the "
            "reaper, aligned to the backend client timeout plus margin"
        ),
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        validation_alias="FOUNDRY_LOG_LEVEL",
    )

    # Pricing (JSON string)
    pricing_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_PRICING_JSON",
        description="JSON object mapping model names to pricing configs",
    )

    # Logical model aliases (JSON string)
    model_aliases_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_MODEL_ALIASES_JSON",
        description="JSON object mapping explicit alias names to canonical model IDs",
    )

    # Google AI Studio free-tier rate limits per quota group
    quota_group_rate_limits_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON",
        description="JSON object mapping quota groups to {rpm, tpm, rpd} limits",
    )

    # Backend credit cycle start days (JSON string)
    backend_cycle_start_day_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKEND_CYCLE_START_DAY_JSON",
        description="JSON object mapping canonical credit groups to cycle start day (1-28)",
    )

    # Protected emergency fallback
    protected_emergency_fallback: bool = Field(
        default=False,
        validation_alias="FOUNDRY_PROTECTED_EMERGENCY_FALLBACK",
    )

    # Distributed state backend (Phase 11). Default memory keeps all existing
    # Settings(...) fixtures passing; table mode requires endpoint + table names.
    state_backend: Literal["memory", "table"] = Field(
        default="memory",
        validation_alias="FOUNDRY_STATE_BACKEND",
        description="State backend: process-local memory or shared Azure Table Storage",
    )
    table_endpoint: str = Field(
        default="",
        validation_alias="FOUNDRY_TABLE_ENDPOINT",
        description="Table service endpoint (https) used only when state_backend is table",
    )
    table_health_name: str = Field(
        default="routerhealth",
        validation_alias="FOUNDRY_TABLE_HEALTH_NAME",
        description="Health table name (3-63 alphanumerics, starting with a letter)",
    )
    table_credit_name: str = Field(
        default="routercredit",
        validation_alias="FOUNDRY_TABLE_CREDIT_NAME",
        description="Credit table name (3-63 alphanumerics, starting with a letter)",
    )
    table_request_timeout_seconds: Annotated[float, Field(gt=0, le=60, allow_inf_nan=False)] = (
        Field(
            default=5.0,
            validation_alias="FOUNDRY_TABLE_REQUEST_TIMEOUT_SECONDS",
            description="Bounded per-operation timeout for Table Storage reads/writes",
        )
    )
    rate_limit_replica_share: Annotated[int, Field(ge=0, le=1000)] = Field(
        default=1,
        validation_alias="FOUNDRY_RATE_LIMIT_REPLICA_SHARE",
        description="Replica divisor for per-replica quota shares (from maxReplicas)",
    )
    rate_limit_backend: Literal["memory", "table"] = Field(
        default="memory", validation_alias="FOUNDRY_RATE_LIMIT_BACKEND"
    )
    table_quota_name: str = Field(
        default="routerquota", validation_alias="FOUNDRY_TABLE_QUOTA_NAME"
    )

    # Backend local credit-cycle allowance estimates (JSON string)
    backend_cycle_allowance_usd_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON",
        description="JSON object mapping credit groups to estimated cycle allowance (USD)",
    )

    # Backend local initial remaining estimates (JSON string)
    backend_initial_estimated_remaining_usd_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON",
        description="JSON object mapping credit groups to estimated remaining credit (USD)",
    )

    # Computed fields (populated after validation)
    backends: dict[str, BackendConfig] = Field(default_factory=dict, exclude=True)
    google_state_keys: GoogleStateKeys | None = Field(default=None, exclude=True, repr=False)
    models: dict[str, ModelBackendPool] = Field(default_factory=dict, exclude=True)
    client_api_keys: list[str] = Field(default_factory=list, exclude=True)
    admin_api_keys: list[str] = Field(default_factory=list, exclude=True)
    pricing: dict[str, PricingConfig] = Field(default_factory=dict, exclude=True)
    model_aliases: dict[str, str] = Field(default_factory=dict, exclude=True)
    quota_group_rate_limits: dict[str, dict[str, int]] = Field(default_factory=dict, exclude=True)
    backend_cycle_start_day: dict[str, int] = Field(default_factory=dict, exclude=True)
    backend_cycle_allowance_usd: dict[str, float] = Field(default_factory=dict, exclude=True)
    backend_initial_estimated_remaining_usd: dict[str, float] = Field(
        default_factory=dict,
        exclude=True,
    )
    reconciliation_overrides_usd: dict[str, float] = Field(default_factory=dict, exclude=True)

    @field_validator("google_state_keys_json")
    @classmethod
    def validate_google_state_keys_json(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            parse_state_keys(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def parse_json_fields(self) -> Settings:
        if self.google_state_keys_json is not None:
            self.google_state_keys = parse_state_keys(
                self.google_state_keys_json.get_secret_value()
            )
        cycle_day_min = 1
        cycle_day_max = 28

        def load_object(raw: str, variable: str) -> dict[str, object]:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid {variable}: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise TypeError(f"{variable} must be a JSON object")
            if any(not isinstance(key, str) or not key.strip() for key in value):
                raise ValueError(f"{variable} keys must be non-empty strings")
            return value

        def load_key_list(raw: str, variable: str) -> list[str]:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid {variable}: {exc.msg}") from exc
            if not isinstance(value, list) or any(
                not isinstance(key, str) or not key.strip() for key in value
            ):
                raise ValueError(f"{variable} must be a JSON array of non-empty strings")
            if len(value) != len(set(value)):
                raise ValueError(f"{variable} must not contain duplicate keys")
            return value

        # Parse backends
        backends_data = load_object(self.backends_json, "FOUNDRY_BACKENDS_JSON")
        try:
            parsed_backends = {}
            for backend_id, value in backends_data.items():
                if not isinstance(value, dict):
                    continue
                normalised_value = dict(value)
                if normalised_value.get("quota_group") is None:
                    normalised_value["quota_group"] = backend_id
                if normalised_value.get("credit_group") is None:
                    normalised_value["credit_group"] = backend_id
                parsed_backends[backend_id] = BackendConfig(**normalised_value)
            self.backends = parsed_backends
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid FOUNDRY_BACKENDS_JSON backend entry: {exc}") from exc
        if len(self.backends) != len(backends_data):
            raise ValueError("FOUNDRY_BACKENDS_JSON values must be JSON objects")

        # Validate at least one backend configured
        if not self.backends:
            raise ValueError("At least one backend must be configured")
        credit_groups = set(credit_membership(self).values())

        # Parse models
        models_data = load_object(self.models_json, "FOUNDRY_MODELS_JSON")
        try:
            self.models = {
                k: ModelBackendPool(**v) for k, v in models_data.items() if isinstance(v, dict)
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid FOUNDRY_MODELS_JSON model entry: {exc}") from exc
        if len(self.models) != len(models_data):
            raise ValueError("FOUNDRY_MODELS_JSON values must be JSON objects")

        # Validate model backends reference existing backends
        for model_name, pool in self.models.items():
            for backend_id in pool.backends:
                if backend_id not in self.backends:
                    raise ValueError(
                        f"Model '{model_name}' references unknown backend '{backend_id}'"
                    )
            signed = [
                self.backends[name].google_features.continuation_policy == "sealed_native"
                for name in pool.backends
            ]
            if pool.continuation_policy == "bound_history_required":
                profiles = [self.backends[name].google_features for name in pool.backends]
                if (
                    not all(signed)
                    or not 1 <= len(profiles) <= MAX_SIGNED_BACKENDS
                    or any(profile != profiles[0] for profile in profiles)
                    or self.google_state_keys is None
                ):
                    raise ValueError(
                        "Bound-history pools require uniform native profiles and state keys"
                    )
                if self.max_request_body_bytes > MAX_SIGNED_REQUEST_BYTES:
                    raise ValueError("Bound-history pools require an intake limit at most 2 MiB")
                raise ValueError("Signed native runtime integration is not yet available")
            if any(signed):
                raise ValueError("Sealed native backends require a bound-history pool")
            has_metered_backend = any(
                self.backends[backend_id].credit_metered for backend_id in pool.backends
            )
            has_non_metered_backend = any(
                not self.backends[backend_id].credit_metered for backend_id in pool.backends
            )
            if has_metered_backend and has_non_metered_backend:
                raise ValueError(
                    f"Model '{model_name}' cannot mix credit-metered and non-metered backends"
                )

        # Parse logical model aliases (one-hop, canonical targets only)
        self.model_aliases = parse_model_aliases(self.model_aliases_json, set(self.models))

        # Parse client API keys
        self.client_api_keys = load_key_list(
            self.client_api_keys_json, "FOUNDRY_CLIENT_API_KEYS_JSON"
        )

        # Parse admin API keys
        self.admin_api_keys = load_key_list(self.admin_api_keys_json, "FOUNDRY_ADMIN_API_KEYS_JSON")

        # Validate at least one client key
        if not self.client_api_keys:
            raise ValueError("At least one client API key must be configured")

        # Validate at least one admin key
        if not self.admin_api_keys:
            raise ValueError("At least one admin API key must be configured")

        # Validate client and admin keys are disjoint
        client_set = set(self.client_api_keys)
        admin_set = set(self.admin_api_keys)
        if client_set & admin_set:
            raise ValueError("Client and admin API keys must be disjoint sets")

        # Parse pricing
        pricing_data = load_object(self.pricing_json, "FOUNDRY_PRICING_JSON")
        try:
            self.pricing = {
                k: PricingConfig(**v) for k, v in pricing_data.items() if isinstance(v, dict)
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid FOUNDRY_PRICING_JSON pricing entry: {exc}") from exc
        if len(self.pricing) != len(pricing_data):
            raise ValueError("FOUNDRY_PRICING_JSON values must be JSON objects")
        for alias_name in self.model_aliases:
            if alias_name in self.pricing:
                raise ValueError(
                    f"FOUNDRY_PRICING_JSON must not contain alias '{alias_name}'; "
                    "canonical target pricing is inherited"
                )
        for model_name, pool in self.models.items():
            if all(not self.backends[backend_id].credit_metered for backend_id in pool.backends):
                generated_image = any(
                    "image_output" in self.backends[name].google_features.features
                    for name in pool.backends
                )
                generated_audio = any(
                    "audio_output" in self.backends[name].google_features.features
                    for name in pool.backends
                )
                if generated_audio and any(
                    self.backends[name].google_features.audio_output_price_ceiling_usd_per_second
                    != 0
                    for name in pool.backends
                ):
                    raise ValueError("Non-metered generated audio requires zero seconds price")
                if generated_image and any(
                    self.backends[name].google_features.image_output_price_ceiling_usd != 0
                    for name in pool.backends
                ):
                    raise ValueError("Non-metered generated image requires zero image price")
                self.pricing[model_name] = PricingConfig(
                    input_per_million=0.0,
                    output_per_million=0.0,
                    image_output_per_image=0.0 if generated_image else None,
                    audio_output_per_second=0.0 if generated_audio else None,
                )
            image_bounds = [
                self.backends[backend_id].google_features.image_input_tokens
                for backend_id in pool.backends
                if "inline_images" in self.backends[backend_id].google_features.features
            ]
            pdf_profiles = [
                self.backends[backend_id].google_features
                for backend_id in pool.backends
                if "inline_pdfs" in self.backends[backend_id].google_features.features
            ]
            if pdf_profiles:
                if any(
                    self.backends[backend_id].provider != "google_ai_studio"
                    or self.backends[backend_id].api_surface != "native"
                    for backend_id in pool.backends
                ):
                    raise ValueError("Google PDF profiles require a Google-native-only pool")
                if model_name not in self.pricing:
                    raise ValueError("PDF-enabled pools require token pricing")
                self.pricing[model_name].pdf_document_tokens = max(
                    (
                        int(profile.pdf_input_tokens_per_page or 0)
                        + int(profile.pdf_native_text_tokens_per_page or 0)
                    )
                    * profile.max_pdf_pages
                    + profile.max_pdf_bytes
                    + 64
                    for profile in pdf_profiles
                )
            video_profiles = [
                self.backends[backend_id].google_features
                for backend_id in pool.backends
                if "inline_video" in self.backends[backend_id].google_features.features
            ]
            if video_profiles:
                if any(
                    self.backends[backend_id].provider != "google_ai_studio"
                    or self.backends[backend_id].api_surface != "native"
                    for backend_id in pool.backends
                ):
                    raise ValueError("Google video profiles require a Google-native-only pool")
                if model_name not in self.pricing:
                    raise ValueError("Video-enabled pools require token pricing")
                self.pricing[model_name].video_file_tokens = max(
                    int(profile.video_input_tokens_per_frame or 0) * profile.max_video_frames
                    + profile.max_video_bytes
                    + 64
                    for profile in video_profiles
                )
            audio_profiles = [
                self.backends[backend_id].google_features
                for backend_id in pool.backends
                if "inline_audio" in self.backends[backend_id].google_features.features
            ]
            if audio_profiles:
                if any(
                    self.backends[backend_id].provider != "google_ai_studio"
                    or self.backends[backend_id].api_surface != "native"
                    for backend_id in pool.backends
                ):
                    raise ValueError("Google audio profiles require a Google-native-only pool")
                if model_name not in self.pricing:
                    raise ValueError("Audio-enabled pools require token pricing")
                self.pricing[model_name].audio_file_tokens = max(
                    int(profile.audio_input_tokens_per_second or 0) * profile.max_audio_seconds + 64
                    for profile in audio_profiles
                )
            if image_bounds:
                if any(
                    self.backends[backend_id].provider != "google_ai_studio"
                    for backend_id in pool.backends
                ):
                    raise ValueError(
                        "Google image profiles require a separate Google-only model pool"
                    )
                if model_name not in self.pricing:
                    raise ValueError("Image-enabled pools require token pricing")
                self.pricing[model_name].image_input_tokens = max(
                    bound for bound in image_bounds if bound is not None
                )

        # Parse quota group rate limits
        quota_limits_data = load_object(
            self.quota_group_rate_limits_json,
            "FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON",
        )
        parsed_quota_limits: dict[str, dict[str, int]] = {}
        for quota_group, limits in quota_limits_data.items():
            if not isinstance(limits, dict):
                raise TypeError(f"Rate limits for '{quota_group}' must be a JSON object")
            parsed_limits = {}
            for key, value in limits.items():
                if key not in {"rpm", "tpm", "rpd"}:
                    raise ValueError(
                        f"Rate limit key '{key}' for quota group '{quota_group}' is not supported"
                    )
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise ValueError(
                        f"Rate limit '{key}' for quota group '{quota_group}' "
                        "must be a positive integer"
                    )
                parsed_limits[key] = value
            parsed_quota_limits[quota_group] = parsed_limits
        declared_quota_groups = {backend.quota_group for backend in self.backends.values()}
        unknown_quota_groups = parsed_quota_limits.keys() - declared_quota_groups
        if unknown_quota_groups:
            unknown_group = min(unknown_quota_groups)
            raise ValueError(f"Rate limits reference unknown quota group '{unknown_group}'")
        self.quota_group_rate_limits = parsed_quota_limits
        validate_audio_output_pools(self, backends_data)
        if any("audio_output" in b.google_features.features for b in self.backends.values()):
            raise ValueError("Generated audio runtime is unavailable pending integration gates")
        validate_image_output_pools(self, backends_data)
        # Local integration alone does not clear resource/readiness/exact-model gates.
        if any(
            "image_output" in backend.google_features.features for backend in self.backends.values()
        ):
            raise ValueError("Generated image runtime is unavailable pending integration gates")

        # Parse backend cycle start days
        cycle_data = load_object(
            self.backend_cycle_start_day_json,
            "FOUNDRY_BACKEND_CYCLE_START_DAY_JSON",
        )
        for backend_id, day in cycle_data.items():
            if (
                isinstance(day, bool)
                or not isinstance(day, int)
                or not (cycle_day_min <= day <= cycle_day_max)
            ):
                raise ValueError(f"Cycle start day for '{backend_id}' must be 1-28")
            if backend_id not in credit_groups:
                raise ValueError(f"Cycle start day references unknown backend '{backend_id}'")
            self.backend_cycle_start_day[backend_id] = day

        # Validate at least one model configured
        if not self.models:
            raise ValueError("At least one model must be configured")

        # Parse backend local credit allowance estimates
        allowance_data = load_object(
            self.backend_cycle_allowance_usd_json,
            "FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON",
        )
        for backend_id, amount in allowance_data.items():
            if backend_id not in credit_groups:
                raise ValueError(f"Cycle allowance references unknown backend '{backend_id}'")
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                raise TypeError(
                    f"Cycle allowance for '{backend_id}' must be a finite non-negative number"
                )
            amount_float = float(amount)
            if not math.isfinite(amount_float) or amount_float < 0:
                raise ValueError(
                    f"Cycle allowance for '{backend_id}' must be a finite non-negative number"
                )
            self.backend_cycle_allowance_usd[backend_id] = amount_float

        # Parse backend local initial remaining estimates
        remaining_data = load_object(
            self.backend_initial_estimated_remaining_usd_json,
            "FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON",
        )
        for backend_id, amount in remaining_data.items():
            if backend_id not in credit_groups:
                raise ValueError(
                    f"Initial estimated remaining credit references unknown backend '{backend_id}'"
                )
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                raise TypeError(
                    f"Initial estimated remaining credit for '{backend_id}' "
                    "must be a finite non-negative number"
                )
            amount_float = float(amount)
            if not math.isfinite(amount_float) or amount_float < 0:
                raise ValueError(
                    f"Initial estimated remaining credit for '{backend_id}' "
                    "must be a finite non-negative number"
                )
            self.backend_initial_estimated_remaining_usd[backend_id] = amount_float

        # Parse optional reconciliation overrides (for local-authoritative sync adapters)
        reconciliation_data = load_object(
            self.reconciliation_overrides_usd_json,
            "FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON",
        )
        for backend_id, amount in reconciliation_data.items():
            if backend_id not in credit_groups:
                raise ValueError(
                    f"Reconciliation override references unknown backend '{backend_id}'"
                )
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                raise TypeError(
                    f"Reconciliation override for '{backend_id}' "
                    "must be a finite non-negative number"
                )
            amount_float = float(amount)
            if not math.isfinite(amount_float) or amount_float < 0:
                raise ValueError(
                    f"Reconciliation override for '{backend_id}' "
                    "must be a finite non-negative number"
                )
            self.reconciliation_overrides_usd[backend_id] = amount_float

        # Phase 11: conditional state-backend validation (memory ignores storage fields
        # so existing Settings(...) fixtures keep passing).
        if self.state_backend == "table" or self.rate_limit_backend == "table":
            endpoint = (self.table_endpoint or "").strip()
            if not endpoint:
                raise ValueError("FOUNDRY_TABLE_ENDPOINT is required when state_backend is table")
            try:
                parts = urlsplit(endpoint)
            except ValueError as exc:
                raise ValueError("FOUNDRY_TABLE_ENDPOINT must be a valid https URL") from exc
            if parts.scheme != "https" or not parts.hostname:
                raise ValueError("FOUNDRY_TABLE_ENDPOINT must be a valid https URL")
            if parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError(
                    "FOUNDRY_TABLE_ENDPOINT must not carry credentials, query or fragment"
                )
            lowered = endpoint.lower()
            if (
                "sig=" in lowered
                or "se=" in lowered
                or "accountkey" in lowered
                or "sharedkey" in lowered
            ):
                raise ValueError(
                    "FOUNDRY_TABLE_ENDPOINT must not carry a key, SAS token or connection string"
                )
            name_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9]{2,62}$")
            for label, value in (
                ("FOUNDRY_TABLE_HEALTH_NAME", self.table_health_name),
                ("FOUNDRY_TABLE_CREDIT_NAME", self.table_credit_name),
                ("FOUNDRY_TABLE_QUOTA_NAME", self.table_quota_name),
            ):
                if not isinstance(value, str) or not name_pattern.match(value):
                    raise ValueError(f"{label} must be 3-63 alphanumerics starting with a letter")
        if self.rate_limit_backend == "table":
            if self.reservation_max_age_seconds > MAX_TABLE_QUOTA_AGE_SECONDS:
                raise ValueError("Table quota reservation age must be at most 3600 seconds")
            if self.table_quota_name in {self.table_health_name, self.table_credit_name}:
                raise ValueError("Quota table must be separate from health and credit tables")
            if any(
                not self.quota_group_rate_limits.get(backend.quota_group or key)
                for key, backend in self.backends.items()
            ):
                raise ValueError("Table quota requires nonempty limits for every backend group")

        return self

    def get_allowed_hostnames(self) -> set[str]:
        """Extract allowed hostnames from configured backends."""
        hostnames: set[str] = set()
        for backend in self.backends.values():
            if backend.endpoint.host:
                hostnames.add(backend.endpoint.host)
        return hostnames


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and validate application settings from a cached singleton."""
    return Settings()
