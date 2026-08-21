# AGENTS.md

Contributor and coding-agent instructions for Foundry Router.

## Repository Status

This repository contains a partial foundational implementation. Configuration validation, authentication, health checks, model listing, structured logging, backend request safety, packaging, CI definitions, and non-streaming/streaming Responses and embeddings forwarding are present; health-aware routing, retries, cooldowns, credit management, and infrastructure remain planned. Do not describe planned behavior as implemented, invent Azure resource IDs, or assume that a documented endpoint is runnable. Use the status labels `Implemented`, `Partially implemented`, `Planned`, and `Design target` consistently.

## Canonical References

- Documentation hub: [`docs/index.md`](docs/index.md)
- Getting started: [`docs/getting-started/index.md`](docs/getting-started/index.md)
- Architecture: [`docs/architecture/index.md`](docs/architecture/index.md)
- Repository structure: [`docs/architecture/solution-structure.md`](docs/architecture/solution-structure.md)
- Runtime features: [`docs/features/index.md`](docs/features/index.md)
- Routing policy: [`docs/features/routing.md`](docs/features/routing.md)
- API contract: [`docs/api/index.md`](docs/api/index.md)
- Configuration: [`docs/configuration/index.md`](docs/configuration/index.md)
- Security: [`docs/configuration/security.md`](docs/configuration/security.md)
- Development: [`docs/development/index.md`](docs/development/index.md)
- Testing: [`docs/development/testing.md`](docs/development/testing.md)
- Operations: [`docs/operations/index.md`](docs/operations/index.md)
- Observability: [`docs/operations/observability.md`](docs/operations/observability.md)
- Decisions: [`docs/decisions/index.md`](docs/decisions/index.md)
- Requirements traceability: [`docs/decisions/requirements-traceability.md`](docs/decisions/requirements-traceability.md)
- Planning templates: [`docs/templates/`](docs/templates/)

## Working Rules

- Inspect the repository and canonical documentation before making assumptions.
- Keep behavior local to the owning boundary: API, backend client, routing, credit, telemetry, or infrastructure.
- Keep quota and credit as separate concepts.
- Treat local cost values as estimates; never present them as authoritative Azure balances.
- Preserve streaming and SSE event boundaries. Never retry or fail over after meaningful streaming output begins.
- Use bounded retries and explicit cooldowns. Do not swallow broad exceptions; log actionable, redacted context.
- Never hard-code credentials, subscription IDs, project IDs, endpoints, or deployment IDs.
- Allow arbitrary backend counts and model-specific pools; do not add special-case A/B routing.
- Do not log API keys, authorization headers, secrets, prompts, or model outputs.
- Add or update documentation whenever behavior, configuration, API, operations, or implementation status changes.

## Required Change Workflow

1. Inspect the current tree, `git status`, relevant canonical docs, and existing tests before editing.
2. Copy relevant blank files from [`docs/templates/`](docs/templates/) into a new folder under [`docs/plans/`](docs/plans/) and write a concrete plan.
3. Have the plan reviewed by a different model or session before implementation.
4. Implement the smallest feature-local change and associated tests; do not add infrastructure without a concrete requirement.
5. Maintain at least 80% coverage for implemented code.
6. Run focused tests, then the full verification suite, linting, formatting, type checks, and a Docker build when applicable.
7. Run `scripts/quality/sonarqube-scan.sh` when that script exists and address all `Blocker`, `Critical`, and `Major` findings.
8. Run the deep review described by [`.agents/prompts/deep-review.prompt.md`](.agents/prompts/deep-review.prompt.md) when that prompt exists, and address its findings.
9. Validate relative documentation links and review the final diff for unsupported present-tense claims or secrets.
10. Update the requirements traceability and operational documentation when the implementation changes the design.

## Implementation Priorities

Implement in this order unless a plan justifies another sequence:

1. Configuration validation, authentication, backend allow-listing, and safe redaction.
2. OpenAI-compatible Responses, embeddings, model discovery, liveness, and readiness endpoints.
3. Asynchronous backend forwarding and streaming pass-through.
4. Backend health, bounded retry, 429/5xx cooldown, and failover.
5. Credit-cycle calculations, pricing-driven estimates, safety reserves, and concurrent reservations.
6. Explainable model-specific routing and cost reconciliation.
7. Metrics, administrative status, IaC, CI/CD, and operational smoke tests.

## Planning Templates

Reusable templates live under [`docs/templates/`](docs/templates/):

- [`inputs.md`](docs/templates/inputs.md)
- [`activities.md`](docs/templates/activities.md)
- [`outputs.md`](docs/templates/outputs.md)
- [`exit-criteria.md`](docs/templates/exit-criteria.md)
- [`risk-register.md`](docs/templates/risk-register.md)
- [`evidence.md`](docs/templates/evidence.md)
