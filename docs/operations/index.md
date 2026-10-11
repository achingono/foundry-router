# Operations and Deployment

## Status: Implemented (IaC and synthetic Table verification); production cut-over Partially implemented

IaC is **Implemented** in `infra/main.bicep` and typed resource modules; CI/CD is defined in `.github/workflows/ci.yml` and `deploy.yml`. Azure template validation, one/two-replica synthetic Table and existing-account cross-RG runtime verification passed. Production cut-over remains **Partially implemented** pending reconciled starting balances and real traffic gates. Production remains `stateBackend: memory` with `maxReplicas: 1`.

## Initial Container App

To verify a client base URL and API key, run `scripts/operations/test-client-connection.sh
https://<container-app-fqdn>/openai/v1`. Set `FOUNDRY_ROUTER_API_KEY` or enter the key at the
hidden prompt; the script checks the authenticated models endpoint.

Production configuration is **Implemented** for two resources, six model pools and two shared credit accounts. Twelve real production Responses tests passed (nonstream/stream for every model), including terminal usage and exact local estimated debit reconciliation. Counters show all requests selected fs-swarm; a follow-up bounded run verified admission rejections, single-pool nonstream/stream settlement and observable failure-state with both test dispatches served by the pool's fs-openclaw backend. Live upstream 429/5xx failover and remaining-pool fs-openclaw coverage remain unverified. Production uses memory/one; Table cut-over remains pending. See [configuration](../plans/production-foundry/evidence.md), [inference evidence](../plans/production-inference/evidence.md) and [failure/admission evidence](../plans/production-failure-admission/evidence.md). Starting estimates are not Azure balances and reset on memory-process restart.

Real non-streaming and streaming Responses verification is **Implemented** for both selected test models through the dedicated memory/one app. Azure v1 routing and nested terminal usage reconciliation were corrected after initial upstream 404s. Both streams completed and local test-price debits matched usage with zero inflight reservations. See [inference evidence](../plans/foundry-inference/evidence.md). This does not establish embeddings, real traffic failover, Table-backed real inference or authoritative Azure cost reconciliation.

A dedicated real-resource test backend is **Implemented** and configuration-ready for both operator-selected deployments. Secrets use a separate vault prefix with generated client/admin keys; local per-backend pricing/credit inputs are explicitly test-only estimates. Health/model discovery checks do not prove provider reachability or inference compatibility. See [test backend evidence](../plans/foundry-test-backend/evidence.md).

Existing-account cross-RG synthetic Table runtime is **Implemented** and verified: table-scoped managed identity, idempotent redeployment, checked parent-setting preservation and restart persistence passed. See [cross-RG evidence](../plans/table-existing-cross-rg/evidence.md). Real inference/provider traffic and production cut-over remain unverified; production stays memory/one.

Two-replica synthetic Table verification is **Implemented** in the isolated test app: replica-targeted managed-identity reservation checks, shared app diagnostics and individual container restart persistence passed. Production remains memory-backed with one replica until cut-over requirements are fulfilled. This evidence does not cover real inference, provider quota admission traffic or metrics aggregation. See [two-replica evidence](../plans/table-two-replica/evidence.md).

Target Consumption settings are 0.25 vCPU, 0.5 GiB memory, and minimum replicas 0. `stateBackend` defaults to `memory`; `table` mode uses the configured HTTPS endpoint and table names with a user-assigned managed identity. Table-mode readiness requires every unique routable metered credit-group balance row and health-table reachability. Startup sync retries failed initialization when routing calls sync again; storage failures fail closed. Scale-to-zero startup latency is expected. Connection-pool/keep-alive/HTTP/2 tuning and graceful shutdown draining are implemented. Do not add always-on infrastructure, API Management, Front Door, Kubernetes, Redis, SQL, or other services without a concrete requirement.

Shared-resource credit and production configuration are **Implemented** with twelve backends, six pools and two accounts. Production pool inference through fs-swarm passed; fs-openclaw and Table-backed production inference remain unverified.
See [shared-credit operations and migration](shared-resource-credit.md). Production remains memory/one.

Production cut-over requires reconciled starting balances, deployment in table mode with one replica, a green readiness check, and draining all memory-backed revisions before raising the replica count. In-memory state is not migrated. Rollback is to `memory` with one replica; retain Table data.

Logical model aliases roll out through validated configuration and the normal
drain/restart procedure; in-flight requests settle against their captured canonical
target. Remove or retarget aliases in a fresh validated configuration to roll back.
Alias configuration is preserved through the optional Bicep `modelAliases` wiring
rather than ad hoc edits.

The production model-alias rollout is **Implemented** with both aliases targeting
`gpt-6.1-sol`, six live normal/streaming cases, and actual Codex reviewer
allow/deny/injected-error validation. It retained memory/one and left ingress
restrictions untouched as directed by the operator. Fresh estimated balances less
existing reservations were pinned for startup; later old-process admissions and
revision overlap were not migrated, so exact credit continuity is unverified.
Preserve observed ingress restrictions explicitly in Bicep; the optional
`ingressIpSecurityRestrictions` default `[]` removes any existing restrictions.
Rollback requires fresh estimates and a pinned secret version, without reactivating
stale memory state. See [production alias evidence](../plans/model-aliases-production/evidence.md).

Memory-mode Azure validation and a single-replica synthetic baseline deployment are **Implemented** and verified in the [validation evidence](../plans/memory-mode-validation/evidence.md). The synthetic baseline covers health, authentication, model discovery, admin and metrics, not inference. New-workspace logging bootstrap requires `configureConsoleLogsPlan=false` until ingestion creates the console table, followed by `true`. The current Classic console table uses Analytics with 30-day retention; Basic/DCR migration remains **Planned**. See the [infrastructure deployment guide](../../infra/README.md) for tenant checks and partial-deployment recovery.

