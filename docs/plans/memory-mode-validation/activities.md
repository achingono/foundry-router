# Memory-mode Validation Activities

## Step-By-Step Activities
1. Independently review this plan before implementation.
2. Investigate ARM validation of conditional table child resources and table-scoped roles. Start with explicit account/service/table parent relationships; if needed isolate conditional storage provisioning and roles in a Table-only module while preserving resource names, GUID formulas, and access scopes.
3. Build/lint and validate memory/new and memory/existing-storage combinations, plus Table/new. Check negative replica assertion and what-if resource changes.
4. Run repository tests with coverage, lint, formatting and type checks; build a Linux amd64 container. Run SonarQube script if present and perform the required deep review.
5. Discover shared registry/vault settings. Use a unique image tag and secret prefix; preserve shared resource settings. Obtain backend inputs or explicitly use synthetic configuration for health/auth/models only.
6. Populate eight namespaced vault secrets through redacted tooling, provision access dependencies, deploy memory mode with one replica, then verify live/ready/auth/models/admin/metrics. Check revisions and logging without displaying secrets, prompts, or outputs.
7. Update operational documentation, traceability, evidence, and documentation links. Record blockers and retain truthful deployment status.
8. First deployment exposed a missing `ContainerAppConsoleLogs_CL` table. Add a default-enabled `configureConsoleLogsPlan` switch: explicitly disable it for workspace bootstrap, start the app and confirm ingestion creates the table, then re-enable the existing plan resource. Preserve cap/alert defaults and document both passes. The initial Basic choice was superseded by step 10 after Azure rejected it.
9. Bootstrap retry confirmed ACA rejects `containers[].ports` with HTTP 400. Remove this unsupported block; retain ingress `targetPort` and image entrypoint port 8000. Validate and retry the same deployment.
10. The ingestion-created table is CustomLog Classic; Azure rejects Basic with `InvalidParameter` and requires DCR-based migration. Restrict this template's consoleLogsPlan to Analytics and update committed parameters/documentation. Retain cap/retention/alert; document Basic as a separate planned ingestion migration.

## Review Focus
- Conditional storage must not leak references or resources into memory mode.
- Table access remains identity-only and table-scoped; existing parent resources remain unchanged.
- Do not confuse a synthetic readiness baseline with successful real backend forwarding or multi-replica validation.
