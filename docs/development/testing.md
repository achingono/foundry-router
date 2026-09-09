# Testing Strategy

## Status: Implemented (unit + integration + fixtures; 90.86% coverage)

Unit tests **Implemented** (`tests/unit/`: `test_config.py`, `test_auth.py`, `test_backends.py`, `test_credit.py`, `test_state.py`, `test_main.py`, `test_metrics.py`, `test_reconciliation.py`, `test_logging.py`, `test_api_common.py`) cover cycle calculation across month boundaries, leap years, start days 1 and 20, reserves, protected and conservation states, projected unused credit, scoring, weighted selection, cooldowns, failover, retry timing, safe response headers, same-backend health-state concurrency, streaming no-retry behavior, pre-output stream bounds, stream cleanup on failure and cancellation, inflight reservations, reaper, unknown models, malformed configuration, intake bounds, and negative estimates.

Integration tests **Implemented** (`tests/integration/test_full_flow.py`) use mocked backends for success, A-to-B failover, 429, 500, unavailability, both unavailable, streaming, and embeddings. Security tests cover authentication, redaction, and configured-backend restrictions.

Performance tests remain advisory; optional real-Azure end-to-end tests must be isolated from pull requests. Current suite achieves `90.86%` coverage, exceeding the `80%` gate (`tests/unit` + `tests/integration`, 227 passed).
