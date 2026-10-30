# G1 ready finish independent plan review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra session, separate from the planner and executor.

## Verdict

**Approved for implementation. Unresolved Critical: 0. Unresolved Major: 0.**

The four-document plan correctly narrows the remaining G1 work to acceptance of the already-promoted current image: executor Allow, four original unused calls, final DENY/drain and one actual revision restart. Exact executable approval remains pending; this plan review grants no execution or production approval.

## Reviewed binding

| Document | SHA-256 |
| --- | --- |
| [Inputs](inputs.md) | `67641ec20ce6cbb5c076de6d9ad074ad2090d33be1368424ab8a8d1a9fe9385f` |
| [Activities](activities.md) | `3ca55ccdb7e9cb72c068a0d5f794f9822c4be8018ba8b42d87f6f240202923c8` |
| [Exit criteria](exit-criteria.md) | `1467fe958c3b127c4ef62d8d9be1d0f118441706e286096986a98e46d3104e58` |
| [Evidence](evidence.md) | `be22dd226def2e031be081a3144f7a4c215f30818385e7b3fd3e8b93262d6ff7` |

## Review findings

- New finish identity, global original-program consumption guard and original execution/program/recovery/continuation/finish locks prevent competing execution and directory-based replay. Frozen helpers are read-only imports; prior apply invocations and consumed/failure history remain immutable. Original baseline/case/restart/results writes require absence and exclusive append semantics.
- The four original USD0.00448 slots remain within USD0.01792 and the existing USD1/16-attempt program. Consume-before-dispatch, max64 reported input/max128 output, one candidate, zero retries, terminal usage/clean EOF and continuous complete account-map reconciliation preserve the financial boundary. Unknown usage retains full reserved liability and prevents later calls; it cannot become a refund or a replacement slot.
- Fresh all-revision inventory, exact current configuration/image/pins, both old-drained account maps, explicitly present current financial counters and zero reservations gate paid traffic. Successful prior promotion is not repeated. No deployment, old-worker stop, role, Table, seed, source configuration or production changes are included.
- Restart observations are distinct from acceptance. Implement the user-authorized bounded zero/multiple-worker or inactive-candidate transition only for the owned current revision, approved image and exact settings under the proved final fence. Old-version or unapproved workers always refuse. Final acceptance requires exactly one active healthy revision with one **ready** current worker, changed actual container generation/restart count and process identity, preserved account/financial counters and zero reservations. These clarify the existing restart requirement; they do not permit relaxed pre-call topology or a new deployment.
- Allow/200 and DENY/403 propagation, the100-second quiet drain, restart observation and nested command deadlines are bounded. Completion remains staged DENY/min1/max1 with separate later cleanup and honest `original_apply_completed:false` provenance. Actual four-call/persistence results and downstream reader review remain required before production uses G1 evidence.

## Checks performed and scope

Inspected local git status, all four plan files, canonical configuration/operations and agent workflow documentation, and prior recovery/continuation exact reviews. Validated the four documents' relative links and independently recomputed their hashes.

Independently read the existing private `ready.json` capture and verified SHA-256 `aa820b62968cc4c44ba8c28589e697c4cd7320faecf882de9aba0ade435e5fbc`. Its recorded public status is403, snapshot readiness is true, and inventory contains four revisions: one active approved-image revision with one worker and three inactive older revisions with zero workers. This is capture inspection, not a fresh Azure observation. Fresh execution-time financial and topology guards remain mandatory.

Only this review file was written. No runner implementation, tests, Azure request, inference, restart or source/configuration edit was performed. Local candidate checks, contextual review and exact finish approval are the next gates.
