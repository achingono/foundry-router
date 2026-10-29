# Production credit correction packet

Status: Executed after independent approval. See [evidence](evidence.md) and [recovery packet](recovery-packet.md) for the approved acceptance diagnostic recovery and final outcomes.

The user authorized enabling `fs-openclaw` with CAD 200 allowance and CAD 180
remaining, and correcting the accounting discrepancies. The October 28 Bank of
Canada rate, 1.4036 CAD per USD, gives cents-floored USD 142.49 and USD 128.24.
These are local estimates, not authoritative Azure balances. Verified billing
cycle days remain unchanged: swarm 2, openclaw 26.

The verified release is ACR build `ca8`, image
`foundry-router@sha256:080491a7df64a42f8eed30d37ba0a67d218f1d3a6e6b48aee0f50c473bc6d273`.
Source hash aggregate is
`2ae231bba2264a5a31fcd287608b76a202dd23267f6a863867d786a1be721634`.
The private handoff script hash is
`081dc6e55bed3b5d3ab590890586061e1501bf07eb3e3a2ac7285a2cde25c230`;
pricing hash is
`b285d3f3808c11f3ad5cd992486f2537769f76a5c2565618227ec40790af3729`.
Private executable and prepared artifacts are `/private/tmp/router-credit-handoff.py`,
`/private/tmp/router-local-snapshot.py`, and `/private/tmp/router-credit-handoff/`.
They contain environment-specific identifiers and are excluded from repository
deliverables. The snapshot helper is hash-bound as
`6f0ccb0bcda3846d899504b1b30b6a8fa1d67039188eb20f9fc0b56e23eee1ab`.
Baseline snapshots, drained seed/snapshot seals, pinned secret bundle and promoted
configuration/process evidence are revalidated through dependent phases.
Seven mocked drift-refusal checks passed in the private guard rehearsal.
The operator has an existing vault-scoped Key Vault Administrator role; no new
assignment is required.

Independent implementation and pricing reviews passed; full verification passed
2,805 tests with 90.39% coverage, lint, formatting, types, real Azurite tests, and
native plus linux/amd64 Docker checks. See [verification](verification.md) and
[pricing review](pricing-review.md). Public ingress is enabled, original IP
restrictions are empty, and the Container Apps environment has no VNet attachment.

## Exact change and execution

1. Bind current application configuration and old revision/process identity.
   Keep memory state and maximum one replica; preserve all 17 backends, 11 model
   pools, aliases, reserve policies and cycle dates.
2. Replace ingress restrictions with deny-all. Verify public admission is denied,
   then read replica-local diagnostics until every reservation drains. Refuse a
   handoff if the old process changes. Seed each existing group from its final
   remaining estimate minus outstanding reservations, floored to six decimals;
   seed openclaw at USD 128.24. Do not refund the historical metric discrepancy.
3. Write three new version-pinned monetary configuration secrets, preserving
   authentication secrets. Use the verified existing vault-scoped operator permissions; no role grant is required.
4. Deactivate the old revision and prove its writer/replicas are absent. Promote
   the pinned image and pinned allowance, initial-balance and pricing secrets.
   No automatic replay after an ambiguous promotion, and no stale ledger rollback.
5. Verify the sole healthy revision's loaded pricing, balances, zero new debit
   counters, unchanged routing configuration and memory/one-replica invariants.
6. Replace deny-all with one allow rule for the bound executor IPv4. Verify the
   same process remains alive. Execute exactly one short non-streaming and one
   streaming Responses request, with consumed-before-dispatch acceptance slots.
   Each uses at most 128 output tokens and must show completed terminal usage.
   The public slots are never replayed. Existing router retry attempts (2) and
   two-backend failover remain bounded at four upstream attempts per call.
   Worst aggregate local estimate is USD 0.02048 (budget USD 0.021). Check exact
   canonical debit deltas and unchanged recovered-debit counters. Keep all outputs
   only in memory; persist usage/count/cost metadata. If actual cached tokens are
   zero, do not claim live validation of a nonzero cache discount.
7. Restore original ingress restrictions only after both cases pass, verify
   process identity and final configuration, capture evidence with no role grant to clean up.

Pricing ceilings are documented in [pricing amendment](pricing-amendment.md).
The packet hashes sources and prepared monetary values before every phase;
guarded phases stop on drift. Recovery requires inspection of actual Azure state
and a fresh bounded plan, rather than repeating an ambiguous inference or loading
the old initial balance into a new process.
