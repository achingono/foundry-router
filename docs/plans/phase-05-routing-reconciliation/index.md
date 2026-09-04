# Phase 05 Modular Routing & Cost Reconciliation

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Decompose monolithic `src/foundry_router/main.py` into dedicated architectural domain modules (`routing/`, `health/`, `forwarding/`, `api/`) to enforce strict separation of concerns. Introduce authoritative cost reconciliation abstractions (e.g. Azure Cost Management billing synchronization) to adjust local credit balances while preserving fail-safe offline operation and graceful stale-cost handling.

## Scope

### In Scope
- Architectural refactoring of `src/foundry_router/main.py` into clean domain packages:
  - `src/foundry_router/health/`: Ephemeral health tracking, cooldown state transitions, and snapshotting.
  - `src/foundry_router/routing/`: Candidate selection, composite scoring (ADR-006), and failover orchestration.
  - `src/foundry_router/forwarding/`: HTTP request forwarding, streaming pass-through, bounded retries, and SSE processing.
  - `src/foundry_router/api/`: FastAPI route modules (`routes/openai.py`, `routes/admin.py`, `routes/health.py`).
- Pure cost reconciliation model:
  - Background periodic polling of Azure Cost Management / billing exports (or mockable reconciliation adapter).
  - Updating `estimated_remaining_usd` with actual reconciled spend without disrupting in-flight reservations.
  - Graceful stale-cost handling: if reconciliation fails, router continues on local estimated tracking with warning logs.
- Unit and integration tests preserving 100% regression compatibility across all existing test suites.

### Out of Scope
- Azure Table Storage shared state (scheduled for Phase 06); Redis is an optional future hot-state optimization under ADR-005.
- Public cloud infrastructure provisioning (scheduled for Phase 07).

## Entry Criteria
- Phase 04 credit scheduling and hardening completed with all tests passing.
- Architectural design review approved for module boundaries.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
