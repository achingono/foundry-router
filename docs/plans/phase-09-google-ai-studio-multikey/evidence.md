# Phase 09 Evidence

Populate this log during implementation. All rows are pending because this phase is `Planned` and
not yet implemented.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Feature request source | [index.md](index.md) Objective | Multiple free Google AI Studio keys, rate-limit/cooldown tracking, success-probability selection |
| Google compatibility URL/auth confirmation | _pending_ | Record the confirmed base URL and auth header and the documentation source in the ADR |
| Provider config + client tests | _pending_ | `tests/unit/test_config.py`, `tests/unit/test_backends.py` |
| Multi-key routing integration test | _pending_ | `tests/integration/` cross-key routing (not round-robin) with the mock backend |
| Rate-limit state boundary tests | _pending_ | Minute/day rollover, reservation vs finalization, exhaustion → cooldown, reset → active |
| Rate-limit configuration tests | _pending_ | Bounded validation, unknown-backend rejection |
| Quota-aware scoring tests | _pending_ | Highest-headroom key chosen; near-limit key skipped; deterministic; failover releases reservation |
| Reactive 429 + RPD reset tests | _pending_ | Google-style 429 with `Retry-After`; RPD reset returns key to service; no mid-stream failover |
| Free-tier credit handling tests | _pending_ | Free backend routable and passes readiness; metered backend still fails readiness when misconfigured |
| Redaction test | _pending_ | No key/credential in logs, `/admin/status`, metric labels, or errors |
| Observability | _pending_ | `/admin/status` per-key budget/cooldown; rate-limit metrics |
| ADR | _pending_ | `docs/decisions/adr/00N-provider-aware-quota-routing.md` linked from the decisions index |
| Full test run | _pending_ | `.venv/bin/python -m pytest -m "not docker" -q` |
| Coverage report | _pending_ | `--cov=src/foundry_router`, >= 80% for implemented code |
| Lint / format / type | _pending_ | `.venv/bin/ruff check`, `ruff format --check`, `.venv/bin/mypy src/` |
| SonarQube scan | _pending_ | `scripts/quality/sonarqube-scan.sh` (N/A if absent) |
| Deep-review prompt run | _pending_ | `.agents/prompts/deep-review.prompt.md` (N/A if absent) |
| Docker build | _pending_ | Note N/A if the Docker CLI is unavailable |
| Documentation updates | _pending_ | Routing, configuration, security, observability, traceability |
