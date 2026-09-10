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
- Google AI Studio free-tier rate-limit dimensions and semantics, per Google's published docs
  (<https://ai.google.dev/gemini-api/docs/rate-limits>):
  - **RPM** (requests per minute), **TPM** (input tokens per minute), and **RPD** (requests per
    day) are enforced **independently** — staying under one does not excuse exceeding another.
  - Limits apply **per Google Cloud project, not per API key**; several keys for one project do not
    multiply the quota. Increasing throughput requires keys in **distinct projects**.
  - RPM and TPM are minute-based. Google documents only "within a minute" and does not commit to a
    rolling versus calendar-minute implementation (it reserves the explicit term "rolling 10-minute
    window" for a separate, spend-based limit that is not applicable to the Free tier). The prudent
    client design is to pace continuously and compute usage over the trailing 60 seconds.
  - RPD is a **fixed daily quota** that resets at **midnight Pacific Time** (07:00 UTC during PDT,
    08:00 UTC during PST; ~03:00 Toronto time), not a rolling 24-hour window.
  - There is **no single universal free-tier triplet**; values vary by model, variant
    (stable vs preview/experimental), and account/usage tier, and Google notes displayed limits may
    change and are not guaranteed. Exact numeric limits are configuration inputs supplied per model
    and quota group, never code constants.
  - Google recommends retrying `429 RESOURCE_EXHAUSTED` with **exponential backoff and jitter**
    (<https://ai.google.dev/gemini-api/docs/troubleshooting>).
- Deriving the owning project from an API key: AI Studio API keys (the `AIza…` form) are opaque and
  do not embed a decodable project ID. The owning project can only be resolved via the Cloud API
  Keys API (`apikeys.googleapis.com`, `keys.lookupKey`/`projects.locations.keys.get`) called with
  separate authorized credentials that have permission on that project — the key alone cannot
  self-identify. The project association is therefore taken from configuration; automated lookup is
  an optional best-effort enhancement, not a dependency.

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
- [ ] Free-tier limit values are supplied as configuration per model and quota group, not committed
      as code constants, and the model-specific values are taken from the authenticated AI Studio
      Rate Limits page.
