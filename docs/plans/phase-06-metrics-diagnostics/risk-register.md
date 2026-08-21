# Phase 06 Risk Register

## Risk Assessment

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R-P06-01 | Network partition to Redis store stalls proxy requests | High | Low | Bounded Redis operation timeouts (50ms) with fail-closed or local fallback semantics. |
| R-P06-02 | Prometheus metric cardinality explosion with unbounded labels | Medium | Low | Strictly bounded label dimensions (only static model and backend IDs; no user IDs or request IDs). |
| R-P06-03 | Multi-worker scrape jitter produces non-monotonic counter samples across Uvicorn workers | Medium | Medium | Use `prometheus_client` multiprocess directory collector or OpenTelemetry metrics exporter for unified process metrics. |
| R-P06-04 | Client-side stream cancellation masking upstream failures | Low | Medium | Explicitly distinguish `asyncio.CancelledError` / client disconnect from upstream `httpx.HTTPError` in stream generator teardown. |

