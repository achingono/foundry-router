# ADR-005: State Management Strategy for Multi-Replica Deployment

## Status
Accepted

## Context
Azure Container Apps Consumption plan allows scaling from 0 to N replicas (initially max 2). The router maintains several types of state that must remain correct across replicas:

1. **Ephemeral/Request-scoped**: Inflight reservations, per-request routing decisions (no persistence needed)
2. **Replica-local caches**: Backend health, cooldown timers, recent error rates (can tolerate brief inconsistency)
3. **Authoritative shared state**: Credit balances, reservations, cost reconciliation data (must be consistent)

## Decision

### Phase 1 (Single Replica Only)
- All state in memory within the single process
- `max_replicas: 1` in Container App configuration
- Simple, correct, no distributed coordination needed
- Document that scaling beyond 1 is not supported

### Phase 2 (Multi-Replica: External Shared State)
Before enabling `max_replicas > 1`, implement authoritative shared state using **Azure Table Storage**:

| State Type | Storage | Consistency Model |
| --- | --- | --- |
| Credit balances / cycle calculations | Azure Table (partition: backend_id; balance row) | Strong (conditional writes with ETags) |
| Inflight reservations | Azure Table (partition: backend_id; request ID row key) | Strong (same-partition transactional batch with the balance row) |
| Backend health / cooldowns | Azure Table (partition: backend_id) | Eventual (last-write-wins with timestamp) |
| Cost reconciliation results | Azure Table (partition: backend_id) | Eventual (periodic writes) |

**Implementation approach**:
- Repository pattern with `StateStore` interface (in-memory for tests, Azure Table for prod)
- Store a backend's balance and every reservation in the same `backend_id` partition. Use ETag-guarded transactional batches to atomically update the balance and create, settle, or release the reservation.
- Make reservation state idempotent and recover expired unfinished reservations through bounded reconciliation; do not use a replica-local fallback for authoritative credit operations.
- Local in-memory cache with TTL (e.g., 30s) to reduce storage calls
- Background reconciliation job writes authoritative Azure Cost Management data

### Phase 3 (Optional: Redis for Hot State)
If latency becomes an issue, add **Azure Cache for Redis** for:
- Read-through caching of health/cooldown snapshots and reservation metadata
- Cached credit-balance reads with Azure Table Storage as the source of truth

Redis must not own reservation creation, release, settlement, or the authoritative credit balance. Those writes remain Azure Table Storage same-partition transactions.

## Consequences

### Positive
- Phase 1 delivers value immediately without distributed systems complexity
- Clear migration path with explicit phases
- Azure Table Storage is cheap, serverless, and strongly consistent
- Same-partition transaction layout prevents shared-credit oversubscription without cross-partition coordination
- Repository pattern keeps business logic storage-agnostic

### Negative
- Phase 1 limits throughput to single replica capacity
- Additional Azure resource (Storage Account) for Phase 2
- Eventual consistency for health/cooldowns may cause brief routing anomalies

### Neutral
- Decision documented early to avoid architectural drift
- Can be revisited if requirements change

## Alternatives Considered
- **In-memory only, accept inconsistency**: Violates safety requirements (credit reserves)
- **Consul/etcd**: Additional operational burden, not cloud-native
- **SQL Database**: Overkill, higher cost, connection pooling complexity
- **CRDTs**: Too complex for this use case
- **Leader election**: Single point of failure, doesn't solve shared state

## Related
- ADR-001: Python/FastAPI (async supports concurrent requests within replica)
- ADR-002: Configuration (backend definitions drive state keys)

## References
- Azure Table Storage: https://learn.microsoft.com/azure/storage/tables/
- Azure Container Apps scaling: https://learn.microsoft.com/azure/container-apps/scale-app
