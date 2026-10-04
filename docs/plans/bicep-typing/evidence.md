# Bicep Typing Evidence

## Evidence Log

| Item | Reference | Notes |
|---|---|---|
| Baseline | Commit 3e47ba3 | Memory deployment and synthetic smoke checks verified; real inference/Table runtime pending |
| Independent plan review | Separate session | Approved with correction: preserve string public params/allowed decorators; typed internal aliases instead |
| Compiler | Bicep 0.47.16 | Build/lint pass; existing CPU schema warning and experimental assertions notice remain |
| Contract fixtures | Temporary fixtures outside workspace | Valid config/open tags accepted; invalid mode BCP033; missing field BCP035; typo BCP089; extra field BCP037 |
| Semantic ARM review | Independent deep-review session | 40 public parameters identical; 9 root string outputs preserved; role GUID inputs/order, scopes, resource properties and app module dependencies equivalent after config/alias mapping |
| Azure validation | Memory/new, memory/existing-storage, Table/new | Passed; memory maxReplicas=2 rejected intended assertion |
| Baseline what-if | Existing synthetic baseline | Succeeded, same change categories as pretyping baseline; no storage changes; nested role expansion Unsupported |
| Deployment | Typed baseline incremental deployment | Succeeded using unchanged synthetic image/configuration and public parameter interface |
| Smoke checks | Direct bounded HTTP checks | Live/ready/models/admin/metrics 200; unauthenticated/cross-role 401; no inference request made |
| Repository checks | Repository environment | 299 passed, 8 Azurite skipped; 86.98% coverage; Ruff, format and mypy passed; linux/amd64 Docker build passed |
| SonarQube | Required script absent | Scan unavailable; independent contextual deep review performed |
| Final review and links | Independent session and local link checker | No Critical/Major findings; changed relative documentation links resolve; git diff --check passed |
