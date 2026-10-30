# G1 resume Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Case 2 was consumed and returned a completed response before the first runner failed to capture its post-case snapshot. | Duplicate charge or fabricated settlement if replayed/assumed. | Never replay; preserve response artifacts and require exact same-process canonical balance/counter reconciliation before case 3. | Reconciled read-only; independent continuation review pending |
| R2 | Executor-only ingress remains Allow after the stopped runner. | The approved executor address can still reach the test app; public readiness returns 200 there. | Retain only the already-approved `/32`; continuation contains no Allow path and must issue exactly one final DENY on every outcome after its execution gate. | Open until DENY is observed |
| R3 | Final ingress mutation or restart may fail or be acknowledged ambiguously. | Test app may remain reachable or worker persistence may be unproven. | The continuation-global marker precedes live preflight; the sole DENY marker precedes its write and is attempted on every post-consumption outcome. Never retry an ambiguous DENY/restart; preserve current state and request fresh review. | Open |
| R4 | A second writer or stale process could change the financial map between reconciliation and case 3. | Incorrect debit attribution or unsafe dispatch. | Reacquire original locks, verify one current worker/process, config/pins, exact all-revision inventory, and same canonical maps immediately before dispatch. | Open |

## Open Decisions

- None proposed. Any new budget, ingress Allow, slot substitution, or provider target requires a separate user decision and independent review.
