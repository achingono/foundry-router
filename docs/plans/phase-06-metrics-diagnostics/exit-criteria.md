# Phase 06 Exit Criteria

## Criteria Checklist

- [x] State store Protocol interfaces (`CreditStore`, `HealthStore`) cleanly separate domain logic from storage implementation. *(Azure Table health adapter boundary added; credit transaction adapter remains pending.)*
- [ ] Azure Table Storage adapter uses a same-backend-partition transactional batch to atomically update a balance and its reservation; concurrent reservation, release, ETag-conflict, and interruption-recovery tests prove shared credit is not oversubscribed. Unavailable authoritative storage fails closed.
- [ ] Health and cooldown snapshots use the ADR-005 timestamped, eventually consistent semantics and are covered by tests.
- [x] `/admin/status` exposes real-time health, cooldown, and credit diagnostics with admin authentication and zero secrets.
- [x] `/metrics` endpoint provides Prometheus-compatible telemetry with admin authentication and zero PII/secret exposure.
- [ ] Multi-worker metric collection verified with consistent monotonic counter exposition across worker processes.
- [ ] Test coverage across new state adapters and metric endpoints >= 85%.
