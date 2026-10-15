# Gemini streaming Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Streaming diagnostic consumes paid allocation without establishing cause | Wasted spend, remaining reduced | Single dispatch, conservative bound, stopped-snapshot binding, halt on ambiguity | Open |
| R2 | Over-broad envelope relaxation accepts untrusted provider state | Safety/credit risk | Allowlist-only correction, reject unknowns, regression tests for invalid shapes | Open |
| R3 | Concurrent staging/production wallet duplication | Double-spend estimate | Isolated staging only; production has fixed 9.90 seed, no transfer/replenish; verify stopped writer | Open |
| R4 | Operator drain in progress interfered with by diagnostic | Production continuity risk | No prod mutation, no ingress change, no old-writer handling in this plan | Open |
| R5 | Assuming nonstream cause (modelStatus/createTime) explains streaming | False fix, repeat 502 | Require chunk-index-specific proof before code change | Open |
| R6 | Flash pass mistaken for both-model qualification | Argon stream failure in production | Mandatory nine-case staging and production, including both Gemini streams; no Flash-only exit | Open |
| R7 | Harness and deployed policy disagree | Rejected streams or unbound acceptance | New recognized identity, both policies enabled, immutable config fingerprints and pre-egress mismatch tests | Open |
| R8 | Crash/relaunch duplicates diagnostic or refunds spend | Unrecorded spend/account duplication | Exclusive durable consumption before egress, permanent debit, immutable result/identity and offline crash/replay tests | Open |
| R9 | Diagnostic leaves insufficient staging budget | Cannot complete bounded qualification | Independently verify R-D, reserve and aggregate case budget before dispatch; no automatic top-up or production borrowing | Open |

## Open Decisions
- Known funding blocker: nine cases' output allowances alone total 0.04608 USD; adding the 0.05 USD reserve requires at least 0.09608 USD before input reservations or diagnostic debit. ca6 began with only 0.088 USD and has since spent funds. The [allocation amendment](allocation-amendment.md) authorizes fresh R=0.104 (D=0.004, S=0.10) with production unchanged, pending independent review; no live spend until reviewed. See [re-review](plan-rereview.md).
- Actual R, conservative D and later S must be fixed from ca6 artifacts and reviewed arithmetic before their respective live gates. Missing inputs block dispatch; they are not implicit approval.
- A separate Argon diagnostic is not authorized by this plan. If Argon acceptance fails, stop and seek a reviewed amendment. Argon streaming acceptance itself is mandatory.
- The updated production packet must reconcile the actual operator-owned drain state. Do not substitute stale seeds if required continuity/final-snapshot evidence is unavailable.
