# Public Interface Activities

## Step-By-Step Activities
1. Independently review before implementation.
2. Add exported sealed discriminated registry (ACR/external), ACR auth (managedIdentity/secret), resource lifecycle (new/existing) and state (memory/table) contracts. Existing resources require name/resourceGroup; new resources require name. External requires server/username and has no managedIdentity auth choice. Table requires account/tablePrefix; memory excludes them.
3. Add infra/typed.bicep as a resource-group-scoped adapter invoking main.bicep. Retain naming/image/scaling/logging knobs and explicit eight secret names. Forward all supported parameters and nine outputs. Resolve unused flat fields to valid placeholders without provisioning anything; guarded property access must not dereference absent union fields. Password remains separate secureString at both boundaries. Do not duplicate resource implementations or change main.bicep/CI.
4. Add placeholder-only typed example parameters. Verify compiler rejection of malformed branch shapes and acceptance of valid variants using temporary fixtures.
5. Validate typed new/existing and memory/Table combinations plus negative replica/auth choices; review baseline what-if then redeploy the same synthetic memory baseline through typed.bicep and smoke check. Account for one added nested deployment boundary and name-scope/GUID invariance.
6. Run full suite/coverage, Ruff/format/mypy, Docker build, required deep review and Sonar script if present. Update documentation/evidence/traceability and links. New-resource runtime and Table runtime remain unverified.

## Review Focus
- Preserve flat default semantics and public output values; resourceGroup scope identical through adapter.
- No credentials in ordinary objects, committed examples or outputs.
- Nested discriminators should reject invalid combinations at the public boundary.
