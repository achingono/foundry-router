"""Configuration management for Foundry Router."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendConfig(BaseModel):
    """Configuration for a single Foundry backend."""

    endpoint: HttpUrl
    credential: str = Field(min_length=1)
    region: str | None = None
    deployment: str = Field(min_length=1)
    api_version: str = "2025-04-01-preview"

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
    def validate_deployment(cls, v: str) -> str:
        if not v.strip() or "/" in v or "\\" in v:
            raise ValueError("Backend deployment must be a single non-empty path segment")
        return v

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        if not v.strip() or any(char in v for char in "&#?/"):
            raise ValueError("Backend API version must be a non-empty query value")
        return v


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
            "Optional JSON object mapping backend IDs to authoritative-or-mocked "
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

    # Backend credit cycle start days (JSON string)
    backend_cycle_start_day_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKEND_CYCLE_START_DAY_JSON",
        description="JSON object mapping backend IDs to cycle start day (1-28)",
    )

    # Protected emergency fallback
    protected_emergency_fallback: bool = Field(
        default=False,
        validation_alias="FOUNDRY_PROTECTED_EMERGENCY_FALLBACK",
    )

    # Backend local credit-cycle allowance estimates (JSON string)
    backend_cycle_allowance_usd_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON",
        description="JSON object mapping backend IDs to local estimated cycle allowance (USD)",
    )

    # Backend local initial remaining estimates (JSON string)
    backend_initial_estimated_remaining_usd_json: str = Field(
        default="{}",
        validation_alias="FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON",
        description="JSON object mapping backend IDs to local estimated remaining credit (USD)",
    )

    # Computed fields (populated after validation)
    backends: dict[str, BackendConfig] = Field(default_factory=dict, exclude=True)
    models: dict[str, ModelBackendPool] = Field(default_factory=dict, exclude=True)
    client_api_keys: list[str] = Field(default_factory=list, exclude=True)
    admin_api_keys: list[str] = Field(default_factory=list, exclude=True)
    pricing: dict[str, PricingConfig] = Field(default_factory=dict, exclude=True)
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
            self.backends = {
                k: BackendConfig(**v) for k, v in backends_data.items() if isinstance(v, dict)
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid FOUNDRY_BACKENDS_JSON backend entry: {exc}") from exc
        if len(self.backends) != len(backends_data):
            raise ValueError("FOUNDRY_BACKENDS_JSON values must be JSON objects")

        # Validate at least one backend configured
        if not self.backends:
            raise ValueError("At least one backend must be configured")

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
            if backend_id not in self.backends:
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
            if backend_id not in self.backends:
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
            if backend_id not in self.backends:
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
            if backend_id not in self.backends:
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
