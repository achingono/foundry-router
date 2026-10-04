# Activities

1. Independently review plan before resource creation.
2. Create a dedicated StorageV2 Standard_LRS test account in operator-selected shared RG, with shared keys disabled, HTTPS/TLS1_2 and blob public access disabled. Record sanitized parent settings before attachment.
3. Use typed.bicep existing storage branch, account resourceGroup shared RG, unique table prefix/app/identity; preserve shared environment/workspace/tags/alerts/vault/image and original test apps. min/max1. Validate and review what-if in incremental mode: only child tables/scoped grants in account RG, no parent account writes.
4. Deploy isolated app in existing test RG; verify table-scoped managed identity grants and ready/auth/models/admin/metrics. Replica-targeted adapter creates/reserves/releases a synthetic verification partition; actual configured synthetic balance persists across targeted container restart. Clean isolated state and confirm parent properties unchanged.
5. Redeploy identical parameters to establish idempotent assignments. Smoke-check original memory/two-replica apps. No inference or production cut-over.
6. Evidence-only verification: retain previous full 307-pass/88.26% suite unless code change needed. Required contextual deep review, docs/traceability/status and relative links. Separate synthetic tests from actual provider traffic and production balance reconciliation.
