# Phase 06 Exit Criteria

## Criteria Checklist

- [x] State store Protocol interfaces (`CreditStore`, `HealthStore`) cleanly separate domain logic from storage implementation. *(Both protocols defined and implemented; Azure Table adapters for both credit and health complete.)*
- [x] Azure Table Storage adapter uses a same-backend-partition transactional batch to atomically update a balance and its reservation; concurrent reservation, release, ETag-conflict, and interruption-recovery tests prove shared credit is not oversubscribed. Unavailable authoritative storage fails closed. *(Implemented in AzureTableCreditStore with 40+ unit tests covering all scenarios.)*
- [x] Health and cooldown snapshots use the ADR-005 timestamped, eventually consistent semantics and are covered by tests. *(Implemented in AzureTableHealthStore with 19 unit tests covering snapshots, cooldowns, cache invalidation, and edge cases.)*
- [x] `/admin/status` exposes real-time health, cooldown, and credit diagnostics with admin authentication and zero secrets.
- [x] `/metrics` endpoint provides Prometheus-compatible telemetry with admin authentication and zero PII/secret exposure. *(Single-process in-process metrics. Multi-worker aggregation planned for Phase 07.)*
- [ ] Multi-worker metric collection verified with consistent monotonic counter exposition across worker processes. *(Planned for Phase 07; requires prometheus_client multiprocess mode or OpenTelemetry exporter integration.)*
- [x] Test coverage across new state adapters and metric endpoints >= 85%. *(Achieved: 90.94% overall, 89.17% state module.)*
