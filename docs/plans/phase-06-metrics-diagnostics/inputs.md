# Phase 06 Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| ADR-005 State Management | `docs/decisions/adr/005-state-management.md` | Architecture |
| ADR-006 Routing Algorithm | `docs/decisions/adr/006-routing-algorithm.md` | Architecture |
| Observability Specification | `docs/operations/observability.md` | Architecture |

## Optional Inputs
- Azure Table Storage connection and managed-identity configuration.
- Azure Cache for Redis client configuration only when a separately approved hot-state optimization is in scope.

## Input Validation Checklist
- [x] All required inputs are current
- [x] `HealthStore` protocol defined; `InMemoryHealthStore` is implemented and `CreditStore` is partially implemented
- [x] ADR-005 selected Azure Table Storage as the required multi-replica authoritative store
