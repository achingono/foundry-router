# Foundry Router Infrastructure as Code (Phases 10 and 11)

## Overview

This directory contains Azure Bicep Infrastructure as Code (IaC) templates for deploying Foundry Router on Azure Container Apps (ACA). Phase 10 adds existing-resource modes and operational guardrails. Phase 11 adds conditional Azure Table Storage provisioning and app wiring. The multi-replica deployment gate remains pending until Azure validation and a two-replica deployment pass.

Minimum verified Bicep v0.47.16 / Azure CLI 2.60.0. `infra/bicepconfig.json` enables assertions. Build/lint compile the assertions; Azure validation evaluates parameter-dependent assertions.

## Structure

- `main.bicep`: Main orchestration template (mode-parameterised)
- `bicepconfig.json`: Enables assertion evaluation
- `types/common.bicep`, `types/access.bicep`, `types/state.bicep`: exported literal aliases and sealed access/storage configuration contracts
- `types/identity.bicep`, `types/observability.bicep`: sealed resource configuration and non-secret reference contracts
- `modules/identity.bicep`: runtime user-assigned identity
- `modules/observability.bicep`: workspace, console plan, daily cap action group and query alert
- `types/containers.bicep`: sealed environment/router contracts, explicit eight secret URL bindings and non-secret resource refs
- `modules/containers/environment.bicep`: managed environment with internal workspace key lookup
- `modules/containers/router.bicep`: single-revision router, secure pull password, Key Vault references and state/runtime settings
- `modules/registryPullRole.bicep`: `AcrPull` assignment scoped to an existing registry's resource group
- `modules/vaultSecretsRole.bicep`: `Key Vault Secrets User` assignment scoped to an existing vault's resource group
- `modules/storageTableResources.bicep`: router tables and table-scoped data roles in an existing Storage account's resource group
- `modules/storageAccountResources.bicep`: new account, tables and table-scoped roles inside a conditional deployment; avoids ARM validating disabled storage references in memory mode
- `parameters.staging.json`: Placeholder-only staging parameters (`new`/`new`, hermetic CI)
- `parameters.prod.json`: Placeholder-only production parameters (`new`/`new`, `maxReplicas: 1` interim guard)
- `parameters.example.json`: Placeholder-only full parameter surface
- `*.local.json`: Gitignored environment overrides (never commit; see below)

## Modes

Public deployment parameters remain flat strings with their existing allowed values and defaults. Typed internal mode variables and config objects feed the module boundaries; direct module callers supply sealed `config` objects. New-storage output is `endpoints.tableEndpoint`; the public root `tableEndpoint` output stays a string. Resource scopes, role GUID inputs and secure registry password handling are preserved. See the [typing plan](../docs/plans/bicep-typing/index.md). Observability and identity extraction is **Implemented** and [verified](../docs/plans/bicep-module-extraction/evidence.md).

The environment module keeps logging-key lookup internal; its root invocation waits for observability. Runtime identity client/principal IDs come from its module; deployment-start ACA identity keys and role names use the identical deterministic resource ID. Module outputs contain no workspace keys or credential values.

Environment and router extraction is **Implemented** and [verified](../docs/plans/bicep-container-modules/evidence.md). The router receives a sealed config, a separate identity resource ID and a separate secure registry password. Its config requires all eight secret URLs and explicit registry provenance; direct callers must preserve grant ordering and match registry provenance to the supplied source. The root waits for registry/vault/table access grants and environment/identity provisioning. Root parameters and output names/types remain compatible. Registry/vault extraction and a public discriminated deployment API remain **Design target**.

| Parameter | Values | Default | Meaning |
|---|---|---|---|
| `registryMode` | `new` \| `existing` | `new` | Provision ACR or attach to a pre-existing registry |
| `keyVaultMode` | `new` \| `existing` | `new` | Provision vault or attach to a pre-existing vault |
| `registryAuthMode` | `managedIdentity` \| `secret` | `managedIdentity` | User-assigned identity pull (ACR only) or stored credential pull |
| `stateBackend` | `memory` \| `table` | `memory` | Process-local state or shared Azure Table state |
| `storageMode` | `new` \| `existing` | `new` | Provision a hardened account or attach to an existing account when `stateBackend=table` |

Defaults are `new` so CI validation stays hermetic (no pre-existing named resource required). Select `existing` only through gitignored `*.local.json` overrides or workflow inputs.

An `existing` reference can read across resource groups via `registryResourceGroupName` / `keyVaultResourceGroupName` (default: deployment resource group). A resource-group-scoped template cannot create resources in another group, so role assignments on an `existing` registry/vault deploy through a module scoped to `resourceGroup(<name>)`. The deploying principal needs `Microsoft.Authorization/roleAssignments/write` on that scope plus table-create rights where applicable.

## Image coordinates

No free-text image reference remains. The image is derived, never concatenated:

- `new` -> `<newRegistry.properties.loginServer>/<imageRepository>:<imageTag>`
- `existing` -> `<existingRegistry.properties.loginServer>/<imageRepository>:<imageTag>`

