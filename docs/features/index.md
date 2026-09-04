# Runtime Features

## Status: Partially implemented

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
- Persistent or externally reconciled usage/cost state. **Planned**
- `CreditStore`, `HealthStore`, and the injected-client Azure Table health boundary for multi-replica support. **Partially implemented**; authoritative Azure Table credit transactions and SDK integration are **Planned**.
- Liveness/readiness, structured logs, and useful metrics. **Partially implemented**
- Secure credentials, IaC, automated deployment, local mocked-backend development, and tests. **Partially implemented**

## Optional and Future Capabilities

Managed identity, Azure Cost Management reconciliation, model aliases, graceful stale-cost degradation, custom domains, Application Insights dashboards, per-model policies, dynamic weights, simulation mode, and additional regions are optional or future scope. They must not make the initial proxy unnecessarily large.

See [routing and scheduling](routing.md) for the safety-critical policy.
