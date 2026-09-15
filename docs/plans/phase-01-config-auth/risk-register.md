# Phase 01 Risk Register

> **Status:** Superseded — see [`phase-01-hardening/risk-register.md`](../phase-01-hardening/risk-register.md) for the current risk set. Rows below are retained for history; the "Status" column reflects the outcome verified in `phase-01-hardening`, not an open Phase 01 gate.

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Pydantic Settings validation misses edge cases in YAML/env parsing | High | Extensive unit tests with malformed inputs; fail-fast startup | Mitigated — `tests/unit/test_config.py` covers malformed JSON shapes, non-string keys/secrets, non-finite numbers, duplicate keys, boolean cycle days (see `phase-01-hardening/exit-criteria.md`) |
| R2 | Log redaction fails for edge cases (nested dicts, multipart bodies) | High | Redaction processor tests with varied payload shapes; integration test scans actual log output | Mitigated — `tests/unit/test_logging.py` verifies redaction; residual exception-sanitization scope tracked as `phase-01-hardening` risk R2 |
| R3 | Allow-list bypass via DNS rebinding or IP spoofing | High | Validate hostname at request time, not just startup; use httpx URL validation | Mitigated — `tests/unit/test_backends.py` covers scheme/host/port/path/userinfo/redirect rejection; network-layer DNS rebinding remains an infrastructure-level concern outside application validation |
| R4 | Authentication timing attacks on key comparison | Medium | Use constant-time comparison (`hmac.compare_digest`) | Mitigated — `hmac.compare_digest` used in `src/foundry_router/auth/__init__.py`; further hardened in Phase 08 (F8: all configured keys compared, no early return) |
| R5 | Configuration drift between docs and implementation | Medium | Single source of truth: Settings model is authoritative; docs generated from model or reviewed in lockstep | Mitigated — `docs/configuration/index.md` and `docs/configuration/security.md` reviewed alongside `Settings` per `AGENTS.md` change workflow |
| R6 | Docker image size exceeds Container Apps limits | Low | Multi-stage build, minimal base (python:3.12-slim), .dockerignore | Mitigated — verified via `phase-01-hardening` Docker build/health evidence |
| R7 | CI pipeline flakiness due to external dependencies | Medium | Mock all external services; no network calls in tests | Mitigated — unit/integration tests mock external services; no live network calls |
| R8 | Correlation ID not propagated to backend calls | Low | Middleware injects request ID; backend client adds as header | By design — the correlation ID is echoed to the client (`x-request-id` response header) and bound to logs, but is intentionally not forwarded to the Azure backend to avoid exposing internal request IDs externally |

## Open Decisions
- **Auth scheme**: API key (simple) vs JWT (extensible) — Decision: API key for Phase 1, JWT as future enhancement
- **Settings format**: YAML file vs environment variables only — Decision: Environment variables + `.env` file via pydantic-settings (supports both)
- **Redaction scope**: Request body only vs request+response — Decision: Request body only for Phase 1 (no proxying yet); response redaction in Phase 2
- **Health check dependencies**: Should `/health/ready` check backend reachability? — Decision: No, only local config validation for Phase 1; backend health in Phase 3