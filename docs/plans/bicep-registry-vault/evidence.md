# Registry/Vault Evidence

## Evidence Log
| Item | Reference | Notes |
|---|---|---|
| Baseline | 49107a5 | Container modules and synthetic memory baseline verified |
| Independent plan review | Separate session | Approved scope, literal GUID preservation and guarded outputs |
| Compiler/deep review | Bicep 0.47.16 and independent session | Build/lint pass with existing CPU/assertion notices; 40 public params/9 outputs preserved; resource APIs/settings/GUIDs equivalent; complete-module dependencies verified |
| Azure validation matrix | New/new, new/existing, existing/new, existing/existing, Table/new | All passed with bootstrap false; known existing resources used where required |
| Conditional-path what-if | External secret registry; ACR secret mode | External has no ACR/grant; ACR secret mode provisions registry without AcrPull; no deployment made for these checks |
| Replica negative | Memory maxReplicas=2 | Rejected intended assertion |
| Baseline what-if/redeployment | Synthetic existing/existing memory | Succeeded; same change categories and no storage; runtime smoke live/ready/models/admin/metrics 200 and auth rejection 401; no inference |
| Repository checks | Repository environment | 299 passed, 8 Azurite skipped, 86.98% coverage; Ruff/format/mypy and linux/amd64 Docker build passed |
| SonarQube | Required script absent | Scan unavailable; contextual deep review completed |
| Final review/links | Independent session and local checks | No Critical/Major findings; changed relative links resolve; diff whitespace check passed |
