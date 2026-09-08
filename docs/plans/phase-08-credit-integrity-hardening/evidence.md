# Phase 08 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Deep-review findings source | F1–F8 in [inputs.md](inputs.md) | Work-item origin for this phase |
| F1 concurrent duplicate-ID test | _add test path_ | Proves independent reservation/finalization |
| F2 oversized-body tests | _add test path_ | `Content-Length` and no-`Content-Length` cases |
| F3 config completeness tests | _add test path_ | Missing credit config and missing pricing |
| F4 reservation reaper tests | _add test path_ | Orphan reclaimed; fresh untouched; long stream not reaped |
| F5 Retry-After hardening test | _add test path_ | Non-ASCII digit header returns None |
| F6 hot-path sync removal | _add test/diff ref_ | No routing/admin/metrics regression |
| F7 stream usage extraction test | _add test path_ | Terminal usage cost unchanged |
| F8 auth constant-work test | _add test path_ | Valid key at any position authenticates |
| Full test run | _add command output ref_ | `.venv/bin/python -m pytest` |
| Coverage report | _add ref_ | >= 80% for implemented code |
| Lint / format / type | _add ref_ | Ruff, formatter, Mypy clean |
| SonarQube scan | _add ref_ | No unresolved Blocker/Critical/Major |
| Deep-review prompt run | _add ref_ | Findings addressed |
| Docker build | _add ref_ | Where applicable |
| Documentation updates | _add doc paths_ | Traceability, security, observability, configuration |
