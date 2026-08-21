# Operations and Deployment

## Status: Design Target

Use IaC for a resource group, Container Apps environment and app, registry, managed identity where needed, RBAC, secrets/configuration, and optional Log Analytics/Application Insights and custom domain. Deploy into either subscription through parameters; never hard-code subscription IDs.

## Initial Container App

Target Consumption settings are 0.25 vCPU, 0.5 GiB memory, minimum replicas 0, and maximum replicas 2. Scale-to-zero startup latency is expected. Do not add always-on infrastructure, API Management, Front Door, Kubernetes, Redis, SQL, or other services without a concrete requirement.

## Reconciliation

Reconcile authoritative Azure usage/cost data every 5–15 minutes, not on every request. Expose `last_cost_reconciliation` and `cost_data_age`. If unavailable, continue with labeled local estimates, mark the state stale, and optionally route more conservatively. Never treat stale estimates as authoritative.

## Failure Handling

Fail over an unavailable backend, cooldown 429 and repeated 5xx failures, return a clear error when all backends are unavailable or protected, clamp negative usable credit to zero, reject unknown models and malformed requests without outbound calls, and never intentionally cross a safety reserve. Operational priority is safety, availability, quota efficiency, minimizing cycle-end waste, then balancing.
