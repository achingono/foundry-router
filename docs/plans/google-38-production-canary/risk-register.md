# Risk register

| Risk | Mitigation |
| --- | --- |
| Provider intermittent503/high demand | Two verified projects, at most two distinct physical attempts, explicit cooldown, fail closed after public SSE starts |
| API keys exposed in earlier conversation | Operator informed to rotate; renewed authorization permits proceeding. Never output credentials or arbitrary fields from secret-bearing objects |
| Quota reset on memory restart | Durable Table quota with historical deterministic seed, fixed groups, Pacific reset, no scale-out |
| UI TPM dimension unknown | Google public rate-limits page explicitly defines TPM as input; record dated source |
| Live stream lifecycle not proved by buffered diagnostics | Real TCP early delivery and natural cancellation acceptance before rollout |
| Azure estimate replenishment on restart | Separate unmetered Google-only canary avoids changing Azure memory credit or requiring handover |
| No deployed collector | Single-process metrics suffice for canary; do not clear multi-replica aggregation gate |
