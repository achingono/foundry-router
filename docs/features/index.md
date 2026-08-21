# Runtime Features

## Status: Partially implemented

The router is more than a load balancer. It is a model router, quota-aware failover layer, credit scheduler, and billing-cycle-aware capacity pool.

## Required Capabilities

- OpenAI Responses API with transparent streaming. **Implemented**
- Embeddings and logical model discovery. **Implemented**
- Two or more configurable Foundry backends, extensible without code changes. **Partially implemented**
- Per-model pools, weighted routing, health tracking, bounded retry, and failover.
- 429 and transient 5xx cooldown behavior.
- Credit-aware routing with safety reserves and cycle awareness.
- Persistent or externally reconciled usage/cost state.
- Liveness/readiness, structured logs, and useful metrics.
- Secure credentials, IaC, automated deployment, local mocked-backend development, and tests.

## Optional and Future Capabilities

Managed identity, Azure Cost Management reconciliation, authenticated administrative status, model aliases, graceful stale-cost degradation, custom domains, Application Insights, Prometheus metrics, dashboards, per-model policies, dynamic weights, simulation mode, and additional regions are optional or future scope. They must not make the initial proxy unnecessarily large.

See [routing and scheduling](routing.md) for the safety-critical policy.
