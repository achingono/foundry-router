# Phase 10 Activities

## Step-By-Step Activities

1. **Establish the mode contract.** Introduce an explicit `registryMode` and `keyVaultMode`, each constrained to `new` | `existing` with `@description` and `@allowed` decorators. Decide and document that the default is `new`, because that keeps CI validation hermetic (step 11) and is the only mode that requires no pre-existing named resource.

2. **Add name-shape validation before any resource is created.** Add a Key Vault name check with the `@minLength(3)` / `@maxLength(24)` decorators, and a registry name check for 5-50 lowercase alphanumeric characters. There is no `@pattern` decorator in Bicep, so all shape rules (vault starts with a letter, ends alphanumeric, no consecutive hyphens) are enforced with `assert` statements only, with human-readable failure messages. Commit `infra/bicepconfig.json` enabling assertions (`experimentalFeaturesEnabled.assertions`) and record the minimum Bicep / Azure CLI version the template requires, so `az bicep build`, `az bicep lint` and `az deployment group validate` all evaluate the assertions identically.

3. **Split registry coordinates.** Replace the single free-text `containerImageUri` with `imageRepository` + `imageTag` and derive the reference from the resource, never by string concatenation:
   - `new` -> `<newRegistry.properties.loginServer>/<imageRepository>:<imageTag>`
   - `existing` -> `<existingRegistry.properties.loginServer>/<imageRepository>:<imageTag>`
   Reading the login server from the resource reference (rather than building `<registryName>.azurecr.io` by concatenation) keeps the pull target correct even if a registry ever uses a non-default suffix. Remove `containerImageUri` and update every caller, including `.github/workflows/deploy.yml` (see step 11). For registries outside Azure Container Registry, the server is not derived at all: it comes from an explicit `registryServer` parameter validated as hostname-only (no scheme, no path), used only together with secret-mode pull.

4. **Declare both resource shapes.** Add `existing` declarations for the registry and the vault, each with an explicit `scope` so a pre-existing resource in a different resource group can be attached. Introduce `registryResourceGroupName` and `keyVaultResourceGroupName` parameters that default to the deployment resource group.

5. **Wire registry pull authentication.** Add `registryAuthMode` (`managedIdentity` | `secret`):
   - `managedIdentity` -> populate `configuration.registries` with `identity: 'SystemAssigned'` and no credentials.
   - `secret` -> add a `@secure() registryPassword` parameter (plus a plain-text username parameter), populate `configuration.secrets` with a registry secret, and reference it from `registries[].secretRef`; the secret name must match the registry entry name. The credential value is supplied only through a gitignored `*.local.json` override or a workflow secret, and is a review gate (see exit criteria).
   Document clearly that managed-identity pull is only available for Azure Container Registry, and that other registries require the secret mode and therefore a stored credential. In secret mode the registry server is the explicit `registryServer` parameter for external registries, or the resource-derived login server for Azure registries; the two sources are never mixed. Add an `assert` guard: when `registryAuthMode` is `managedIdentity`, the resolved login server must carry the Azure registry suffix; a non-Azure registry with managed-identity mode fails validation with an actionable message rather than deploying and failing at pull time.

6. **Add the registry pull role assignment.** Grant `AcrPull` to the container app's system-assigned principal, scoped to the registry resource itself (least privilege, not the resource group), with a deterministic `guid()`-seeded assignment name derived from the app id, registry id and role definition id so redeployments are idempotent. Reference the principal from the container app resource so ARM's implicit dependency orders the assignment after the identity exists; this single-pass pattern works, but the first deploy must still be verified end to end (see step 15): a clean deploy into an empty resource group must converge, with any transient `ImagePullBackOff` distinguished from a true crash loop before the template is labelled `Implemented`.

7. **Make vault provisioning RBAC-correct.** When `keyVaultMode` is `new`, set `enableRbacAuthorization: true`, keeping the empty access policy list. Record this as an intentional behaviour change from the current template, which creates an access-policy vault and therefore cannot consume the managed identity the Phase 08 design assumes.

8. **Add the vault secret role assignment.** Grant `Key Vault Secrets User` (read-only, least privilege) to the container app's system-assigned principal, scoped to the vault, in both modes. Treat `Key Vault Secrets Officer` as out of scope unless a write requirement is demonstrated.

9. **Wire secret references.** Populate `configuration.secrets` with `keyVaultReference` entries built from the vault URI resolved by mode. Each entry requires the full shape `{ name, keyVaultUrl, identity: 'system' }`; the identity is the container app's own system-assigned identity, not the managed environment's. Add the corresponding `env` entries using `secretRef` rather than inline values. Define a secret-name prefix parameter defaulting to an `appName`-derived value, so that when a shared vault is used, router secrets are namespaced and rotation stays scoped to this workload while the default remains zero-configuration.

10. **Split environment-specific configuration out of version control.** Adopt a `*.local.json` suffix for parameter overrides that contain subscription, tenant, resource group, registry or vault names; add it to `.gitignore`. Keep committed parameter files placeholder-only, and add a placeholder-only `infra/parameters.example.json` documenting the full parameter surface.

