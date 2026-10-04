# Table Runtime Evidence

| Item | Reference | Notes |
|---|---|---|
| Baseline | d70f0ea | Public typed interface committed; memory baseline smoke verified |
| Plan review | Independent session | Approved precise clean-image, shared-resource preservation and adapter/restart checks |
| Packaging | pyproject.toml | aiohttp>=3.9,<4 added to Azure extra only; final linux/amd64 image constructs actual SDK TableClient via wrapper _get_client and closes successfully |
| Initial Azure deployment | New test Storage account | RoleDefinitionDoesNotExist exposed invalid Table role ID; account/tables created, grants failed |
| Corrected role | Azure role-definition lookup and independent review | Storage Table Data Contributor ID ends aaa3; both modules corrected, table scopes preserved; invalid grants never created |
| Deployment | Separate synthetic Table app, min/max 1 | Incremental typed deployment Succeeded with existing registry/vault/environment/workspace; original baseline retained |
| Account/access | Azure inspection | Shared keys false, HTTPS true, TLS1_2, blob public false; runtime table-scoped grants; no storage credential configuration |
| Smoke/readiness | Direct bounded HTTP | Table app live/ready/models/admin/metrics 200; unauthenticated/cross-role 401; no inference |
| Real Azure adapter checks | Two independent AzureCli token-authenticated clients/adapters | Concurrent 60-unit reservations with 10-unit reserve accepted exactly one; settlement/reconciliation preserved competing reservations; health cooldown visible after cache bound |
| Restart persistence | Synthetic estimate marker 77 | Fresh adapter initialization and actual app restart preserved marker; readiness passed; synthetic estimate restored to 100 and isolated verification partition removed |
| Baseline/cleanup | Original memory app | Smoke checks still passed; temporary operator account data grant removed; Azurite container stopped |
| Tests | Repository environment | Focused 31 passed; full 307 passed including eight Azurite tests, 88.26% coverage; Ruff/format/mypy passed |
| Remaining gates | Operations | Two deployed replicas, Table/existing runtime and real inference pending; production unchanged |
| Deep review/links | Independent session | No Critical/Major findings; relative links and diff checks passed; Sonar script absent |
