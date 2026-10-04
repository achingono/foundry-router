# Memory-mode Validation Evidence

## Evidence Log

| Item | Reference | Notes |
|---|---|---|
| Original build/lint | `infra/main.bicep` | Passed on Bicep 0.41.2; existing CPU/ports warnings and experimental assertions notice |
| Original memory validation | Staging defaults | Failed: storage account not defined in template |
| Original memory what-if | Staging defaults | Succeeded, 11 creates, no storage resources |
| Original Table validation | Staging defaults with Table state | Succeeded; no runtime deployment verified |
| Independent plan review | Separate review session | Approved parent-chain investigation with full-module fallback and exact GUID preservation |
| Fix experiments | `infra/main.bicep` | Parent-chain-only and role-only isolation still failed; entire new-storage branch isolation passed |
| Fixed validation matrix | Azure group validation | Memory/new, memory/existing-storage, Table/new passed; memory maxReplicas=2 rejected by the intended assertion |
| Memory what-if | Staging defaults | Succeeded, 11 creates, no storage resources |
| Deployment prerequisites | Operator-selected shared resources | ACR supports managed-identity pull; shared vault tenant mismatch caused AKV10032; operator approved dedicated RBAC vault |
| Initial deployment | Disposable baseline | Console table plan failed before ingestion; bootstrap switch added after independent review |
| Bootstrap retry | ACA API | Unsupported containers[].ports rejected HTTP 400; field removed after independent review |
| Log plan | Classic console table | Basic rejected InvalidParameter; Analytics supported, DCR migration remains Planned |
| Configuration correction | Synthetic test inputs | Corrected temporary pricing schema to input_per_million/output_per_million; fresh revision loaded corrected secret |
| Baseline deployment | Azure incremental deployment | Final deployment Succeeded; image built linux/amd64 and pulled with managed identity; namespaced vault references resolved |
| Smoke checks | Direct bounded HTTP checks | Live/ready/models/admin/metrics HTTP 200; unauthenticated and cross-role access HTTP 401; synthetic model present; no inference request made |
| Repository verification | Repository environment | 299 passed, 8 Azurite tests skipped, 86.98% coverage after installing Azure dependencies and aiohttp locally; Ruff and mypy passed |
| Deep review | Independent session using required prompt | No Critical/Major findings; documentation evidence update suggested and addressed |
| SonarQube | Required script lookup | scripts/quality/sonarqube-scan.sh absent; scan unavailable |
| Final checks | Azure and local tools | Final memory/Table bootstrap validation passed; build/lint pass with only existing CPU warning; final what-if succeeded with no storage changes (role expansion Unsupported); healthy active revision; Analytics retention 30 days confirmed |
| Follow-ups | Existing runtime/tooling | Azure extras omit aiohttp; locally installed for full-suite verification, Table image still needs dependency correction. Existing shell smoke helper issues avoided with independent checks |
| Final review | Independent deep-review session | No Critical/Major findings; relative links resolve and git diff --check passed |
