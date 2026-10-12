# Enablement inputs

| Input | Source | Required before |
| --- | --- | --- |
| Current environment baseline: pools, aliases, backend/account membership, auth bindings, ingress, workers/replicas, image and all app settings | Read-only operator capture; [operations](../../operations/index.md) and [production precedent](../production-foundry/index.md) | Preparing any config change |
| Exact model/wire evidence and limits | [Live verification](../zen-openrouter-live-verification/evidence.md) | Plan review; recorded |
| Current model prices, units, fees and account data-use policy | [Prior provenance](../zen-openrouter-live-verification/amendment-paid-models.md), provider public docs and operator account controls | Provisioning and production approval |
| Canonical credit ownership and safe initial values | [Shared-credit operations](../../operations/shared-resource-credit.md); operator account evidence | Each restart, including rollback |
| Environment-specific vault bundles and supported immutable-version selection | [Infra contract](../../../infra/README.md); private operator mapping | Staging changes |
| Release digest tied to tested source and current configuration schema | Existing CI/build evidence and registry metadata | Staging changes |
| Dedicated staging auth/provider budget; existing production auth preserved | Operator | Staging changes |
| Reviewed exact request manifests, durable attempt ledger and execution harness | [Activities](activities.md); reuse reviewed patterns with new identities | First inference dispatch |
| Named operator, approver, maintenance/intake-stop procedure and monitoring owner | Operator | Staging change and separate production promotion approval |

Committed parameter files are references, not proof of deployed settings or
runnable environments. No real IDs, credentials or raw configuration values
are needed for this plan review. Resolve sensitive inputs only through existing
authorized vault access at execution time and validate without printing values.

Staging must not receive production client/admin credentials or production Azure
provider credentials/topology. Prefer separate provider test credentials/accounts
with capped allowances. If a staging provider credential shares a paid account,
reserve a disjoint test allocation from its available budget, coordinate other
writers, and debit test spend before production seeds are prepared. Independent
memory ledgers must not each receive the full shared account balance.
