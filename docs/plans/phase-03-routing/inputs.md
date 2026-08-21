# Phase 03 Inputs

## Required Inputs
List every document, data source, or artefact that must exist before this phase can start.

| Input | Source | Owner |
|---|---|---|
| Phase 02 forwarding implementation (main.py, backends, config) | `src/foundry_router/` | Implementation agent |
| Phase 02 test suite (unit/integration) | `tests/` | Implementation agent |
| Canonical routing policy | `docs/features/routing.md` | Architecture |
| Backend client security contract | `src/foundry_router/backends/__init__.py` | Implementation agent |
| Configuration schema with retry/cooldown settings | `src/foundry_router/config/__init__.py` | Implementation agent |

## Optional Inputs
Inputs that improve the phase but are not blockers.
- Real Azure OpenAI backend for smoke testing (not required for mocked tests)
- Load-test harness for retry/failover timing verification

## Input Validation Checklist
- [x] All required inputs are current (not from a superseded version)
- [x] No required input is missing or in draft state
- [x] Configuration schema already includes `retry_attempts`, `retry_max_delay_seconds`, and `protected_emergency_fallback` from Phase 01
