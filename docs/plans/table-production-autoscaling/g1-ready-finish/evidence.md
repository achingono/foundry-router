# G1 ready finish Evidence

## Status: Planned

Plan authored2026-10-30 only under this new directory. Planner inspected local docs/source references/status and blank templates; no implementation, Azure call/mutation, paid inference, restart or runtime verification was performed.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Earlier exact D approval | [Continuation review](../g1-api-continuation/exact-packet-review.md) | Frozen continuationa2b3e… approved for API2025 promotion; not approval of this finish |
| Actual D outcome | Coordinator supplied execution report/private D summary/promotion marker | API2025 PATCH succeeded/current image deployed. Checker then failed `Inactive revision has workers` in new revision transient preactivation; no original paid slot consumed. Do not replay PATCH or D apply |
| Settled current evidence | Private ready.json SHA-256 `aa820b62968cc4c44ba8c28589e697c4cd7320faecf882de9aba0ade435e5fbc` | Coordinator reports one active ready current worker, four total revisions/three inactive old with0workers, Table/min1/max1/retry0,403 and both maps exactly old-drained/current counters explicitly0/no reservations. Planner did not query Azure or independently read private snapshot |
| Frozen provenance | [D review](../g1-api-continuation/exact-packet-review.md), [recovery review](../g1-fence-recovery/exact-packet-review.md), [original verification](../phase1-verification.md) | h701cca/recoverye3c47/continuea2b3e imports unchanged;76runtime file/image match prior evidence. Full pins require revalidation for new approval |
| Financial ownership | Original e program ledger/slots and old-drained snapshot, coordinator report | Four wholly unstarted original slots/USD0.01792, existing USD1/16 program; no new budget, refund or paid restart probe |
| Immutable history and ownership | e/a/D consumed/failure artifacts; [agent workflow](../../../development/agents.md), local git status | Earlier failures remain retained; P2/private drafts USER WORK untouched. New finish identity/global guard must be approved before mutation |
| New finish gates | [Activities](activities.md), [exit criteria](exit-criteria.md) | Independent plan/candidate/exact review, acceptance-only executor Allow/four cases/DENY/restart/results still pending |
| Plan link check | Read-only local validation of these four files | No broken relative links; documentation validation only |

Later evidence must bind the full original/recovery/D/ready/finish source and approval chain, refreshed sole-ready/config/financial baseline, original slot ownership/usage/debit results, final fence and actual restart generation plus persistent balances/counters. Append compatible G1 results with original_apply_completed:false and accurate new finish link. Report transient restart topology separately from final accepted1worker. Keep secrets/private IDs/prompts/outputs out of committed evidence. Production remains memory/one; staged isolated DENY/min1 success still requires separate exact ingress/min0 cleanup.
