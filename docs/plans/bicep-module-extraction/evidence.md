# Module Extraction Evidence

## Evidence Log
| Item | Reference | Notes |
|---|---|---|
| Baseline | f9b89a5 | Typed root and synthetic memory baseline verified |
| Independent plan review | Separate session | Approved extraction and deployment-start static ID amendment |
| Build/lint | Bicep 0.47.16 | Passed, existing CPU warning and experimental assertions notice remain |
| Semantic ARM deep review | Independent session | 40 root parameters and 9 outputs preserved; exact resource settings/API/name and GUID equivalence; module ordering acyclic; no credential outputs |
| Identity ID compatibility | BCP120 investigation | Runtime-valued object cannot supply identity key/role name; separate deterministic ID preserves original value, runtime client/principal refs infer app dependency |
| Azure validation | Memory/new, Table/new | Passed with bootstrap false; memory two replicas rejected intended assertion |
| What-if | Existing baseline | Succeeded, no new physical resource categories; identity/workspace/alert/action group NoChange; role expansion Unsupported; no storage changes |
| Synthetic redeployment | Incremental deployment | Succeeded using unchanged baseline image/vault config |
| Smoke checks | Direct bounded HTTP | Live/ready/models/admin/metrics 200; unauthenticated/cross-role 401; no inference request |
| Repository checks | Repository environment | 299 passed, 8 Azurite skipped, 86.98% coverage; Ruff/format/mypy and linux/amd64 Docker build passed |
| SonarQube | Required script absent | Scan unavailable; contextual deep review completed |
| Logging checks | Deployed workspace/table | 1 GB daily cap, Analytics plan and 30-day retention confirmed |
| Links/diff | Changed documents | Relative links resolve; git diff --check passed |
