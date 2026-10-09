# Azure Cost Management reconciliation

**Implemented** locally, independently reviewed 2026-10-08; see [review](plan-review.md).
Independent workstream 4e of the
[routing roadmap](../google-ai-routing-order/index.md). Production remains memory/one;
this code phase neither grants Azure permissions nor authorizes deployment.

## Billing data and credit contract

Azure Cost Management Query returns reported costs, not remaining promotional credit. Azure
[documents delayed availability and estimated open-period charges](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data);
fetching a response does not establish reporting completeness.
Implement an opt-in `azure_cost_management` reconciliation provider alongside the default
static overrides. Query cycle-to-date ActualCost using the official
[2025-03-01 contract](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01).
Subscription or resource-group scopes and explicit Cognitive Services resource IDs are
operator configuration; never infer billing scope from an inference endpoint. Each mapped
canonical metered credit group must have explicit cycle allowance/start-day configuration.
Reject overlapping resource membership, unknown/nonmetered groups and simultaneous static
overrides. Restrict this phase to public Azure and USD; currency conversion, other billing
scopes and promotional balance discovery need their own contracts.

For each group, request Custom UTC cycle-start through query-time, Sum PreTaxCost, and
ResourceId filtering/grouping: `aggregation.totalCost = {name: PreTaxCost, function: Sum}`,
`filter.dimensions = {name: ResourceId, operator: In, values: configured IDs}` and
`grouping = [{type: Dimension, name: ResourceId}]`. The aggregate alias is not a guaranteed
response column name; require named PreTaxCost (Number), Currency (String) and ResourceId
(String) columns. Validate returned column names/types and exact resource
membership case-insensitively, finite nonnegative decimal amounts and USD. Reject unexpected
resources, duplicate columns, malformed rows, absent required columns, mixed currency or
partial pagination. Empty/204 responses mean unavailable cost evidence; do not manufacture
a zero-cost balance. Include ResourceId grouping so scope/filter mistakes are observable.
Bounds: at most 64 configured groups, 32 resources per group, 10 pages/group, 10,000 rows
per group, 1 MiB/page, and a 30-second deadline for the complete refresh including token
acquisition and all groups/pages. Fail the complete fetch before any balance updates when
any query is invalid, incomplete or unavailable. A storage failure during application can
still leave earlier groups updated; report failure without claiming cross-group atomicity.

Introduce a typed cost ceiling batch, separate from existing replacement overrides.
Compute `max(0, configured cycle allowance - reported cycle cost)` and bind every ceiling
to the queried UTC cycle start, explicit cycle-start day, allowance and immutable fingerprint
of canonical group, scope and sorted resource membership. Recheck this fingerprint against
current settings during application and validate numeric cycle policy against persisted state. Memory updates hold the store lock; Table
updates use a fresh balance read and ETag transaction on every retry. Reject/skip ceilings
whose cycle/start-day/allowance no longer matches persisted policy or whose mapping
fingerprint no longer matches current settings. Atomically set remaining to
`min(current remaining, ceiling)`; preserve inflight reservations and concurrent debits.
Never implement this as a read-snapshot followed by a replacement balance. Recheck the current cycle with fresh application
time on every CAS retry, and convert decimal ceilings conservatively without overflow or
upward rounding. Repeated or lower reported costs cannot replenish credit; ordinary configured cycle rollover remains
separate. Query-time is a fetch timestamp, not a billing-completeness watermark. Local and
reported spend may overlap, and delayed/external charges may be missing: this is a labeled
conservative ceiling estimate, not proof of available Azure funds or exact settlement.

Keep existing static provider/test injection behavior. The loop accepts either existing
replacement dictionaries or the typed cost batch and dispatches to the appropriate store
operation. Ownership maintenance and reservation reaping must run independently of a failed
provider fetch; a billing outage must not disable cleanup. Expose provider kind, last fetch
and failure/stale state in existing authenticated diagnostics, without resource IDs, URLs,
bearer tokens, returned billing bodies or fabricated reporting freshness. Keep inference
free of billing I/O. A failed refresh preserves local estimates and records sanitized error
categories; no fallback to configured allowance as a fresh balance.

## Confined transport and lifecycle

Use existing async Azure identity selection: managed identity in Container Apps, developer
identity chain locally. Acquire the public ARM token scope; own and close credential/client
with the provider lifespan even after startup failure or cancellation. Resource-group names support bounded documented Unicode letters/numbers and `_-.()`,
without trailing dots; validated Unicode path segments are encoded before dispatch.
JSON container depth is checked before decoding and bounded to 16.
No API keys, SAS,
connection strings, new infrastructure or hard-coded resource identifiers.

Build POST URLs from validated subscription/resource-group scopes on fixed
`https://management.azure.com`; no configured arbitrary host. Validate raw IDs before URL
normalization: reject query/fragment/userinfo, encoded/dot/slash ambiguities, controls and
out-of-scope resource paths. Use verified TLS, `trust_env=False`, no redirects, bounded
response streaming and a single-shot HTTP request. 401/403/429/5xx, malformed JSON and
deadline failure preserve estimates until the next scheduled refresh; never log raw errors.
Validate every nextLink against the same ARM host, exact scope/query operation path and
supported API version with only bounded `$skiptoken` pagination input. Official examples
include older-version links: fail explicitly rather than silently changing API contract.
Detect repeated nextLinks. Reuse identical query body for subsequent POST pages. Bound
token lifetime/cache through Azure identity; no token in diagnostics or logger context.

## Verification and rollout gates

Obtain independent plan review before runtime edits. Test exact POST payload/auth, pagination,
column reordering, currency/resource validation, empty results, hostile nextLinks/ambient
proxy settings, slow responses, deadline/cancellation and ownership cleanup. Verify memory
and fake-Table concurrent settlement, ETag conflict retries, inflight preservation, repeated
cost data, cycle/start-day/mapping changes during a fetch, and reconciliation failure with reservation reaping.
Run real local Azurite ceiling concurrency/restart checks and the full coverage/quality/Docker
suite; follow the repository's contextual implementation review and link/secret checks.

Live acceptance needs actual operator-supplied scope/resource mapping, confirmed Cost
Management read permissions and bounded read-only query evidence. Compare reported resource
costs/currency/cycle window and local ceilings without representing them as authoritative
balances. This remains unverified until recorded separately. Production cut-over still needs
its own reconciled starting estimates and go decision.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
