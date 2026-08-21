# Testing Strategy

## Status: Planned

Unit tests must cover cycle calculation across month boundaries, leap years, start days 1 and 20, reserves, protected and conservation states, projected unused credit, scoring, weighted selection, cooldowns, failover, retry timing, safe response headers, same-backend health-state concurrency, streaming no-retry behavior, pre-output stream bounds, stream cleanup on failure and cancellation, inflight reservations, unknown models, malformed configuration, and negative estimates.

Integration tests use mocked backends for success, A-to-B failover, 429, 500, unavailability, both unavailable, streaming, and embeddings. Security tests cover authentication, redaction, and configured-backend restrictions.

Performance tests should verify low routing overhead, prompt streaming start, no full-response buffering, and approximately constant proxy memory with response size. Optional real-Azure end-to-end tests must be isolated from pull requests.
