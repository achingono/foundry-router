# Amendment: scoped black-box deployment acceptance

Date: 2026-10-12. Status: **Implemented locally** and independently reviewed in
[82c7d09](review-staging-harness-9a763c7.md#follow-up-review-of-82c7d09). Live
execution remains **Planned**. No staging write, production deployment or paid
dispatch is approved here; separate execution gates remain.

## Decision and rationale

Use the deployed router's public completion/usage and canonical admin debit
as **deployment acceptance** evidence for the existing six cases. This tests
the configured route, public completion and local accounting together; it does
not independently verify raw provider output, actual provider usage, provider
billing or authoritative account balances. Both observations originate from
the router, so a correlated translation/accounting error may escape this check.

The exact models already have separately recorded live nonstream evidence and
Zen has live streaming evidence. That supports a bounded deployment acceptance
check against the reviewed image/configuration rather than requiring a new raw
provider observer in the deployed app. It does not establish OpenRouter router
streaming. OpenRouter remains staging nonstreaming only and absent from production.
No direct probes, extra calls or broader provider qualification are added.

## Replacement acceptance contract

This supersedes only the independent-upstream-observation requirement in the
[activities](activities.md). All other release, auth, quiescence, price, budget,
rollback, state and approval gates remain unchanged.

1. Public responses must pass strict completion, usage, caps and streaming-frame
   checks. Canonical group debits must reconcile with that public usage at the
   exact configured prices, with precision-appropriate checks and no unresolved
   reservations. Account quiescence and stable backend/group identity throughout
   each measurement remain required.
2. Results and their manifest/fingerprint must identify the evidence scope as
   deployed public/admin acceptance. `independent_upstream_observed` remains
   false for this harness. Setting it true is neither evidence nor a promotion
   authorization. Do not rewrite historical records or infer broader verification.
3. Production eligibility requires all four staging cases to form the complete,
   strictly bound and ledger-consistent accepted sequence under this contract.
   Recompute success coherence (exact provider/deployment/mode, token caps,
   debit/flags) rather than trusting Boolean summaries. Missing results, missing
   ledger outcomes, failed/halted states and conflicting evidence block dispatch
   before any successor, including after a crash.
4. Keep the explicit production approval flag and separate operator approval of
   the exact tested release, environment bundle and maintenance procedure.
   Neither the flag nor an evidence Boolean bypasses sequence/state checks.
5. Preserve the four staging plus two Zen production cases and USD 0.01 aggregate
   configured-price allowance. No retry, new target or reset of consumed run
   identities follows from this amendment. Update and review the immutable
   manifests/evidence schema before use; do not grandfather old evidence silently.

## Implementation and review gates

- [x] Reviewer narrowing decision and residual evidence limits recorded.
- [x] SV-1 reconciliation and result-coherence gaps independently verified in
      [08221ff](review-staging-harness-9a763c7.md#follow-up-review-of-08221ff).
- [x] Harness/manifests bind this evidence scope and production gating validates
      it; no fabricated upstream flags can satisfy the gate.
- [x] Actual resume, crash, corrupted-result and scoped production-positive/
      production-negative paths covered offline with canonical manifests present.
- [x] Revised harness independently reviewed in `82c7d09`.
- [ ] All separate operator/release/maintenance gates met before execution.

The amendment and harness review gates are cleared for the committed six-case
scope. This is deployment acceptance based on public/admin evidence, not
independent provider or billing verification. Actual staging/production execution
still requires the separate plan gates and operator approvals.
