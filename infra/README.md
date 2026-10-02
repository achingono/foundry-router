# Foundry Router Infrastructure as Code (Phase 10)

## Overview

This directory contains Azure Bicep Infrastructure as Code (IaC) templates for deploying Foundry Router on Azure Container Apps (ACA). Phase 10 extends the Phase 07 template so a single template can either provision a new container registry and Key Vault or attach to pre-existing ones, wires image pull and Key Vault secret references, and enforces cost and replica guardrails.

Minimum Bicep v0.30.0 / Azure CLI 2.60.0 (`infra/bicepconfig.json` enables `assertions`; `az bicep build`, `az bicep lint` and `az deployment group validate` evaluate them identically).

## Structure

- `main.bicep`: Main orchestration template (mode-parameterised)
- `bicepconfig.json`: Enables assertion evaluation
- `modules/registryPullRole.bicep`: `AcrPull` assignment scoped to an existing registry's resource group
- `modules/vaultSecretsRole.bicep`: `Key Vault Secrets User` assignment scoped to an existing vault's resource group
- `parameters.staging.json`: Placeholder-only staging parameters (`new`/`new`, hermetic CI)
- `parameters.prod.json`: Placeholder-only production parameters (`new`/`new`, `maxReplicas: 1` interim guard)
- `parameters.example.json`: Placeholder-only full parameter surface
- `*.local.json`: Gitignored environment overrides (never commit; see below)

## Modes

| Parameter | Values | Default | Meaning |
|---|---|---|---|
| `registryMode` | `new` \| `existing` | `new` | Provision ACR or attach to a pre-existing registry |
| `keyVaultMode` | `new` \| `existing` | `new` | Provision vault or attach to a pre-existing vault |
| `registryAuthMode` | `managedIdentity` \| `secret` | `managedIdentity` | System-identity pull (ACR only) or stored credential pull |

Defaults are `new` so CI validation stays hermetic (no pre-existing named resource required). Select `existing` only through gitignored `*.local.json` overrides or workflow inputs.

An `existing` reference can read across resource groups via `registryResourceGroupName` / `keyVaultResourceGroupName` (default: deployment resource group). A resource-group-scoped template cannot create resources in another group, so role assignments on an `existing` registry/vault deploy through a module scoped to `resourceGroup(<name>)`. The deploying principal needs `Microsoft.Authorization/roleAssignments/write` on that scope plus table-create rights where applicable.

## Image coordinates

No free-text image reference remains. The image is derived, never concatenated:

- `new` -> `<newRegistry.properties.loginServer>/<imageRepository>:<imageTag>`
- `existing` -> `<existingRegistry.properties.loginServer>/<imageRepository>:<imageTag>`

Reading the login server from the resource keeps the pull target correct even for non-default suffixes. For registries outside ACR, the server comes from the explicit `registryServer` parameter (hostname only, no scheme/path), used only with secret-mode pull. `containerImageUri` is removed; deploy jobs override `imageRepository`/`imageTag` (and `registryServer` for external registries).

Managed-identity pull is only available for ACR. An `assert` fails validation with an actionable message when `registryAuthMode` is `managedIdentity` with a non-Azure registry server, rather than deploying and failing at pull time.

## Registry and vault wiring

- `managedIdentity` -> `configuration.registries` carries `identity: 'system'` and no credential; `AcrPull` is granted to the container app's system-assigned principal scoped to the registry resource (deterministic `guid()`-seeded name; ARM implicit dependency on `containerApp.identity.principalId` orders it after the identity exists).
- `secret` -> a `@secure() registryPassword` parameter (plus plain-text username) populates `configuration.secrets` and `registries[].passwordSecretRef`. The value comes only from a gitignored `*.local.json` override or workflow secret.

