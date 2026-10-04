# Registry/Vault Activities

## Step-By-Step Activities
1. Independently review plan; preserve pre-change ARM outside workspace.
2. Add sealed new registry/vault configuration and non-secret reference types. Registry config carries name/location/tags and grantPull bool. Identity resourceId/principalId stay separate module params; IDs are deployment-start evaluable where used in GUIDs.
3. Extract new ACR resource and conditional AcrPull grant to registry.bicep, preserving Basic SKU, admin disabled, API and exact GUID inputs with literal role GUID. Extract new vault and Secrets User grant to key-vault.bicep preserving properties/API/GUID inputs. Output resolved loginServer/vaultUri and resource ID only.
4. Root conditional calls preserve new/existing/external conditions. Resolve new loginServer/vaultUri through guarded outputs. Workload explicitly waits on the provisioning modules (and unchanged existing grants) before starting. Keep existing registry/vault lookups and cross-RG role modules untouched.
5. Validate 40 public params/9 output contracts, new resources/properties/role identities through semantic ARM comparison. Verify nested conditions and no storage/ACR resources for disabled paths.
6. Build/lint; Azure validation for new/new, new/existing, existing/new, existing/existing using known existing ACR/vault where needed, plus Table/new and negative guards. No live backend calls.
7. Review baseline what-if, redeploy same synthetic existing/existing memory baseline and run direct health/auth/models/admin/metrics smoke checks. New-resource paths receive template validation/what-if, not unverified runtime claims.
8. Full repository suite/coverage, Ruff/format/mypy, Docker build, required deep review and Sonar script if present. Update structure/operations/traceability/evidence; check links and secrets.

## Review Focus
- Module outputs must remain non-secret, not credentials or keys.
- Preserve new-grant GUID identity-resource-ID input versus existing principal-based formulas.
- Avoid unguarded outputs and lost app dependency when grants move into modules.
