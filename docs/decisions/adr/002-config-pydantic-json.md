# ADR-002: Configuration with Pydantic Settings and JSON Environment Variables

## Status
Accepted

## Context
The router needs flexible configuration supporting:
- Multiple backends with credentials, endpoints, regions
- Per-model backend pools with weights
- Separate client/admin API key sets
- Pricing, credit reserves, retry policies
- Backend-specific credit cycle start days
- Secure secret handling (no secrets in source, Git, images, logs)

## Decision
We will use **Pydantic Settings (pydantic-settings)** with **JSON-formatted environment variables** for complex structures.

Configuration is loaded from:
1. Environment variables (primary, works with Azure Container Apps secrets)
2. `.env` file (local development only, gitignored)

Complex nested structures (backends, models, pricing, keys) are provided as JSON strings in single environment variables:
- `FOUNDRY_BACKENDS_JSON`
- `FOUNDRY_MODELS_JSON`
- `FOUNDRY_CLIENT_API_KEYS_JSON`
- `FOUNDRY_ADMIN_API_KEYS_JSON`
- `FOUNDRY_PRICING_JSON`
- `FOUNDRY_BACKEND_CYCLE_START_DAY_JSON`

All settings are validated at startup with clear error messages.

## Consequences

### Positive
- Single source of truth: Settings model is authoritative; docs generated from model
- Type-safe configuration with validation at load time
- Works seamlessly with Azure Container Apps secrets (each secret → env var)
- JSON format supports arbitrary nesting without custom parsing
- Clear separation: simple scalars as individual env vars, complex objects as JSON
- Startup fails fast with actionable errors for invalid config

### Negative
- JSON in env vars can be unwieldy for very large configs (mitigated by current scope)
- Requires valid JSON syntax (validated at startup)
- No native YAML/TOML file support (but env vars are standard for containers)

### Neutral
- Local development uses `.env` file with JSON values
- Documentation must show JSON examples clearly

## Alternatives Considered
- **YAML/TOML config file**: Requires file mount in container, less cloud-native
- **Individual env vars for each field**: Explodes to dozens of vars for backends/models
- **Azure App Configuration**: Adds external dependency, overkill for this scope
- **Dynaconf**: More features but less type safety than Pydantic v2

## Related
- ADR-001: Python/FastAPI stack (Pydantic integrates naturally)
- ADR-004: Secret handling and redaction

## References
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Azure Container Apps secrets: https://learn.microsoft.com/azure/container-apps/manage-secrets