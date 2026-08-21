# Glossary

This document defines key terms used throughout the Foundry Router documentation.

## Core Concepts

### Backend
An Azure AI Foundry deployment endpoint with associated credentials. Each backend represents a distinct subscription/project/region combination. Backends are identified by a unique ID (e.g., `sub_a`, `sub_b`) and have independent credit cycles, quota, and health state.

### Logical Model
A user-facing model name (e.g., `gpt-5.4`, `text-embedding-3-large`) that maps to one or more backends. Clients use logical model names; the router selects the appropriate backend deployment.

### Backend Pool
The set of backends configured for a specific logical model, each with an associated weight. Weights influence routing probability during normal operation.

### Credit Cycle
The billing period for a backend's associated Azure subscription. Each backend has an independent cycle start day (1-28). Credit is allocated at the start of each cycle and consumed by model inference.

### Safety Reserve
The minimum credit threshold that must be preserved for each backend. The router will not intentionally route requests to a backend if doing so would cross its safety reserve. Calculated as the greater of:
- `min_credit_reserve_usd` (absolute dollar amount)
- `min_credit_reserve_percent` (percentage of total cycle credit)

### Spendable Credit
`remaining_credit - safety_reserve`. The amount of credit available for routing decisions.

### Projected Unused Credit
`remaining_credit - estimated_daily_burn * days_remaining`. Estimated credit that would go unused at cycle end if current burn rate continues. Used to increase routing urgency for backends with high projected waste.

### Inflight Reservation
A conservative cost estimate reserved before dispatching a request. Formula: `available_credit = estimated_remaining_credit - reserved_inflight_cost - safety_reserve`. Released after request completion with actual cost recorded.

## Backend States

### ACTIVE
Normal routing state. Backend receives traffic according to its weight and score.

### CONSERVATION
Reduced traffic state. Activated when projected cycle-end utilization is low or reserve pressure is rising. Backend still receives some traffic but at reduced priority.

### PROTECTED
No intentional traffic. Backend is at or near its safety reserve. Only used if `protected_emergency_fallback` is enabled and all other backends are unavailable.

### QUOTA_COOLDOWN
Temporary state after receiving HTTP 429 (rate limit) from the backend. Backend is excluded from routing for a cooldown period.

### ERROR_COOLDOWN
Temporary state after repeated transient errors (5xx). Backend is excluded from routing for a cooldown period.

### DISABLED
Operator-controlled state. Backend is explicitly disabled via configuration.

## Routing & Scoring

### Weighted Round-Robin
Selection mechanism used when candidates have equal scores. Backends are chosen proportionally to their configured weights.

### Routing Score
A composite score combining:
- Availability (backend state)
- Quota health (recent 429s, TPM utilization)
- Credit health (spendable credit vs estimated request cost)
- Cycle urgency (projected unused credit, days remaining)
- Error health (recent 5xx rate)

### Failover
Automatic retry to an alternative backend when the selected backend returns a transient error (429, 500, 502, 503, 504). Limited to one immediate failover by default. Never occurs after streaming has meaningfully started.

## Cost & Reconciliation

### Local Cost Estimate
Token-count-based cost calculation using configured per-model pricing. Always labeled as an estimate, never presented as authoritative.

### Authoritative Azure Cost
Actual billing data from Azure Cost Management API. Reconciled periodically (every 5-15 minutes). Used to correct local estimates.

### Reconciliation Interval
How often the router fetches authoritative cost data from Azure. Configurable (default 10 minutes).

### Stale Cost Data
Local estimates that haven't been reconciled recently. Marked with `cost_data_age` and `last_cost_reconciliation`. Router may route more conservatively when data is stale.

## Security & Operations

### Allow-List
The set of backend hostnames extracted from configuration. The outbound HTTP client rejects any request to a hostname not in this list, preventing SSRF.

### Correlation ID / Request ID
A unique identifier (UUID) generated per request, propagated through logs, response headers (`x-request-id`), and backend calls for traceability.

### Redaction
Automatic removal of sensitive data (API keys, Authorization headers, prompts, completions) from log output. Applied by the structured logging processor.

### Client Authentication
Authentication required for all `/openai/v1/*` endpoints. Uses API key header (`api-key`) or Bearer token.

### Admin Authentication
Separate authentication required for `/admin/status`. Uses `x-admin-key` header or Bearer token with separate key set.

## Deployment

### Scale-to-Zero
Azure Container Apps Consumption feature allowing zero replicas when idle. Router must start quickly and maintain correctness with multiple replicas.

### Consumption Plan
Azure Container Apps pricing tier with per-request billing, 0.25 vCPU / 0.5 GiB minimum, scale-to-zero enabled.

### IaC (Infrastructure as Code)
Declarative definition of Azure resources (Container Apps, managed identity, secrets, RBAC). Must not contain hard-coded subscription IDs.