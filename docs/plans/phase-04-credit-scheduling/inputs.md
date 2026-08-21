# Phase 04 Inputs

## Required Inputs
_List every document, data source, or artefact that must exist before this phase can start._

| Input | Source | Owner |
|---|---|---|
| Phase 03 routing implementation and passing tests | `docs/plans/phase-03-routing/`, `src/foundry_router/main.py`, `tests/` | Project maintainer |
| Credit and cycle policy | `docs/features/routing.md` | Project maintainer |
| Explainable routing decision | `docs/decisions/adr/006-routing-algorithm.md` | Project maintainer |
| State ownership and replica constraints | `docs/decisions/adr/005-state-management.md` | Project maintainer |
| Validated pricing, reserve, and cycle configuration | `src/foundry_router/config/`, `docs/configuration/index.md` | Implementation agent |
| Local estimated credit snapshot contract | Phase 04 configuration schema: `cycle_start_day`, `cycle_allowance_usd`, `initial_estimated_remaining_usd`, `pricing` (input/output per 1k tokens) | Implementation agent |
| Token estimation bounds & default output limits | Phase 04 estimator spec: default char-to-token ratio (1:3), default max output tokens fallback (4096) | Implementation agent |
| Required test and quality gates | `docs/development/testing.md`, `AGENTS.md` | Implementation agent |

## Optional Inputs
- Representative request fixtures with known token counts and expected output limits.
- Azure billing-cycle examples for development-only comparison; these must not be treated as authoritative runtime data.
- Load/concurrency measurements for reservation contention.

## Input Validation Checklist
- [ ] All required inputs are current (not from a superseded version)
- [ ] No required input is missing or in draft state
