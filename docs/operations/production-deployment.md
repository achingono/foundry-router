# Production maintenance deployment

Status: Operator procedure and workflow guard Implemented. Each environment requires its own reviewed acceptance packet.

Automatic production dispatch exits before a build, validation or Azure login. Staging follows the existing workflow. Prepare a concrete reviewed maintenance operation before making production changes; image publication and application deployment are separate steps.

1. Freeze the exact reviewed source, image digest and intended configuration. Verify registry pull authorization and immutable image identity.
2. Capture current application shape, active revisions, ingress restrictions, identities, secret references and authoritative ledger state in private operator records. Verify readiness and zero unresolved ownership before mutation.
3. Close public ingress under a reviewed maintenance restriction, drain existing traffic and fence all writers. Preserve existing restrictions explicitly; a default empty restriction list can remove them.
4. Apply only reviewed changes. Keep authoritative Table ledgers intact and do not seed existing accounts. Verify image, state backend, references, resource shape and replica settings from current provider readback.
5. Run bounded trusted acceptance: readiness, configured provider nonstreaming/streaming behavior, reservations, usage settlement and actual targeted restart persistence. Keep budgets and real credentials in private operator configuration.
6. For optional larger intake, pass full-runtime Linux capacity and actual ingress acceptance before activation. For scale changes, pass multi-worker reservations, metrics ingestion/completeness, alert behavior and the intended scaling policy.
7. Restore the captured ingress policy only after acceptance. Record failures and exact readbacks without rewriting earlier failures as successful evidence.

Rollback must preserve authoritative Table finance and the latest confirmed ledger lifetime. Revert to an accepted compatible image/configuration and single replica while diagnosing a failed scale exercise. A stale memory revision is not a safe rollback target. A failed or uncertain mutation requires read-only reconciliation of actual state before any new write; never blindly replay consumed operations.

Do not commit environment-specific allocations, actual spend/balances, resource/account/worker identities, access URLs or private receipt inventories to a public repository. Publish generic implementation status and measured local verification only. See [release preparation](../plans/public-runtime-release/index.md).
