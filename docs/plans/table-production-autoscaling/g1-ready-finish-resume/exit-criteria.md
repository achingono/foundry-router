# G1 resume Exit Criteria

## Gate Checklist

- [x] Independent review approves this amendment before runner implementation.
- [x] Focused continuation tests and full repository coverage ≥80% pass; Ruff, formatting, source/operator Mypy, links, and contextual review pass.
- [ ] Fresh private packet binds the exact reconciliation artifact, current one-ready-worker Table state, original case-3 identity/reserve, and current source/test hashes.
- [ ] The packet binds accepted case 0/1 receipt hashes; apply revalidates their finish links, recomputes configured-price debits, requires each debit within its matching original slot reserve, and verifies the contiguous canonical account/counter chain before case 3 or final results.
- [x] After case-3 ownership/consumption, a fresh all-revision/process/configuration/ingress/financial snapshot matches the reconciliation immediately before HTTP dispatch; injected financial drift DENYs with no case-3 request/restart.
- [x] The bounded readiness wait occurs before the final pre-dispatch snapshot; there is no wait/remote operation between that snapshot and the single HTTP dispatch. Drift injected during readiness is caught by that final snapshot.
- [ ] Independent exact approval authorizes only case 3 once, final DENY once, quiet drain, and one restart; no new allocation or Allow.
- [x] Read-only preparation performs no original-history append. After exact approval and ownership locks, the global continuation marker is consumed before all execution-time history/slot/live checks; every later refusal/failure attempts the one final-DENY mutation. The separate DENY marker is written immediately before that PATCH. Ambiguous DENY is never retried; pre-boundary approval/lock failures do not mutate.
- [x] If writing the secondary DENY marker fails after global continuation consumption, the runner still attempts DENY once using that global guard; if 403 is observed, it stops without restart or pass results. A pre-existing DENY marker suppresses any second PATCH.
- [x] A simulated concurrent FileExistsError while consuming the DENY marker produces no second PATCH, and the consumed global resume identity prevents fresh-directory replay.
- [x] If the global resume marker cannot be confirmed durable, no case dispatch or ingress mutation occurs; any visible marker remains immutable for fresh review.
- [x] Global-marker durability confirmation is itself budget-bounded; timeout/unconfirmed durability performs no ingress/provider mutation.
- [x] A global-marker write failure after file/directory fsync confirmation attempts DENY once; a failed attempt with unconfirmed durability remains pre-boundary/non-mutating.
- [x] All operations obey a 30-minute continuation budget, 60-second case dispatch, 60-second DENY mutation, 120-second DENY propagation, 100-second quiet drain, 180-second post-drain snapshot/marker window, 180-second restart observation, and reserved cleanup headroom.
- [x] All fsync-backed consumption/result records are bounded by a 15-second remaining-budget limit inside the active phase.
- [x] Focused tests cover post-marker pre-dispatch refusal, dispatch timeout/failure, ambiguous DENY, fresh-directory replay, and pre-boundary lock/approval failure with exact no-retry/no-restart expectations.
- [ ] Actual case-3 completion/usage and exact configured-price single-group settlement are observed; both canonical groups have zero reservations and financial continuity is retained.
- [ ] Final public status is live 403; quiet drain is proved; exactly one actual current-revision restart is observed within deadline.
- [ ] Final topology is one ready approved worker, old/unapproved revisions have zero workers, persisted balances/debit/recovery counters are unchanged, and reservations remain zero.
- [ ] Original case-2 reconciliation and case-0/1/3 receipts are hash-linked into the final result; no consumed history was overwritten.
- [ ] Exact original ingress/min0 restoration remains a separate reviewed cleanup and is not claimed complete here.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | OpenCode coordinator | Implemented locally | One source/test writer; live operations remain gated |
| Reviewer | Independent session | Contextual implementation review approved | Plan and implementation reviews complete; exact private-packet review remains pending |
| Approver | Independent exact-packet reviewer | Pending | Binds one remaining original call and final fenced restart |
