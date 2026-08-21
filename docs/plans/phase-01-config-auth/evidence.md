# Phase 01 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Configuration validation tests | `tests/unit/test_config.py` | Covers valid, missing, invalid, edge cases |
| Logging redaction tests | `tests/unit/test_logging.py` | Verifies JSON format, correlation ID, secret removal |
| Authentication tests | `tests/unit/test_auth.py` | Client vs admin, valid/invalid/missing keys |
| Backend allow-list tests | `tests/unit/test_backends.py` | Allowed/blocked hosts, header stripping |
| Health endpoint tests | `tests/unit/test_main.py` | Live/ready behavior |
| Integration flow tests | `tests/integration/test_full_flow.py` | Auth → validate → forward → response |
| CI pipeline run | GitHub Actions run URL | To be captured after push |
| Docker build log | `docker build` output | To be captured |
| Coverage report | `pytest --cov=src/foundry_router --cov-report=term-missing` | To be captured |
| Ruff/mypy output | Tool output | To be captured |