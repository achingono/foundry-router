# Phase 01 Evidence

> **Status:** Superseded — see [`phase-01-hardening/evidence.md`](../phase-01-hardening/evidence.md) for the current, captured verification run.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Configuration validation tests | `tests/unit/test_config.py` | Covers valid, missing, invalid, edge cases |
| Logging redaction tests | `tests/unit/test_logging.py` | Verifies JSON format, correlation ID, secret removal |
| Authentication tests | `tests/unit/test_auth.py` | Client vs admin, valid/invalid/missing keys |
| Backend allow-list tests | `tests/unit/test_backends.py` | Allowed/blocked hosts, header stripping |
| Health endpoint tests | `tests/unit/test_main.py` | Live/ready behavior |
| Integration flow tests | `tests/integration/test_full_flow.py` | Auth → validate → forward → response |
| CI pipeline run | GitHub Actions run URL | Superseded — captured as part of `phase-01-hardening` verification |
| Docker build log | `docker build` output | Superseded — captured in `phase-01-hardening/evidence.md` (build + `/health/live` smoke test passed) |
| Coverage report | `pytest --cov=src/foundry_router --cov-report=term-missing` | Superseded — captured in `phase-01-hardening/evidence.md` (83 passed, 90.70% coverage) |
| Ruff/mypy output | Tool output | Superseded — captured in `phase-01-hardening/evidence.md` (all checks passed) |