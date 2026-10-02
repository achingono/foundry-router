# Phase 10 Outputs

## Mandatory Outputs

| Output | Description | Format |
|---|---|---|
| Mode-parameterised template | `infra/main.bicep` supporting `registryMode` and `keyVaultMode` across `new` and `existing` | Bicep |
| Assertion configuration | `infra/bicepconfig.json` enabling assertions, with the minimum Bicep / Azure CLI version recorded | JSON |
| Existing-resource declarations | `existing` registry and vault symbols with explicit scope | Bicep |
| Registry pull wiring | `configuration.registries` plus `AcrPull` role assignment for the system-assigned identity | Bicep |
| Vault secret wiring | `configuration.secrets` with `keyVaultReference`, `secretRef` env entries, and `Key Vault Secrets User` assignment | Bicep |
| Name validation | Length and shape decorators plus `assert` statements covering the vault and registry limits | Bicep |
| Ingestion cap and alert | `dailyCapGb` parameter wired to `workspaceCapping.dailyQuotaGb`, plus a 90%-of-cap scheduled query alert over the `Usage` table | Bicep |
| Console-log table plan | `consoleLogsPlan` parameter defaulting to `Basic` for `ContainerAppConsoleLogs`, retention held at 30 days | Bicep |
| Source-volume reduction | `--no-access-log` on the uvicorn entrypoint; candidate-array detail in `routing_decision` gated behind `WARNING`/debug with focused tests | Dockerfile, Python, tests |
| Measured log baseline | Per-request stdout volume recorded from a load run, with the cap-sizing calculation shown | Evidence log |
| Split parameter files | Committed placeholder-only parameter files, a placeholder-only `infra/parameters.example.json`, and a gitignored `*.local.json` convention | JSON, `.gitignore` |
| Pipeline alignment | Updated `.github/workflows/deploy.yml` for the new parameter surface, referencing variables and secrets by name only | YAML |
| Interim replica guard | `@maxValue(1)` on `maxReplicas`; `infra/parameters.prod.json` set to `1` | Bicep, JSON |
| Multi-replica status correction | Documents listed in activities step 16 relabelled `Partially implemented` with a Phase 11 reference | Markdown |
| Infrastructure documentation | `infra/README.md` covering both modes, secret provisioning, and cost boundaries | Markdown |
| Traceability update | Requirements traceability and operational documentation updated for the design change | Markdown |

## Optional Outputs

- A short operator runbook section in `infra/README.md` for attaching to a pre-existing vault, including the required role assignments and the secret-name prefix rule.
- An optional decision record for the registry-versus-secret pull trade-off if the review concludes it warrants a separate ADR.

## Output Quality Checklist
- [ ] All mandatory outputs produced
- [ ] All outputs reviewed before gate
- [ ] Evidence log updated with output references
- [ ] No subscription, tenant, registry, vault or resource group name from any live environment appears in any output
- [ ] Documentation status labels used consistently (`Implemented`, `Partially implemented`, `Planned`, `Design target`)
