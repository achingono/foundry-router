# Phase 10 Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Current IaC template | `infra/main.bicep` | Implementation agent |
| Committed parameter files | `infra/parameters.staging.json`, `infra/parameters.prod.json` | Implementation agent |
| Deployment workflow behaviour | `.github/workflows/deploy.yml` | Implementation agent |
| Phase 07 design intent | `docs/plans/phase-07-infrastructure-operations/` | Project maintainer |
| Managed-identity RBAC intent | `docs/plans/phase-08-credit-integrity-hardening/`, `docs/architecture/index.md` | Project maintainer |
| Azure resource naming rules | Microsoft resource-name-rules reference | Implementation agent |
| Azure Monitor cost mechanics | Microsoft cost-optimization and table-plan references | Implementation agent |
| Per-request log inventory | `src/foundry_router/routing/__init__.py:83,204,329,412,425` (`routing_decision` at `info` with full candidate arrays), `Dockerfile:42` (uvicorn defaults, access log on), `docs/operations/observability.md` | Implementation agent |
| Security configuration guidance | `docs/configuration/security.md` | Implementation agent |

## Optional Inputs

- Confirmation from the operator of which registry and vault each environment should attach to. This is deliberately **not** recorded in the repository; it is supplied at deploy time through gitignored overrides.
- Registry SKU and vault region, needed only to confirm private-endpoint and region constraints are not silently assumed.

## Input Validation Checklist
- [x] All required inputs are current (not from a superseded version)
- [x] No required input is missing or in draft state
- [x] No subscription-specific resource name, ID, or tenant appears in any input or output artefact
