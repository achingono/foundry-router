# Phase 06 Distributed State Abstractions & Observability

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Introduce abstract state store protocols (`CreditStore`, `HealthStore`) with swappable implementations (in-memory reference store and distributed Redis adapter) to enable multi-worker (`--workers > 1`) and multi-replica Container App deployments. Enrich `/admin/status` with live real-time routing, health cooldown, and credit diagnostics per ADR-006, and establish Prometheus / OpenTelemetry metric exporters.

## Scope

### In Scope
- Abstract Protocol definitions for `CreditStore` and `HealthStore`.
- Distributed store backend implementation (Redis with atomic Lua scripts for reservations, releases, and cooldown tracking).
- Live diagnostic introspection on `/admin/status` (live health state, remaining cooldown seconds, spendable credit, active reservations).
- Prometheus `/metrics` and OpenTelemetry instrumentation (request rates, error codes, token throughput, spend rate, routing state distribution).
- Multi-process / multi-replica concurrency safety verification.

### Out of Scope
- Production cloud infrastructure deployment (scheduled for Phase 07).

## Entry Criteria
- Phase 05 modular architecture completed and verified.
- State management ADR (ADR-005) requirements confirmed.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
