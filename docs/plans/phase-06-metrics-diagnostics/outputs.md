# Phase 06 Outputs

## Deliverables

| Output | Destination | Description |
|---|---|---|
| State Protocols | `src/foundry_router/credit.py`, `src/foundry_router/health/`, `src/foundry_router/state/` | `CreditStore` and `HealthStore` protocols with in-memory and Azure Table Storage adapter implementations (**Implemented**) |
| Azure Table Storage Adapter | `src/foundry_router/state/table.py` | `AzureTableCreditStore` (352 LOC) with same-partition transactional batch for atomic reservation lifecycle; `AzureTableHealthStore` with timestamped, eventually consistent health/cooldown snapshots; both use ETag-guarded conditional writes (**Implemented**) |
| Optional Redis Hot-State Adapter | Future separately approved scope | Cache-only optimization after a demonstrated latency need; it must not replace the Azure Table Storage source of truth (**Planned**) |
| Enriched Admin Status | `src/foundry_router/main.py` | Live health and credit introspection in `/admin/status` with admin authentication; exposes backend state, cooldown remaining, credit availability, active reservations, cycle boundaries (**Implemented**) |
| Metrics Exporter & Multi-Worker Support | `src/foundry_router/metrics/__init__.py`, `src/foundry_router/main.py` | Authenticated Prometheus `/metrics` endpoint with counters, histograms, gauges for request rate, latency, estimated cost, and backend health; single-process in-memory collection (**Implemented**); multi-process metric aggregation via prometheus_client or OpenTelemetry (**Planned for Phase 07**) |
