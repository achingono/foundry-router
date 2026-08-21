# Phase 01 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Pydantic Settings validation misses edge cases in YAML/env parsing | High | Extensive unit tests with malformed inputs; fail-fast startup | Open |
| R2 | Log redaction fails for edge cases (nested dicts, multipart bodies) | High | Redaction processor tests with varied payload shapes; integration test scans actual log output | Open |
| R3 | Allow-list bypass via DNS rebinding or IP spoofing | High | Validate hostname at request time, not just startup; use httpx URL validation | Open |
| R4 | Authentication timing attacks on key comparison | Medium | Use constant-time comparison (`hmac.compare_digest`) | Open |
| R5 | Configuration drift between docs and implementation | Medium | Single source of truth: Settings model is authoritative; docs generated from model or reviewed in lockstep | Open |
| R6 | Docker image size exceeds Container Apps limits | Low | Multi-stage build, minimal base (python:3.12-slim), .dockerignore | Open |
| R7 | CI pipeline flakiness due to external dependencies | Medium | Mock all external services; no network calls in tests | Open |
| R8 | Correlation ID not propagated to backend calls | Low | Middleware injects request ID; backend client adds as header | Open |

## Open Decisions
- **Auth scheme**: API key (simple) vs JWT (extensible) — Decision: API key for Phase 1, JWT as future enhancement
- **Settings format**: YAML file vs environment variables only — Decision: Environment variables + `.env` file via pydantic-settings (supports both)
- **Redaction scope**: Request body only vs request+response — Decision: Request body only for Phase 1 (no proxying yet); response redaction in Phase 2
- **Health check dependencies**: Should `/health/ready` check backend reachability? — Decision: No, only local config validation for Phase 1; backend health in Phase 3