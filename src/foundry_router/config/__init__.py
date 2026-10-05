"""Configuration management for Foundry Router."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from foundry_router.credit_groups import credit_membership, validate_credit_group


class BackendConfig(BaseModel):
    """Configuration for a single Foundry backend."""

    provider: Literal["azure_foundry", "google_ai_studio"] = "azure_foundry"
    endpoint: HttpUrl
    credential: str = Field(min_length=1)
    region: str | None = None
    deployment: str | None = None
    api_version: str = "2025-04-01-preview"
    quota_group: str | None = None
    credit_metered: bool = True
    credit_group: str | None = None

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
        if not v.strip() or "/" in v or "\\" in v:
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

    @model_validator(mode="after")
    def validate_provider_specific_fields(self) -> BackendConfig:
        if self.provider == "azure_foundry":
            if not self.deployment or not self.deployment.strip():
                raise ValueError("Backend deployment is required for azure_foundry backends")
            if not self.api_version or not self.api_version.strip():
                raise ValueError("Backend API version is required for azure_foundry backends")
            return self

        if self.provider == "google_ai_studio":
            if not self.deployment or not self.deployment.strip():
                raise ValueError(
                    "Google AI Studio model name is required for google_ai_studio backends"
                )
            return self

        return self


class ModelBackendPool(BaseModel):
    """Backend pool configuration for a logical model."""

    backends: dict[str, float] = Field(default_factory=dict)

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


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Backends configuration (JSON string)
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
    models: dict[str, ModelBackendPool] = Field(default_factory=dict, exclude=True)
    client_api_keys: list[str] = Field(default_factory=list, exclude=True)
    admin_api_keys: list[str] = Field(default_factory=list, exclude=True)
    pricing: dict[str, PricingConfig] = Field(default_factory=dict, exclude=True)
    quota_group_rate_limits: dict[str, dict[str, int]] = Field(default_factory=dict, exclude=True)
    backend_cycle_start_day: dict[str, int] = Field(default_factory=dict, exclude=True)
    backend_cycle_allowance_usd: dict[str, float] = Field(default_factory=dict, exclude=True)
    backend_initial_estimated_remaining_usd: dict[str, float] = Field(
        default_factory=dict,
        exclude=True,
    )
    reconciliation_overrides_usd: dict[str, float] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="after")
    def parse_json_fields(self) -> Settings:
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
        for model_name, pool in self.models.items():
            if all(not self.backends[backend_id].credit_metered for backend_id in pool.backends):
                self.pricing[model_name] = PricingConfig(
                    input_per_million=0.0,
                    output_per_million=0.0,
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
        if self.state_backend == "table":
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
            ):
                if not isinstance(value, str) or not name_pattern.match(value):
                    raise ValueError(f"{label} must be 3-63 alphanumerics starting with a letter")

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
