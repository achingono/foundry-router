# Runtime Features

## Status: Implemented locally; deployed quota/metrics aggregation and production Table cut-over remain unverified

The router is more than a load balancer. It is a model router, quota-aware failover layer, credit scheduler, and billing-cycle-aware capacity pool.

## Required Capabilities

- OpenAI Responses API with transparent streaming. **Implemented**
- Embeddings and logical model discovery. **Implemented**
- Two or more configurable Foundry backends, extensible without code changes. **Implemented**
- Per-model pools, weighted routing, health tracking, bounded retry, and failover. **Implemented**
- 429 and transient 5xx cooldown behavior. **Implemented**
- Credit-aware routing with safety reserves and cycle awareness. **Implemented**
- Streaming terminal usage extraction for accurate reservation settlement. **Implemented**
- Structured explainable routing decision logging. **Implemented**
- Persistent or externally reconciled usage/cost state via periodic reconciliation loop (`reconciliation_interval_minutes` + `InMemoryCreditStore.apply_reconciled_remaining` / `AzureTableCreditStore.apply_reconciled_remaining`). **Implemented**
- `CreditStore`, `HealthStore`, identity-only Azure Table adapters and conditional state wiring are **Implemented**. [Synthetic one/two-replica and cross-RG Azure verification](../plans/table-existing-cross-rg/evidence.md) passed; Table-backed real inference and production cut-over remain unverified.
- Liveness/readiness, structured logs and single-process Prometheus metrics are **Implemented**. Opt-in [OTLP aggregation](../plans/metrics-aggregation/evidence.md) passed local two-worker/restart verification; deployed collector acceptance remains unverified.
- Secure credentials, IaC (Bicep), automated deployment, local mocked-backend development, and tests. **Implemented**

## Optional and Future Capabilities

Managed identity and model aliases are **Implemented**. The [Azure Cost Management adapter](../plans/azure-cost-reconciliation/evidence.md) is **Implemented** locally; live billing acceptance remains unverified. Custom domains, Application Insights dashboards, dynamic weights, simulation mode and additional regions remain optional or future scope.

See [routing and scheduling](routing.md) for the safety-critical policy.
