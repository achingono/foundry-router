# Phase 09 Google AI Studio Multi-Key Quota-Aware Routing

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Status
Planned. No behaviour in this document is implemented yet. Implementation status labels
(`Implemented`, `Partially implemented`, `Planned`, `Design target`) must be applied to the
corresponding documentation only after the change lands and is verified.

## Objective
Allow the router to front multiple free-tier Google AI Studio (Gemini) API keys for the same
logical model and select, per request, the key with the highest estimated chance of success
rather than cycling keys round-robin. This phase adds a Google AI Studio backend provider type,
represents each API key as an independent backend within the existing model-pool machinery, and
adds proactive rate-limit accounting for requests-per-minute (RPM), input-tokens-per-minute (TPM),
and requests-per-day (RPD) that feeds the existing explainable scoring function. Because Google
enforces these limits **per Google Cloud project, not per API key**, accounting is scoped to a
configurable quota group so keys that share a project share a budget; only keys in distinct
projects add real throughput. The result is a quota-aware load balancer that avoids keys that are
rate-limited, in cooldown, or about to cross a free-tier limit, while preserving the existing
streaming, credit, health, and failover contracts.

## Design Summary
The existing routing core already selects a backend for a model from a weighted pool using an
explainable score over health (cooldown) state and credit assessment; it is not round-robin. This
phase reuses that core by mapping **one API key to one backend entry** in a model pool, so
"intelligently use the key with the highest chance of success" is realised by the existing scoring
plus a new **rate-limit health signal**:

- Each Google AI Studio key is a distinct backend with `provider: "google_ai_studio"`, the shared
  Google endpoint, and its own credential.
- Rate-limit state is scoped to a configurable **quota group** that names the Google Cloud project,
  not the key. Each Google backend declares its project via a `quota_group` value (the project ID or
  name); two keys that share a project set the same value and therefore share one RPM/TPM/RPD
  budget. When omitted, a key forms its own group by its backend ID, which is the correct default
  for the one-key-per-project deployment. To raise throughput the keys must belong to different
  projects (different `quota_group` values), because Google enforces limits per project, not per
  key.
- Window semantics follow Google's published behaviour: RPM and **input** TPM are evaluated over a
  minute, and the router computes usage over the trailing 60 seconds as a prudent assumption
  (Google documents only "within a minute" and does not commit to rolling versus calendar-minute);
  RPD is a fixed daily quota that resets at **midnight Pacific Time** (07:00 UTC during PDT, 08:00
  UTC during PST), not a rolling 24-hour window. There is no single universal free-tier triplet:
  limits vary by model, variant, and account tier, so they are configuration inputs, never code
  constants.
- The router consults remaining budget before dispatch: a key whose group is exhausted or
  nearly-exhausted scores lower (or is proactively skipped), so traffic flows to the key most
  likely to succeed.
- Reactive `429 RESOURCE_EXHAUSTED` handling continues to drive `QUOTA_COOLDOWN` through the
  existing health store, using exponential backoff with jitter (Google's recommendation); the new
  proactive signal complements it so most 429s are avoided before they occur.

Quota (rate limits) and credit (dollar allowance) remain separate concepts. Free-tier keys carry
no dollar cost, so this phase also defines how a backend can opt out of dollar-credit accounting
without tripping the Phase 08 readiness completeness checks.

## Scope

## In Scope
- A provider discriminator on backend configuration (`azure_foundry` default, `google_ai_studio`)
  and Google-specific endpoint/auth/URL handling in the backend client via the Gemini
  OpenAI-compatibility surface.
- Representing an arbitrary number of API keys as backends in a model pool (no special-case A/B or
  two-key assumptions), with a configurable quota group per backend so same-project keys share a
  budget and only distinct-project keys add throughput.
- A rate-limit state boundary (`RateLimitStore` protocol plus an in-memory single-replica
  implementation) tracking per-quota-group RPM, input TPM, and RPD with a trailing-60-second
  window for the per-minute dimensions and a midnight-Pacific reset for RPD.
- Per-key free-tier limit configuration wired through the existing settings/JSON pattern with
  bounded validation.
- A rate-limit health signal integrated into the existing explainable scoring so selection favours
  the key with the highest estimated success probability.
- Free-tier credit/pricing handling: a way to mark a backend as non-credit-metered so Phase 08
  readiness completeness checks pass, with pricing treated as zero for cost estimation.
- Observability: per-key remaining budget and cooldown surfaced in `/admin/status`; rate-limit
  metrics; secret-safe logging that never emits keys.
- Documentation updates: configuration, routing feature, security, observability, requirements
  traceability, and a new ADR for provider-aware quota-based routing.

## Out of Scope
- Distributed / multi-replica rate-limit accounting (remains `Planned`; only documented as a
  scaling boundary, consistent with ADR-005 and the existing credit state boundary).
- The Gemini native (`generateContent`) request/response schema; this phase uses the Google
  OpenAI-compatibility endpoint to reuse existing forwarding, streaming, and usage extraction.
- Any change to the streaming/SSE event-boundary contract or the "never retry or fail over after
  meaningful streaming output begins" rule.
- New client-facing endpoints, ML-based prediction, or infrastructure provisioning beyond
  configuration.
- Automatic key discovery, key rotation/minting, or Google billing integration.

## Entry Criteria
- The implemented tree matches the modules referenced in [Inputs](inputs.md).
- Phase 08 credit-integrity hardening is in place (server-owned reservation keys, readiness
  completeness checks, reservation reaper).
- The repository virtual environment `.venv/` is available for verification.
- No real Google API keys, Azure identifiers, or credentials are required for verification; tests
  use mocked backends and synthetic keys.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent planning / second-model review (required before implementation per
  `AGENTS.md`)
- Approver: Project maintainer
