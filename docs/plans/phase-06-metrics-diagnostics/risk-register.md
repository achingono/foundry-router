# Phase 06 Risk Register

## Risk Assessment

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R-P06-01 | Network partition or Azure Table Storage conflict delays authoritative credit operations | High | Medium | Use bounded storage operation timeouts and ETag retry limits; fail closed for credit reservation and release decisions rather than falling back to replica-local state. |
| R-P06-05 | Eventual consistency of health/cooldown snapshots causes a brief routing anomaly | Medium | Medium | Use timestamped last-write-wins health snapshots, retain bounded cooldowns, and rely on upstream 429/5xx responses to re-establish cooldowns. |
| R-P06-06 | Process interruption leaves an unfinished reservation and incorrectly locks or charges credit | High | Medium | Persist idempotent reservation state and expiry in the same backend partition as the balance; transactionally settle or release it through bounded recovery. |
| R-P06-02 | Prometheus metric cardinality explosion with unbounded labels | Medium | Low | Strictly bounded label dimensions (only static model and backend IDs; no user IDs or request IDs). |
| R-P06-03 | Multi-worker scrape jitter produces non-monotonic counter samples across Uvicorn workers | Medium | Medium | Use `prometheus_client` multiprocess directory collector or OpenTelemetry metrics exporter for unified process metrics. |
| R-P06-04 | Client-side stream cancellation masking upstream failures | Low | Medium | Explicitly distinguish `asyncio.CancelledError` / client disconnect from upstream `httpx.HTTPError` in stream generator teardown. |
