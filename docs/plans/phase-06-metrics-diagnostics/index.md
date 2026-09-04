# Phase 06 Distributed State Abstractions & Observability

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Introduce abstract state store protocols (`CreditStore`, `HealthStore`) with swappable implementations (in-memory reference stores and Azure Table Storage adapters) to enable multi-worker (`--workers > 1`) and multi-replica Container App deployments. Enrich `/admin/status` with live real-time routing, health cooldown, and credit diagnostics per ADR-006, and establish Prometheus / OpenTelemetry metric exporters.

ADR-005 is authoritative for this phase: Azure Table Storage is the required authoritative shared store before enabling more than one replica. Azure Cache for Redis is not a Phase 06 dependency; it remains an optional later hot-state optimization, subject to a concrete latency requirement and a separate approved plan or ADR update.

Authoritative credit state must use a single Azure Table partition per backend. The backend balance row and every request-reservation row use that backend ID as their partition key, allowing a single transactional batch to atomically create, settle, or release a reservation while updating the balance. Reservation records must be idempotent and include a state, backend ID, and expiry; the store API must retain or receive the backend ID during finalization. A recovery job must safely settle or release expired unfinished reservations. Cross-partition transactions and replica-local fallback are out of scope because they could oversubscribe shared credit.

## Scope

### In Scope
- Abstract Protocol definitions for `CreditStore` and `HealthStore`.
- Azure Table Storage adapters using conditional writes and ETags for authoritative credit balances and reservation lifecycle, plus timestamped last-write-wins health/cooldown snapshots.
- Transactional, same-backend-partition reservation lifecycle and idempotent expiry recovery.
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
