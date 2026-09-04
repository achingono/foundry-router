# Phase 03 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Cooldown state lost on replica restart (stateless design) | May route to a backend that was just cooled | Keep cooldown durations short; rely on upstream to re-emit 429/5xx; add Azure Table Storage health snapshots in Phase 06 | Open |
| R2 | Retry-After header parsing (seconds vs HTTP-date) | Incorrect delay if header format varies | Implement robust parser supporting both integer seconds and HTTP-date formats with clamping between 0 and `retry_max_delay_seconds` | Open |
| R3 | Failover livelock or race conditions under concurrent requests | Inconsistent health state across tasks | Protect all health and cooldown state reads/writes with an `asyncio.Lock` | Open |
| R4 | Exhausted cooldown behavior when all backends cooled | Unclear client response status or missing retry guidance | Return `503` (or `429` for quota) with `Retry-After` set to the minimum remaining cooldown time among candidates | Open |
| R5 | Streaming first-chunk detection varies by backend | Premature "output started" decision | Define "meaningful output" as any non-empty byte chunk; unit test with empty-body 200 | Open |
| R6 | Correlation ID propagation on failover | Traceability broken if ID not re-sent | Use same `x-request-id` for all attempts; log attempt number with ID | Open |

## Open Decisions
- Cooldown duration: reuse `retry_max_delay_seconds` or add dedicated `cooldown_duration_seconds`?
- Should cooldown be per-model or per-backend? (Current: per-backend, simpler and safer)
- Emergency fallback: return 503 with `Retry-After` or 429? (Prefer 503 with `Retry-After` for quota, 503 for errors)
- Maximum total request latency budget (affects retry + failover budget): document in operations guide.
