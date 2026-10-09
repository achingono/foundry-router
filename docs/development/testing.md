# Testing Strategy

## Status: Implemented (unit + integration + fixtures; 87.08% coverage)

Unit tests **Implemented** (`tests/unit/`: `test_config.py`, `test_auth.py`, `test_backends.py`, `test_credit.py`, `test_state.py`, `test_main.py`, `test_metrics.py`, `test_reconciliation.py`, `test_logging.py`, `test_api_common.py`) cover cycle calculation across month boundaries, leap years, start days 1 and 20, reserves, protected and conservation states, projected unused credit, scoring, weighted selection, cooldowns, failover, retry timing, safe response headers, same-backend health-state concurrency, streaming no-retry behavior, pre-output stream bounds, stream cleanup on failure and cancellation, inflight reservations, reaper, unknown models, malformed configuration, intake bounds, and negative estimates.

Integration tests **Implemented** (`tests/integration/test_full_flow.py`) use mocked backends for success, A-to-B failover, 429, 500, unavailability, both unavailable, streaming, and embeddings. Security tests cover authentication, redaction, and configured-backend restrictions.

Performance tests remain advisory; optional real-Azure end-to-end tests must be isolated from pull requests. Current feature implementation run achieves `87.08%` coverage, exceeding the `80%` gate (626 passed excluding Docker/Azurite; 14 Azurite tests passed separately). Google feature tests include actual OpenAI Python 2.8.1 stream-state consumption and stateless function replay. See [implementation evidence](../plans/google-ai-studio-tools-multimodal/implementation/evidence.md).

## Captures and test inputs

Raw plan JSON/TXT results, diagnostics and measurements are local-only and ignored. Sanitized
Markdown summaries retain historical verification scope; a fresh clone does not contain unused
captures. Eleven explicitly allowed artifacts remain because offline tests read them, including
indirect validation prerequisites. See [retained inputs](../plans/capture-history-cleanup/retained-inputs.md).
Operator validation scripts require their local capture/prerequisite files; missing captures must
be obtained or generated through a separately reviewed run. Removing captures does not authorize
replaying live traffic or recreating mutable validation ledgers. Tests use temporary copies for writes.