## Reconciliation

One-replica synthetic Table runtime verification is **Implemented**: token-only managed-identity readiness, independent adapter accounting and restart persistence passed. Two-replica synthetic checks also passed. Production stays memory/one; Table-backed real inference and remaining cut-over gates are pending. See [Table runtime evidence](../plans/table-runtime-validation/evidence.md).

The Bicep typing foundation, identity/observability and environment/router modules are **Implemented**; the public flat parameter interface remains compatible. Use Bicep 0.47.16 or newer (minimum verified version). Direct internal module callers supply sealed config objects and preserve access-grant dependencies. See [typing evidence](../plans/bicep-typing/evidence.md), [module extraction evidence](../plans/bicep-module-extraction/evidence.md), [container module evidence](../plans/bicep-container-modules/evidence.md) and the infrastructure guide.

The opt-in Azure Cost Management provider queries reported subscription-currency costs in the background at
the configured reconciliation interval (default ten minutes). Atomic cycle-bound ceilings
can lower local remaining estimates without replenishing concurrent spend. Authenticated
reconciliation diagnostics expose provider kind, last attempt/success and failure/stale state;
fetch time does not establish billing completeness. Unavailable/incomplete evidence preserves
local estimates while reservation maintenance continues. Live Azure query acceptance remains
unverified; see the [contract](../plans/azure-cost-reconciliation/index.md).
Configure each subscription's billing currency as USD or CAD. CAD uses one published Bank
of Canada daily average for the complete refresh; safe acceptance evidence retains its date,
CAD-per-USD rate and source. Missing, malformed or older-than-four-day rate evidence rejects
the refresh while local estimates and reservation maintenance continue. Daily conversion of
cycle-to-date totals remains an estimate; it does not reconstruct transaction-day FX.
See [currency configuration and verification](../plans/azure-cost-currency/index.md).

## Failure Handling

Generic compatible upstreams are **Implemented with mocked verification** through
`provider: openai_compatible`. Validate the exact API root, physical model, operation support,
fixed Chat wire dialect and separate quota/credit inputs before rollout. Their live
compatibility remains unverified; production currently has no generic-provider enablement.
OpenRouter upstreams (`provider: openrouter`) reuse the same translated dialect and
rollout gates against their exact API root. Zen Responses upstreams
(`provider: opencode_zen`) use pass-through against their exact API root with the
bounded stateless-text request gate and operator-selected Responses models. Use the
normal validated configuration/drain/restart procedure and bounded exact-model
inference/usage checks. Do not infer Google quota/reset semantics for another provider.

All new infrastructure resource families now have typed module owners; the root preserves existing-resource lookups and the flat deployment interface. Registry/vault combinations are template-validated, with the synthetic existing/existing memory path redeployed and smoke-tested. New-resource runtime convergence, real inference and Table runtime remain separate verification gates; see [registry/vault evidence](../plans/bicep-registry-vault/evidence.md).

The opt-in `infra/typed.bicep` interface is **Implemented** and synthetic memory redeployment verified. CI retains `main.bicep`. Typed registry/vault/state choices reject inactive branch fields; password remains separate and secure. Both entry points retain the same bootstrap and cut-over requirements; see [public interface evidence](../plans/bicep-public-interface/evidence.md).

Fail over an unavailable backend, cooldown 429 and repeated 5xx failures, return a clear error when all backends are unavailable or protected, clamp negative usable credit to zero, reject unknown models and malformed requests without outbound calls, and never intentionally cross a safety reserve. Operational priority is safety, availability, quota efficiency, minimizing cycle-end waste, then balancing.

- [Google tool, structured text and small PNG feature operations](google-features.md) (Implemented with synthetic/client verification; live gate Planned)
- [Google model task guidance](google-model-task-guidance.md) maps candidate workloads to published benchmarks, model guides and public reports, with local availability and capability gates.
- [Google AI Studio capacity inventory](../plans/google-ai-studio-capacity-inventory/index.md) records all discovered project/model combinations and dated native operation outcomes. Provider 429s establish selected model RPM, input TPM and RPD values; remaining quotas are explicitly unknown. Use its dated provider evidence and capture procedure before changing quota configuration.

## Opt-in Table quota operations

**Implemented** and locally verified; production remains memory/one. Shared quota uses a
separate Table and identity permissions, independently of credit/health state. Provisioning,
Azure clocks, actual provider admission, deployed metrics and rollout overlap require
separate acceptance evidence before scale-out. Do not enable Table quota by assuming
synthetic credit Table validation proves these gates.

Drain every writer before changing group membership, limits, accounting policy or expiry.
The persisted fingerprint also requires no pending attempts, an empty 70-second window and
prior admission day elapsed outside Pacific-midnight uncertainty. Restart preserves usage;
local reset never clears shared quota. Storage outages and ambiguous acknowledgements fail
closed. Resolve retained uncertainty through same-attempt settlement or conservative expiry,
without reusing an attempt ID or deleting the row. Capacity is 256 retained records and
48 KiB UTF-16 state per group; this bounds correctness for small free-tier workloads.

Opt-in OTLP central metrics is **Implemented** with local two-worker/restart evidence. Supply
and verify the actual collector, auth, network route, retention and resource-based aggregation
before deployment; it is not created by runtime enablement. See
[observability aggregation guidance](observability.md#central-otlp-aggregation). Local
verification does not clear production scale-out or real provider admission gates.