Reading the login server from the resource keeps the pull target correct even for non-default suffixes. For registries outside ACR, the server comes from the explicit `registryServer` parameter (hostname only, no scheme/path), used only with secret-mode pull. `containerImageUri` is removed; deploy jobs override `imageRepository`/`imageTag` (and `registryServer` for external registries).

Managed-identity pull is only available for ACR. An `assert` fails validation with an actionable message when `registryAuthMode` is `managedIdentity` with a non-Azure registry server, rather than deploying and failing at pull time.

## Registry and vault wiring

- A user-assigned runtime identity is created before the container app. `AcrPull`, `Key Vault Secrets User`, and (in table mode) table-scoped `Storage Table Data Contributor` assignments target this identity and are dependencies of the app. This gives image pull and Key Vault references a principal before app provisioning. Container Apps uses the same identity for those references; `FOUNDRY_AZURE_CLIENT_ID` selects it for the Table SDK.
- `managedIdentity` -> `configuration.registries` carries the user-assigned identity resource ID and no credential; `AcrPull` is scoped to the ACR resource. External registries do not create a placeholder ACR and require secret-mode pull.
- `secret` -> a `@secure() registryPassword` parameter (plus plain-text username) populates `configuration.secrets` and `registries[].passwordSecretRef`. The value comes only from a gitignored `*.local.json` override or workflow secret.

New vaults set `enableRbacAuthorization: true` (intentional change from the access-policy vault). The runtime identity receives `Key Vault Secrets User` (read-only, least privilege) scoped to the vault. Key Vault references specify that user-assigned identity and expose values only through `secretRef` env entries. A `secretNamePrefix` parameter (default: `appName`-derived) namespaces router secrets in shared vaults. Secret *values* are never in the template; they remain operator-supplied out of band.

First-deploy convergence: verify a clean deploy into an empty resource group end to end; distinguish transient `ImagePullBackOff` (role propagation) from a true crash loop before labelling the template `Implemented`.

Vault lifecycle: soft-deleted name collisions block recreation in `new` mode (recover or purge first); an `existing` vault's authorisation model is detected and documented, never silently mutated. In shared resource groups the Log Analytics workspace is reused per the workspace-reuse rule below.

## Parameters and local overrides

Committed parameter files are placeholder-only. Environment-specific values (subscription, tenant, resource-group, registry, vault names, credentials) go in `*.local.json` (gitignored, confirmed untracked) or workflow inputs. `infra/parameters.example.json` documents the full surface with placeholders.

Required repository variables/secrets by name only (values never committed):

- Variables: `FOUNDRY_IMAGE_REPOSITORY` (lowercase GHCR image repository path), `FOUNDRY_ALERT_EMAIL` (required alert recipient).
- Secrets: `AZURE_CREDENTIALS_STAGING`, `AZURE_CREDENTIALS_PRODUCTION` (deploy + Bicep validation login), `AZURE_RESOURCE_GROUP_STAGING`, `AZURE_RESOURCE_GROUP_PRODUCTION`, `ADMIN_API_KEY_PRODUCTION` (smoke test). GHCR pull uses the workflow-scoped `GITHUB_TOKEN` with package-read permission; other secret-mode registry credentials remain environment supplied and are rotated by the registry owning team.

## Cost guardrails

- The Key Vault itself is free; costs arise from diagnostics or networking.
- `dailyCapGb` wires to `workspaceCapping.dailyQuotaGb`. Size it from the first week of measured baseline plus headroom, not upfront guessing; the committed default is a conservative placeholder. Triage query:
  ```kusto
  Usage
  | where IsBillable
  | summarize BillableGB = sum(Quantity) / 1000 by bin(TimeGenerated, 1d), DataType
  | order by TimeGenerated desc
  ```
- A rolling-24-hour scheduled query alert fires at 90% of the cap and sends email through its action group. `alertEmailAddress` is required; committed parameter files use a placeholder and deployment workflows must set `FOUNDRY_ALERT_EMAIL`. Cap-hit drill: check the alert, run the triage query grouped by `DataType`, identify the spiking table, then check `ContainerAppConsoleLogs_CL` volume and revision count before raising the cap.
- Subscription Advisor cost alerts and resource-group budget alerts are operator runbook steps (permissions the template may not hold), not template resources.
- `consoleLogsPlan` supports `Analytics` for `ContainerAppConsoleLogs_CL` (retention 30 days; pay-as-you-go SKU unchanged). Azure deployment confirmed the current ACA integration creates a Classic custom-log table and rejects Basic. Basic requires a separately planned DCR-based ingestion migration. Change any old local overrides supplying Basic to Analytics.
- New-workspace bootstrap requires two incremental deployments: first set `configureConsoleLogsPlan=false`, start the app and confirm ingestion creates `ContainerAppConsoleLogs_CL`; then redeploy with `configureConsoleLogsPlan=true` (the default). False leaves the plan unmanaged; the ingestion-created table initially uses Analytics. A plan update before the table exists fails with `ResourceNotFound`. Reuse the same names on partial-deployment retries.
- Source-volume reduction: uvicorn `--no-access-log` (access lines duplicate structured logs/`/metrics`; entrypoint stays single-worker since each worker would hold its own in-memory state) and `routing_decision` candidate-array detail gated to `WARNING`/debug (production `INFO` keeps request id, model, backend, reason, estimate only).