New vaults set `enableRbacAuthorization: true` (intentional change from the access-policy vault). The container app identity receives `Key Vault Secrets User` (read-only, least privilege) scoped to the vault. Secrets use the full `keyVaultReference` shape `{ name, keyVaultUrl, identity: 'system' }` (the app's own identity) with `secretRef` env entries. A `secretNamePrefix` parameter (default: `appName`-derived) namespaces router secrets in shared vaults. Secret *values* are never in the template; they remain operator-supplied out of band.

First-deploy convergence: verify a clean deploy into an empty resource group end to end; distinguish transient `ImagePullBackOff` (role propagation) from a true crash loop before labelling the template `Implemented`.

Vault lifecycle: soft-deleted name collisions block recreation in `new` mode (recover or purge first); an `existing` vault's authorisation model is detected and documented, never silently mutated. In shared resource groups the Log Analytics workspace is reused per the workspace-reuse rule below.

## Parameters and local overrides

Committed parameter files are placeholder-only. Environment-specific values (subscription, tenant, resource-group, registry, vault names, credentials) go in `*.local.json` (gitignored, confirmed untracked) or workflow inputs. `infra/parameters.example.json` documents the full surface with placeholders.

Required repository variables/secrets by name only (values never committed):

- Variables: `FOUNDRY_IMAGE_REPOSITORY` (image repository path); secret-mode additionally uses a registry server variable.
- Secrets: `AZURE_CREDENTIALS_STAGING`, `AZURE_CREDENTIALS_PRODUCTION` (deploy + Bicep validation login), `AZURE_RESOURCE_GROUP_STAGING`, `AZURE_RESOURCE_GROUP_PRODUCTION`, `ADMIN_API_KEY_PRODUCTION` (smoke test), plus the secret-mode registry credential (rotation owner: registry owning team; rotate via `*.local.json`/workflow secret update, never in repo).

## Cost guardrails

- The Key Vault itself is free; costs arise from diagnostics or networking.
- `dailyCapGb` wires to `workspaceCapping.dailyQuotaGb`. Size it from the first week of measured baseline plus headroom, not upfront guessing; the committed default is a conservative placeholder. Triage query:
  ```kusto
  Usage
  | where IsBillable
  | summarize BillableGB = sum(Quantity) / 1000 by bin(TimeGenerated, 1d), DataType
  | order by TimeGenerated desc
  ```
- A scheduled query alert fires at 90% of the cap. Cap-hit drill: check the alert, run the triage query grouped by `DataType`, identify the spiking table, then check `ContainerAppConsoleLogs` volume and revision count before raising the cap.
- Subscription Advisor cost alerts and resource-group budget alerts are operator runbook steps (permissions the template may not hold), not template resources.
- `consoleLogsPlan` defaults to `Basic` for `ContainerAppConsoleLogs` (retention 30 days; pay-as-you-go SKU unchanged). Trade-offs: per-query scan charges, reduced alerting, one plan switch per table per week. Revert to `Analytics` if query/alert needs emerge.
- Source-volume reduction: uvicorn `--no-access-log` (access lines duplicate structured logs/`/metrics`; entrypoint stays single-worker since each worker would hold its own in-memory state) and `routing_decision` candidate-array detail gated to `WARNING`/debug (production `INFO` keeps request id, model, backend, reason, estimate only).

## Replica guard (interim)

`maxReplicas` carries `@maxValue(1)` and every committed parameter file sets `1` because the app runs only in-memory credit, health and rate-limit state (`src/foundry_router/main.py`). `activeRevisionsMode: 'Single'` is explicit so no second revision serves traffic. Residual window: during a single-revision rollout the old and new revisions briefly run together until traffic switches and the old drains, and each new revision restarts in-memory credit from configured initial balances. Multi-replica is lifted only by Phase 11 (`stateBackend: table` + Storage wiring); Phase 11 replaces the decorator with an `assert` tied to `stateBackend`.

Deployed multi-replica shared state (Table Storage across replicas) is `Partially implemented`: the adapter code and unit tests are `Implemented`, but no deployment provisions or consumes them yet (storage provisioning, client wiring and multi-replica deployment are `Planned` in Phase 11).

## Validation

```bash
az bicep build --file infra/main.bicep
az bicep lint --file infra/main.bicep
az deployment group validate --resource-group <disposable-rg> --template-file infra/main.bicep --parameters infra/parameters.staging.json
```

Cover all four mode combinations (`new`/`new`, `new`/`existing`, `existing`/`new`, `existing`/`existing`) against a disposable resource group. Negative cases must fail with actionable messages: over-length vault name, invalid registry name, `managedIdentity` against a non-Azure registry, secret-mode external-server validation, and `maxReplicas=2` (fails referencing Phase 11). Known pre-existing warnings: `BCP036` (`cpu` typed as string) and `BCP037` (`ports` on `Container`); no new warnings introduced. The experimental-assertions notice comes from the required `bicepconfig.json`.

## Health Checks

After deployment, verify:

```bash
FQDN=$(az deployment group show --name <deployment> --resource-group $RESOURCE_GROUP --query 'properties.outputs.containerAppFqdn.value' -o tsv)
curl https://$FQDN/health/live
curl https://$FQDN/health/ready
az containerapp revision list --name <app> --resource-group $RESOURCE_GROUP --query '[].{name:name,active:properties.active,traffic:properties.trafficWeight}'
```

Expect exactly one active revision receiving 100% of traffic.

## Cleanup

```bash
az deployment group delete --name <deployment> --resource-group $RESOURCE_GROUP
```

Note: Key Vault is soft-deleted and can be recovered within 90 days.
