# Phase 05 Activities

## Step-By-Step Activities

1. **Modular Codebase Refactoring**:
   - Extract health state logic into `src/foundry_router/health/`.
   - Extract candidate selection and scoring into `src/foundry_router/routing/`.
   - Extract streaming and retry execution into `src/foundry_router/forwarding/`.
   - Organize FastAPI endpoints into modular routers in `src/foundry_router/api/`.
   - Keep `src/foundry_router/main.py` as a lightweight application entry point and lifespan coordinator.

2. **Cost Reconciliation Subsystem**:
   - Implement `ReconciliationEngine` interface in `src/foundry_router/credit.py` / `src/foundry_router/reconciliation/`.
   - Add periodic reconciliation loop in application lifespan respecting `reconciliation_interval_minutes`.
   - Reconcile local remaining credit with authoritative balances when available, accounting for in-flight reservations.
   - Implement stale-cost fallback with warning logs when reconciliation is unavailable or delayed.

3. **Regression & Unit Testing**:
   - Update and split unit tests to mirror new module boundaries.
   - Add dedicated tests for reconciliation edge cases (negative adjustments, stale timestamps, upstream API failures).

## Review Focus
- Clean domain separation without circular imports.
- Zero behavioral drift in OpenAI compatibility and credit reservation semantics.
- Non-blocking reconciliation and graceful offline degradation.
