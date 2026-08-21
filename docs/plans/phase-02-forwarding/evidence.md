# Phase 02 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Plan review | Independent review completed | Protocol, selection, credential, streaming, and verification gaps resolved before implementation |
| Focused tests | `tests/unit/test_main.py`, `tests/unit/test_backends.py` | Forwarding, credentials, validation, and SSE tests pass |
| Full verification | `pytest --cov`, `ruff check`, `ruff format --check`, `mypy src/` | 95 tests pass; 88.62% coverage; all quality checks pass |
| Documentation review | README and canonical docs listed in exit criteria | Status and traceability updated; future routing behavior remains Planned |

## Hardening Follow-Up

- Streaming reads the first backend chunk before committing the HTTP response status, then emits an SSE error only for failures after output begins.
- Deployments are required configuration, and readiness reports incomplete deployment configuration.
- Backend allow-list checks retain per-backend origins and base paths even when hostnames are shared.
- Equal-weight forwarding candidates select the lexicographically smallest backend ID.
- Embeddings input arrays are validated as non-empty arrays of non-empty strings before forwarding.
- Validated request correlation IDs are forwarded as `X-Request-Id`.
