# Phase 09 Evidence

Phase 09 is `Implemented` within its planned single-process scope. Distributed quota accounting
remains `Planned` and out of scope.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Feature request source | [index.md](index.md) Objective | Multiple free Google AI Studio keys, rate-limit/cooldown tracking, success-probability selection |
| Google compatibility URL/auth confirmation | Implemented | ADR-007 | Google OpenAI compatibility URL and Google Cloud REST `x-goog-api-key` header confirmed against vendor docs fetched 2026-09-27 |
| Provider config + client tests | Implemented | `tests/unit/test_config.py`, `tests/unit/test_backends.py` | Azure defaults preserved; URL/auth and sensitive-header handling covered |
| Multi-key routing integration test | Implemented | `tests/integration/test_full_flow.py` | Three synthetic Google backends in distinct project groups; highest-headroom project selected, authenticated with that key, and exposed only by backend/group ID |
| Rate-limit state boundary tests | Implemented | `tests/unit/test_ratelimit.py` | 10 tests cover monotonic rollover, Pacific midnight/DST, cooldown expiry, reservations, actual-token reconciliation, same-group use, failover transfer, reset delay, and age-based reaping |
| Rate-limit configuration tests | Implemented | `tests/unit/test_config.py` | Positive integer bounds, supported dimensions, group references, and mixed-metering rejection |
| Quota-aware scoring tests | Implemented | `tests/unit/test_main.py`, `tests/unit/test_credit.py` | Highest headroom, three groups, deterministic identical inputs, near-limit deprioritization, and group cooldown |
| Reactive 429 + RPD reset tests | Implemented | `tests/unit/test_main.py`, `tests/unit/test_ratelimit.py` | Group-wide cooldown with/without `Retry-After`, bounded Google jitter, Pacific/DST reset, and existing streaming no-failover coverage |
| Free-tier credit handling tests | Implemented | `tests/unit/test_main.py`, `tests/unit/test_config.py` | Non-metered backend routes and passes readiness; metered Azure readiness remains strict; mixed pools rejected |
| Redaction test | Implemented | `tests/integration/test_full_flow.py`, `tests/unit/test_main.py`, `tests/unit/test_metrics.py` | Synthetic Google credential absent from response, logs, admin status, and metrics |
| Observability | Implemented | `tests/unit/test_main.py`, `tests/unit/test_metrics.py` | Admin status exposes per-key/group budget; Prometheus exports remaining, exhausted, and cooldown gauges |
| ADR | Implemented | [ADR-007](../../decisions/adr/007-provider-aware-quota-routing.md) | Linked from the decisions index; records provider, quota, scoring, and free-tier choices |
| Full test run | Implemented | `.venv/bin/python -m pytest -m "not docker" -q --cov=src/foundry_router --cov-report=term-missing --disable-warnings` | 263 passed, 1 deselected |
| Coverage report | Implemented | Same full-suite command | 88.26% total; `ratelimit.py` 95.37%, `routing/__init__.py` 81.93% |
| Lint | Implemented | `.venv/bin/ruff check src/ tests/` | All checks passed |
| Formatter | Implemented | `.venv/bin/ruff format --check src/ tests/` | All 35 files formatted; repository-wide check passes after formatting `src/foundry_router/state/table.py` |
| Type check | Implemented | `.venv/bin/mypy src/` | Success: no issues in 22 source files |
| Editor diagnostics | Implemented | VS Code diagnostics | No errors found |
| SonarQube scan | N/A | `scripts/quality/sonarqube-scan.sh` | Script is absent from the repository |
| Deep-review prompt run | Implemented | `.agents/prompts/deep-review.prompt.md` | Independent review completed; mixed-metering pools now fail config validation. Other suggestions were checked against explicit no-limit behavior, conservative minimum-headroom scoring, and reservation transfer semantics; no remaining actionable blocker was identified |
| Docker build | N/A | Docker CLI | Docker CLI unavailable in this environment |
| Documentation links | Implemented | Phase 09 documentation, README, docs hub | Relative links checked in 16 touched Markdown files; all targets exist |
