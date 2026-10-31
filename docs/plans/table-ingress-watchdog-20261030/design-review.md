# Independent Watchdog Design Review

**Verdict: Approved as design requirements only.** An independent session reviewed
the design, returned seven Major findings, then found one further Major on the
first re-review. Its final re-review found all eight addressed and no new
Critical or Major issue. The reviewer did not author the design or perform Azure
operations. The review verdict alone does not authorize implementation,
deployment, paid calls, the old case-3 slot, or production changes. The operator
subsequently approved all stages in principle; exact packet gates remain open.

| Finding | Disposition in the amended design |
|---|---|
| Fresh G1 requires four cases, not the old remaining slot | New dedicated app and four ordered cases; old results and liability stay separate; fresh budget must fit applicable aggregate limits or receive a separately approved amendment. |
| A gateway POST can cause router retries or failover | Pin and verify zero retries and no multiple-attempt failover; configuration drift or failed fault tests block dispatch. |
| Existing runner's control-plane and secret access can bypass the gateway | Separate trusted operator and verifier; deny runner/supervisor exec, secrets, infrastructure mutation and direct provider access; prove the diagnostic path and effective permissions. |
| Delayed renewal could extend access after runner death | Use single-use challenges and an authenticated pre-liveness-check timestamp; cap expiry by that timestamp, TTL, clock uncertainty and the absolute deadline, not receipt time. |
| Ledger insertion could finish after closure or expiry | Consume before dispatch, then serialize the final lease/phase/slot check with nonblocking forwarding initiation; late insertion sends no bytes and consumes the slot. |
| One DENY probe cannot prove both sides of restart | Separate one-use pre- and post-restart gateway-origin probes, each with calibrated diagnostics and fresh ARM corroboration; never reopen normal forwarding. |
| Shared-environment fallback was inconsistent with mandatory isolation | Require a new dedicated internal ACA environment/VNet; the old shared app is ineligible regardless of bypass-test results. |
| Financial state could drift after a prior receipt | Verify a fresh sole-writer baseline and snapshot immediately before each case, after consuming the slot; sign bounded evidence and initiate forwarding without another remote operation or wait. |

The review explicitly leaves network isolation, sole-writer enforcement,
operator/diagnostic separation, clock bounds, WORM behavior, provider attempt
limits, DENY-log attribution and budget approval unverified. A hung but live
runner may renew until its signed absolute deadline. Future implementation
review must test receipt freshness and ordering, delayed renewals, and closure
races. Missing or ambiguous feasibility evidence blocks acceptance.
