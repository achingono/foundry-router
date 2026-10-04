# Module Extraction Activities

## Step-By-Step Activities
1. Obtain independent review before implementation; save compiled ARM outside the workspace.
2. Add sealed ObservabilityConfig/ObservabilityRef and RuntimeIdentityConfig/RuntimeIdentityRef types. Identity outputs contain id/clientId/principalId; observability outputs contain workspace id/name only.
3. Extract workspace, conditional console plan, action group and query alert into observability.bicep. Pass exact names, displayName, location, tags, cap, email and plan/bootstrap values. Preserve APIs, query and retention.
4. Keep managed environment inline. Declare a root existing workspace by its known name and make the environment depend on the observability module before accessing customerId/listKeys. Do not output logging keys.
5. Extract runtime identity into identity.bicep. Replace consumers with its typed output while preserving every GUID argument's value/order, all role scopes and existing module names. App and grants must wait for the identity module.
6. Compare ARM resource properties and IDs across nested boundaries; verify all public parameters/outputs unchanged and inspect dependencies. Build/lint and perform positive/negative Azure validation and reviewed what-if.
7. Redeploy the same synthetic memory baseline, check health/auth/models/admin/metrics and logging cap/retention. Do not change replicas, backend topology or image.
8. Run full suite/coverage, Ruff/format/mypy, Docker build, required deep review and Sonar script if present. Update architecture/operations/traceability and evidence, validate links.
9. Compiler requires deployment-start identity IDs for ACA identity keys and inline role names. Resolve a separate static identity ID with resourceId using the unchanged name; use module outputs for client/principal IDs. The app's runtime output references infer the identity module dependency (confirmed in compiled ARM); explicit dependsOn is redundant.

## Review Focus
- Nested deployment ordering adds a completion boundary; bootstrap false must still permit log ingestion.
- Existing workspace lookup must not introduce a reference before provisioning.
- No credential outputs, GUID drift, shared resource mutation or unverified Table runtime claims.
