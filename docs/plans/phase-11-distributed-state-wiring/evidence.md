# Phase 11 Evidence

## Evidence Log

| Item | Reference | Notes |
|---|---|---|
| Plan | `docs/plans/phase-11-distributed-state-wiring/` | Scope, activities, risks and gate checklist for distributed state wiring |
| Origin | `docs/plans/phase-10-bicep-existing-resource-support/risk-register.md` (R14, D11) | Phase 10 review found no provisioning or consumption path for the Table adapters; storage and client wiring moved here as one unit |
| Baseline template state | `infra/main.bicep` | No `Microsoft.Storage/storageAccounts`, tables or storage role assignment; no storage app settings |
| Baseline app state | `src/foundry_router/main.py:55-58` | In-memory health, credit, metrics and rate-limit stores are module-level globals; no Table client is constructed anywhere in `src/` |
| Baseline dependencies | `pyproject.toml` | No `azure-data-tables` or `azure-identity` dependency |
| Baseline adapter defect | `src/foundry_router/state/table.py:313-340`, `:896` | `sync_from_settings` upserts the balance row with zero reservations on every new process; unsafe across replicas (R1) |
| Baseline retry defect | `src/foundry_router/state/table.py:613-628`, `:846-862` | Settle and reaper retries refresh the ETag but resend a pre-conflict balance; cache is not invalidated on failure (R12) |
| Baseline ETag key | `src/foundry_router/state/table.py:988` | Adapter reads `"odata.etag"`; the async SDK exposes `metadata['etag']` (R11) |
| Baseline fallback bypass | `src/foundry_router/routing/__init__.py:391` | Protected emergency fallback reserves with `allow_over_limit=True` (D7) |
| Baseline limit re-sync | `src/foundry_router/routing/__init__.py:118-126` | Routing re-syncs the rate-limit store whenever its limits differ from unscaled settings (step 12) |
| Stale docstring | `src/foundry_router/state/table.py:391` | States no list/query is exposed; `query_entities` exists on the protocol |
| Rate-limit baseline | `src/foundry_router/ratelimit.py:76` | `InMemoryRateLimitStore` only; no distributed adapter (D6) |
| CI baseline | `.github/workflows/ci.yml` | No Azurite or storage-backed integration job |
| Template/app contract | Pending | Step 1 output |
| D6 maintainer decision | `risk-register.md` D6 | Option B (per-replica share of each quota limit) selected by the maintainer |
| Independent plan review | GPT-6 Sol session, 2026-10-02 | Verdict: reject pending changes (3 Blockers, 5 Majors, 4 Minors). Applied: F1 revision overlap and cut-over drain (step 16, R13); F2 SDK ETag normalisation (step 8, R11); F3 protected-fallback exemption (step 12, D7 proposed); F4 cross-resource-group module (steps 2, 5, R15); F5 recompute-on-conflict and cache bypass for writes (step 9, R12); F6 single effective-limit contract and zero-share check (step 12); F7 production cut-over runbook (step 16, R14); F8 role resolution by verified built-in GUID (step 5); F9 `azurite` marker and dedicated CI job; F11 operation-specific conflict mapping (step 8); F12 bounded readiness cache and request-path fail-closed test (step 11). F10 applied to Phase 10. Re-review pending |
| Resolved role definition ID | Pending | Recorded from the built-in role lookup, not guessed |
| Post-change validation runs | Pending | Memory, table+new, table+existing, plus negative cases |
| Two-replica deployment | Pending | Convergence, shared reservation counts, restart without reset, conflict rate |
| Post-change diff scan | Pending | No live names, IDs, endpoints, keys or connection strings |
| Post-change test and quality gates | Pending | Focused, full, `azurite`, lint, format, type check, Docker build, SonarQube, deep review |
