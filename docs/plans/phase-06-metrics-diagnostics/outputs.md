# Phase 06 Outputs

## Deliverables

| Output | Destination | Description |
|---|---|---|
| State Protocols | `src/foundry_router/credit.py`, `src/foundry_router/health/`, `src/foundry_router/state/` | `CreditStore` boundary and in-memory implementation (**Partially implemented**); `InMemoryHealthStore` and `HealthStore` (**Implemented**) |
| Azure Table Storage Adapter | `src/foundry_router/state/table.py` | Injected-client health adapter boundary using partitioned, timestamped entities (**Partially implemented**); Azure SDK integration and transactional credit adapter remain **Planned** |
| Optional Redis Hot-State Adapter | Future separately approved scope | Cache-only optimization after a demonstrated latency need; it must not replace the Azure Table Storage source of truth (**Planned**) |
| Enriched Admin Status | `src/foundry_router/main.py` | Live health and credit introspection in `/admin/status` with admin authentication (**Implemented**) |
| Metrics Exporter & Multi-Worker Support | `src/foundry_router/metrics/__init__.py`, `src/foundry_router/main.py` | Authenticated Prometheus `/metrics` endpoint, stream lifecycle hooks, and multi-process scraping support (**Partially implemented**) |
