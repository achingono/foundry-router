# Container Modules Activities

## Step-By-Step Activities
1. Independently review plan before implementation. Preserve pre-change ARM outside workspace.
2. Add sealed environment config/reference and router config/reference contracts. Required secret URL object explicitly contains all eight router bindings. State runtime config contains backend, endpoint and table names; registry config contains auth mode/server/username and explicit isExternalRegistry provenance for direct-module auth assertions. No secret values in ordinary objects.
3. Extract environment into modules/containers/environment.bicep. Resolve existing workspace internally by config.workspaceName and use listKeys only in environment configuration; root module waits on observability. Return id only.
4. Extract ACA resource into modules/containers/router.bicep. Keep ingress/CORS, resource sizing, Single revisions, replica defaults, fixed env tuning, namespaced Key Vault references and all state/env mappings unchanged. Registry password remains a separate secure parameter at root and module boundaries. Identity resource ID is a separate plain string param so ACA identity key is deployment-start evaluable inside the module; client ID comes from typed config.
5. Root workload module explicitly waits on new/existing registry/vault grant resources/modules, both storage modules, environment and identity outputs as applicable. Preserve GUID formulas in root/access/storage modules. Adapt public FQDN/environment ID outputs without changing their names/types.
6. Add module-local replica/backend and auth compatibility assertions so direct module callers retain invariants. Root assertions remain unchanged. Validate compiler contracts and semantic ARM equivalence across module boundaries.
7. Build/lint; positive memory/new, memory/existing-storage, Table/new and negative replica/auth Azure validation; review what-if before redeploying same synthetic memory baseline. Check smoke and logging settings.
8. Full suite/coverage, Ruff/format/mypy, Docker build, Sonar script if present, independent contextual deep review. Update docs/traceability/evidence and validate relative links.

## Review Focus
- Module password must remain secureString; no credential outputs or object values.
- No lost access-grant dependency across workload boundary.
- Preserve exact eight secret bindings and fixed runtime settings, CORS, resource API and name.
- Keep existing CPU schema warning local; do not silently change sizing/API in this refactor.
