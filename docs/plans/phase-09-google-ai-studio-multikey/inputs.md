# Phase 09 Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Feature request: multiple free Google AI Studio keys, rate-limit/cooldown tracking, success-probability selection | This handoff | Reviewer |
| Backend configuration model | `src/foundry_router/config/__init__.py` (`BackendConfig`, `ModelBackendPool`, `PricingConfig`, `Settings.parse_json_fields`) | Implementation agent |
| Allow-list backend client and URL/auth construction | `src/foundry_router/backends/__init__.py` (`AllowedBackendClient._backend_url`, `_backend_headers`, `_validate_url`) | Implementation agent |
| Candidate ranking and credit-aware selection | `src/foundry_router/routing/__init__.py` (`ranked_model_backends`, `select_candidate_backend`) | Implementation agent |
| Scoring function | `src/foundry_router/credit.py` (`score_credit_assessment`, `estimate_request_cost`, `CreditAssessmentContext`) | Implementation agent |
| Health / cooldown state boundary | `src/foundry_router/health/__init__.py` (`BackendHealthState`, `InMemoryHealthStore`, `cooldown_exhausted_response`, `COOLDOWN_STATES`) | Implementation agent |
| Forwarding, retries, `429`/`Retry-After`, and cooldown triggers | `src/foundry_router/forwarding/__init__.py` (`parse_retry_after`, `set_backend_cooldown` call sites, `RETRYABLE_STATUS_CODES`) | Implementation agent |
| Distributed/in-memory state pattern | `src/foundry_router/state/__init__.py`, `src/foundry_router/state/table.py` | Implementation agent |
| Admin status and metrics | `src/foundry_router/api/routes/admin.py`, `src/foundry_router/metrics/` | Implementation agent |
| Readiness completeness checks (Phase 08) | `src/foundry_router/api/routes/health.py` (`backend_credit_config_complete`, `model_pricing_complete`) | Implementation agent |
| Model discovery route | `src/foundry_router/api/routes/openai.py` (model listing) | Implementation agent |
| Existing unit and integration tests | `tests/unit/`, `tests/integration/`, `tests/fixtures/mock_backend.py` | Implementation agent |
| Routing policy and ADR-006 | `docs/features/routing.md`, `docs/decisions/adr/006-routing-algorithm.md` | Implementation agent |
| Configuration, security, observability docs | `docs/configuration/index.md`, `docs/configuration/security.md`, `docs/operations/observability.md` | Implementation agent |
| Requirements traceability | `docs/decisions/requirements-traceability.md` | Implementation agent |

## External Reference Inputs
- Google AI Studio (Gemini API) OpenAI-compatibility base path and authentication header
  (`x-goog-api-key`). The concrete base URL and header name must be confirmed against current
  Google documentation during design and recorded in the ADR; do not hard-code an unverified URL
  in source or docs.
- Google AI Studio free-tier rate-limit dimensions (requests-per-minute, tokens-per-minute,
  requests-per-day) and their reset semantics (per-minute rolling window; per-day reset). Exact
  numeric limits are configuration inputs supplied per model/key, not constants baked into code.

## Optional Inputs
- ADR-004 (allow-list HTTP client) and ADR-005 (state management) for consistency of the new
  provider and rate-limit state boundary.
- ADR-002 (config via Pydantic + JSON) for the configuration surface pattern.
- `AGENTS.md` working rules and required change workflow.

## Input Validation Checklist
- [ ] All required inputs are current (not from a superseded version).
- [ ] No required input is missing or in draft state.
- [ ] The implemented code still matches the module map above before editing.
- [ ] The Google OpenAI-compatibility base URL and auth header have been confirmed against current
      Google documentation and recorded in the ADR.
- [ ] Free-tier limit values are supplied as configuration, not committed as code constants.