11. **Keep CI validation hermetic.** The workflow's Bicep validation job must not depend on a resource that only exists in one subscription. Keep committed parameter files in `new` mode, and select `existing` mode through gitignored overrides or workflow inputs. Update `.github/workflows/deploy.yml` for the new parameter surface: replace the inline `--parameters containerImageUri=<external-registry reference>` overrides in the staging and production deploy jobs with `registryServer`/`imageRepository`/`imageTag` overrides, keep validation pointed at the committed `new`-mode files only, and verify the validation job's Azure authentication (it currently sets credential environment variables without an explicit login step). Record the required repository variables and secrets by name only, including the rotation owner for the secret-mode credential.

12. **Cap ingestion and alert on it.** Add a `dailyCapGb` parameter wired to `workspaceCapping.dailyQuotaGb`. The value is sized from the first week of measured baseline plus headroom, not guessed up front; the parameter defaults to a conservative placeholder and the sizing method is recorded in `infra/README.md`. Add a scheduled query alert over the `Usage` table (`where IsBillable`, per-day, per-table) firing at 90% of the cap so the cause can be investigated before the cap stops all ingestion for the day. The sizing and triage query is:

```kusto
Usage
| where IsBillable
| summarize BillableGB = sum(Quantity) / 1000 by bin(TimeGenerated, 1d), DataType
| order by TimeGenerated desc
```

Record subscription-level Advisor cost alerts and resource-group budget alerts as operator runbook steps in `infra/README.md` (they need permissions the template may not hold), not as template resources.

13. **Move console logs to the Basic plan.** Add a `consoleLogsPlan` parameter defaulting to `Basic` for the `ContainerAppConsoleLogs` table (`Microsoft.OperationalInsights/workspaces/tables`), leaving retention at 30 days. The `Usage` table stays on the Analytics plan as the alert source. Document the trade-offs where the parameter is defined: per-query scan charges, reduced alerting capability, and one plan switch per table per week — with an explicit gate to revert to Analytics if query or alert needs emerge. Explicitly hold pay-as-you-go SKU and 30-day retention as decided non-changes (retention stays inside the free window; commitment tiers wait for a measured baseline).

14. **Cut log volume at the source (telemetry-local app exception).** Two changes, both deployment telemetry with no routing/credit/API behaviour impact: (a) add `--no-access-log` to the uvicorn entrypoint in `Dockerfile`, since per-request access lines duplicate what the structured app logs and `/metrics` already cover; (b) move the candidate-array detail in the five `routing_decision` call sites (`src/foundry_router/routing/__init__.py:83,204,329,412,425`) behind `WARNING`/debug so production `INFO` emits the decision (request id, model, backend, reason, estimate) without the full per-backend evaluation. `FOUNDRY_LOG_LEVEL` stays `INFO`. Cover the level gating with focused tests and keep the 80% coverage bar.

15. **Verify.** Run `az bicep build`, `az bicep lint`, and `az deployment group validate` for all four mode combinations (`new`/`new`, `new`/`existing`, `existing`/`new`, `existing`/`existing`) against a disposable resource group. Confirm the negative cases: over-length vault name, invalid registry name, and `registryAuthMode: 'managedIdentity'` against a non-Azure registry must each fail validation with an actionable message rather than deploying. Document vault lifecycle behaviour for both modes: soft-deleted name collisions that block recreation in `new` mode, and the rule that an `existing` vault's authorisation model is detected and documented, never silently mutated. Record the Log Analytics workspace reuse rule for shared resource groups.

16. **Update documentation.** Refresh `infra/README.md` (structure, new parameters, both modes, secret provisioning, cost note that the vault itself is free and costs arise from diagnostics or networking), `docs/architecture/solution-structure.md`, `docs/configuration/security.md`, `docs/operations/index.md`, and the requirements traceability matrix. Record the new phase plan link in `docs/index.md`.

17. **Run the required gates.** Focused tests, full verification suite, lint, format, type check, Docker build, `scripts/quality/sonarqube-scan.sh` if present, and the deep-review prompt if present. Scan the final diff for subscription-specific names, IDs, endpoints, and secrets.

## Review Focus
- Correctness of the `existing` declarations, especially the cross-resource-group `scope` and the login-server read.
- Whether the single-pass role-assignment dependency on `containerApp.identity.principalId` behaves on both first deploy and redeploy.
- Whether the `new` vault's RBAC switch is an acceptable behaviour change, and whether any existing deployment would be affected.
- That no secret *value* can enter the template, and that the secret mode does not become the documented default.
- That CI validation cannot be broken by a subscription-specific name reaching a committed file.
- That the daily cap value is traceable to a measured baseline rather than a guess, and that the 90% alert query validates against the `Usage` schema.
- That the `Basic` plan default does not silently break any existing log-alert or query dependency, and that the revert path is real.
- That the step-14 log changes emit strictly less in production and alter no routing, credit, forwarding, or API behaviour.
- Consistency of the status labels used in documentation.
