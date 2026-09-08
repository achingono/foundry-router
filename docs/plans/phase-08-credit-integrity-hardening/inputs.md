# Phase 08 Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Deep-review findings F1–F8 | Deep-review report (this handoff) | Reviewer |
| Correlation middleware and app assembly | `src/foundry_router/main.py` | Implementation agent |
| OpenAI-compatible routes | `src/foundry_router/api/routes/openai.py` | Implementation agent |
| Shared API helpers | `src/foundry_router/api/common.py` | Implementation agent |
| Routing orchestration | `src/foundry_router/routing/__init__.py` | Implementation agent |
| Credit estimation, reservations, and cycle math | `src/foundry_router/credit.py` | Implementation agent |
| Forwarding, retries, and streaming passthrough | `src/foundry_router/forwarding/__init__.py` | Implementation agent |
| Configuration validation | `src/foundry_router/config/__init__.py` | Implementation agent |
| Readiness endpoint | `src/foundry_router/api/routes/health.py` | Implementation agent |
| Admin status endpoint | `src/foundry_router/api/routes/admin.py` | Implementation agent |
| Authentication dependencies | `src/foundry_router/auth/__init__.py` | Implementation agent |
| Existing unit and integration tests | `tests/unit/`, `tests/integration/` | Implementation agent |
| Requirements traceability | `docs/decisions/requirements-traceability.md` | Implementation agent |
| Security and observability docs | `docs/configuration/security.md`, `docs/operations/observability.md` | Implementation agent |

## Finding Reference (source work items)

| ID | Severity | Summary | Primary modules |
|---|---|---|---|
| F1 | Critical | Client `x-request-id` is used as the credit-reservation key; duplicate IDs cause under-reservation and lost cost accounting | `main.py`, `api/routes/openai.py`, `routing/__init__.py`, `credit.py` |
| F2 | Major | No request body size limit before `request.json()`; unbounded memory and recursion on the token estimator | `api/common.py`, `credit.py` |
| F3 | Major | Backends missing credit config or models missing pricing are silently unroutable with confusing 503s | `credit.py`, `config/__init__.py`, `api/routes/health.py` |
| F4 | Major | Reservations have no TTL/reaper; inflight credit can leak on client disconnect during streaming | `credit.py`, `forwarding/__init__.py` |
| F5 | Suggestion | `parse_retry_after` raises `ValueError` on non-ASCII digit `Retry-After` headers | `forwarding/__init__.py` |
| F6 | Suggestion | `sync_from_settings` runs lock-held on every request despite immutable config | `routing/__init__.py`, `credit.py` |
| F7 | Suggestion | Streaming usage extractor `json.loads` every SSE event | `forwarding/__init__.py` |
| F8 | Suggestion | Auth loop short-circuits, leaking matched-key position via timing | `auth/__init__.py` |

## Optional Inputs
- ADR-005 (state management) and ADR-006 (routing algorithm) for consistency checks.
- `AGENTS.md` working rules and required change workflow.

## Input Validation Checklist
- [ ] All required inputs are current (not from a superseded version)
- [ ] No required input is missing or in draft state
- [ ] The implemented code still matches the module map above before editing
