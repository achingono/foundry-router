# Phase 10 Bicep Existing-Resource Support

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Extend `infra/main.bicep` so a single template can either provision a new container registry and Key Vault or attach to pre-existing ones, wire the container app to actually pull its image and read its secrets, and enforce that no Azure subscription-specific names (registry, vault, resource group, subscription, tenant) ever reach version control.

## Scope

### In Scope
- Explicit, parameterised selection between provisioned and pre-existing resources for:
  - Azure Container Registry (`Microsoft.ContainerRegistry/registries`)
  - Azure Key Vault (`Microsoft.KeyVault/vaults`)
- Derived image coordinates (`imageRepository` + `imageTag`) so the container image reference cannot drift from the configured registry.
- Two registry authentication modes: managed identity pull (`AcrPull`) and registry-secret pull.
- Explicit external-registry path: a validated `registryServer` parameter for registries outside Azure Container Registry, so no free-text image reference is needed. `containerImageUri` is removed, not retained as an override.
- Pre-created user-assigned runtime identity with least-privilege registry/vault role assignments before app provisioning, plus `keyVaultReference` secret wiring.
- Name-length and name-shape validation, including the Key Vault global name limit that currently fails late in deployment.
- Log Analytics cost guardrails: a parameterised daily ingestion cap with a 90%-of-cap alert, a `Basic` table plan for `ContainerAppConsoleLogs_CL`, an explicit decision to hold pay-as-you-go SKU and 30-day retention, and source-volume reduction (uvicorn access logs off; per-request candidate-array detail gated behind `WARNING`/debug).
- Environment-specific parameter override files excluded from version control; committed parameter files limited to placeholders.
- Interim single-replica guard: `maxReplicas` constrained to `1` in the template and in every committed parameter file, because the deployed app runs only in-memory credit, health and rate-limit state (`src/foundry_router/main.py:55-58`). Lifted only by [Phase 11](../phase-11-distributed-state-wiring/index.md).
- Status correction for documents that describe Azure Table Storage multi-replica state as deployed or verified (activities step 16).
- Documentation and requirements-traceability updates.

### Out of Scope
- Private endpoints, service endpoints, or network ACL changes on the registry or vault. No registry SKU is selected by this phase, so any future private-endpoint requirement needs a separate SKU decision first.
- Availability-zone redundancy, geo-replication, or registry service tiers.
- Custom domains, DNS, WAF, Front Door, or other edge resources.
- Moving or renaming any resource that already exists in a live subscription.
- Populating secret *values* in the template; values remain operator-supplied out of band.
- Ingestion-time DCR transformations for log filtering. Complexity and the over-50%-filter billing quirk make this a last resort, only if source-volume reduction and table plans prove insufficient.
- Commitment-tier reservation. The deployment is new with no measured baseline; pay-as-you-go stands until sustained ingestion approaches commitment thresholds, at which point a separate decision is recorded.
- Azure Storage account, tables, `Storage Table Data Contributor` assignment, and the application-side Table client wiring. These ship together in [Phase 11](../phase-11-distributed-state-wiring/index.md) so the template and its only consumer are verified end to end; provisioning storage here would be unconsumed and unverifiable infrastructure.
- Application-code changes except one telemetry-local exception: gating the per-request candidate-array log detail behind `WARNING`/debug (activities step 14). No routing, credit, forwarding, or API behaviour changes.

## Entry Criteria
- Phase 07 IaC exists and builds (`infra/main.bicep`, `infra/parameters.staging.json`, `infra/parameters.prod.json`).
- The container app already requests a system-assigned managed identity.
- `infra/README.md` and the requirements traceability matrix are current for Phase 07.
- This plan has been reviewed by a different session before any template edit.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
