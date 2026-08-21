# Phase 01 Hardening Exit Criteria

## Gate Checklist
- [x] `pytest tests/unit/ tests/integration/` passes.
- [x] Coverage is at least 80 percent and CI enforces the threshold.
- [x] `ruff check .` and `ruff format --check .` pass.
- [x] `mypy src/` passes in strict mode.
- [x] Package installation succeeds from a clean checkout.
- [x] `pip install -e ".[dev]"` succeeds from a clean checkout and matches CI.
- [x] Docker build succeeds and a configured container answers `/health/live`.
- [x] Outbound validation rejects wrong scheme, port, host, path, userinfo, and redirect destinations.
- [x] Outbound requests do not accept credential-bearing `auth` or cookie kwargs.
- [x] Exception logs contain no raw exception message or sensitive request data.
- [x] Correlation IDs are bounded and context is cleared after successful and failed requests.
- [x] Configuration rejects malformed JSON shapes, non-string keys/secrets, non-finite numbers, duplicate keys, and boolean cycle days.
- [x] Documentation does not claim routing or forwarding is implemented.

## Approval Table
| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