## Distributed State

Table resources, role assignments and endpoint settings are emitted only when `stateBackend: table`. The table endpoint is read from `primaryEndpoints.table`, not synthesized. The app uses token authentication only; no storage key or connection string is passed to it. New accounts disable shared-key access, require TLS 1.2/HTTPS, and disable blob public access. Existing accounts are not mutated.

| App setting | Bicep source | App setting field | Default |
|---|---|---|---|
| `FOUNDRY_STATE_BACKEND` | `stateBackend` parameter | `Settings.state_backend` | `memory` |
| `FOUNDRY_AZURE_CLIENT_ID` | `runtimeIdentity.outputs.identityRef.clientId` | `AzureTableEntityClient` managed-identity credential selection | UAMI client ID |
| `FOUNDRY_TABLE_ENDPOINT` | `storageAccount.properties.primaryEndpoints.table` | `Settings.table_endpoint` | empty in memory mode |
| `FOUNDRY_TABLE_HEALTH_NAME` | `tablePrefix` + `health` | `Settings.table_health_name` | app-derived |
| `FOUNDRY_TABLE_CREDIT_NAME` | `tablePrefix` + `credit` | `Settings.table_credit_name` | app-derived |
| `FOUNDRY_RATE_LIMIT_REPLICA_SHARE` | `maxReplicas` | `Settings.rate_limit_replica_share` | `1` |

`maxReplicas > 1` requires `stateBackend: table`; `maxReplicas` is at least 1. Per-replica in-memory provider quota limits are divided by `maxReplicas`, so actual usage below capacity underuses quota. Protected emergency fallback and brief revision overlap remain documented exceptions. `activeRevisionsMode: 'Single'` limits active traffic revisions, but old and new revisions can overlap briefly during rollout.

State adapter, concrete identity-only client, conditional storage template, startup wiring, and Azurite coverage are implemented in code. Table/new template validation has passed; Table runtime deployment, remaining attach-path validation and a two-replica Azure deployment are still pending, so deployed multi-replica shared state remains **Partially implemented** and production parameters remain memory-backed with one replica.

## Validation

```bash
az bicep build --file infra/main.bicep
az bicep lint --file infra/main.bicep
az deployment group validate --resource-group <disposable-rg> --template-file infra/main.bicep --parameters infra/parameters.staging.json
```

Cover all four mode combinations (`new`/`new`, `new`/`existing`, `existing`/`new`, `existing`/`existing`) against a disposable resource group. Negative cases must fail with actionable messages: over-length vault name, invalid registry name, `managedIdentity` against a non-Azure registry, secret-mode external-server validation, and memory mode with `maxReplicas=2`. Remaining warning: `BCP036` (`cpu` typed as string). The unsupported container `ports` block was removed after Azure rejected it; ingress targetPort must match the image listener (8000 in the supplied image). The experimental-assertions notice comes from the required `bicepconfig.json`.

Memory/new, memory/existing-storage and Table/new Azure validation passed after isolating new storage in its module. A memory-backed single-replica synthetic baseline deployed successfully with an existing cross-resource-group ACR and a dedicated RBAC vault. Health, authentication, models, admin and metrics checks passed; this does not verify real inference or deployed Table state. See [validation evidence](../docs/plans/memory-mode-validation/evidence.md).

For attached vaults, verify `properties.tenantId` matches the subscription tenant as well as RBAC/network access. The baseline encountered `AKV10032` on a shared vault left in another tenant and used a dedicated compatible vault without changing the shared vault. Secret writers need explicit data-plane permission; the runtime receives only Secrets User. After configuration-secret changes, ensure a fresh revision has loaded the updated values.

## Health Checks

After deployment, verify:

```bash
FQDN=$(az deployment group show --name <deployment> --resource-group $RESOURCE_GROUP --query 'properties.outputs.containerAppFqdn.value' -o tsv)
curl https://$FQDN/health/live
curl https://$FQDN/health/ready
az containerapp revision list --name <app> --resource-group $RESOURCE_GROUP --query '[].{name:name,active:properties.active,traffic:properties.trafficWeight}'
```

Before raising replicas, validate table-mode and verify all configured backend balance rows are present and `/health/ready` is green. Do not switch production until starting balances are reconciled and the previous memory-backed revision is drained; no in-memory state migrates.

## Cleanup

```bash
az deployment group delete --name <deployment> --resource-group $RESOURCE_GROUP
```

Note: Key Vault is soft-deleted and can be recovered within 90 days.
