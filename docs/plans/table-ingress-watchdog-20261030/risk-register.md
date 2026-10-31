# Isolated Ingress Watchdog Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Periodic ARM watchdog is delayed or ARM is unavailable | Stale ingress policy could remain active | Private ACA origin is reachable only through gateway; local lease expiry blocks forwarding, independent of ARM | Addressed in design; network proof open |
| R2 | ACA origin has an internal path bypassing public IP restrictions | Requests bypass gateway lease | Require a dedicated internal ACA environment/VNet with only the gateway routable; shared environments are disallowed | Open blocker until dedicated network evidence |
| R3 | Old arm credential is replayed after restart because session state was memory-only | Reopens forwarding during an unexpired credential window | Durably consume unique session ID in locked-WORM blob before arm; immutable absolute deadline; no re-arm after restart | Addressed in design; implementation/test open |
| R4 | Runner crashes after dispatch but before recording completion | Provider charge/result is ambiguous | Consume slot before request; retain full liability; no retry/refund; reconcile separately | Mitigated by G1 protocol; test open |
| R5 | Stream cancellation fails to stop upstream work | Work/charge continues after runner dies | Terminate proxy connection; treat upstream work as uncertain; no claim that cancellation reverses provider execution | Open |
| R6 | Lease is renewed after runner death by a surviving helper/thread or delayed packet | Gateway remains open beyond the bound | One-shot supervisor verifies exact child; authenticated check timestamp and one-use challenge cap expiry independently of arrival; uncertain clocks refuse renewal | Addressed in design; clock and fault tests open |
| R7 | Gateway VM/private route failure | Acceptance unavailable or unexpected route | Dedicated VNet/internal ACA environment, constrained ingress/egress, route verification after restart; fail closed and block acceptance | Open |
| R8 | Gateway compromised or target allowlist weakened | Arbitrary access or ingress bypass | Minimal fixed-origin proxy, no ARM credentials, pinned config, independent review, OS hardening | Open |
| R9 | Runner gets a network error/403 from a boundary other than ACA, or the app itself emits the same 403 | Incorrect G1 pass | Probe private ACA origin; require calibrated ACA HTTP diagnostic evidence, request-ID correlation, zero upstream attempts, no matching app request, and fresh ARM ingress GET | Addressed in design; diagnostic calibration and runner change/test open |
| R10 | Proposed VM cost/operations exceed value of isolated test | Unnecessary infrastructure | Compare managed alternatives only if equivalent local lease and no-bypass behavior can be proven | Open |
| R11 | Runner has valid app API key and makes extra paid requests during lease | Extra provider spend and slot-policy violation | Independent runner authentication plus four ordered durable one-shot POSTs, exact body binding and independently signed progression | Addressed in amended design; implementation/test open |
| R12 | Runner supplies a forged or altered “approved” packet | Unauthorized origin, duration, or request scope | Gateway verifies detached signature over canonical exact packet using independently provisioned reviewer public key | Addressed in amended design; signing workflow open |
| R13 | Runner or another workload gains a direct private route to ACA | Bypasses gateway lease and one-shot dispatch | Dedicated isolated VNet with no peering/other clients; verify effective network route and deny tests before acceptance | Open blocker until network evidence |
| R14 | ACA diagnostic logs cannot distinguish ingress rejection from app-generated 403 | False final-DENY proof | Calibrate response-code details and upstream-attempt evidence against a disposable non-paid app; if ambiguous or unavailable, block acceptance | Open feasibility gate |
| R15 | Runner uses exec, secret access, cloud privileges or direct provider egress to bypass the gateway | Unbounded or unobserved dispatch | Separate trusted operator and financial verifier from runner; deny runner exec/secret/write/provider access and independently test effective permissions and evidence path | Open feasibility gate |
| R16 | Slow ledger insert completes after lease expiry or close | A late provider dispatch occurs despite the fence | Serialize a final lease/phase recheck with nonblocking forwarding initiation; consume and halt on late completion; fault-test the race | Design mitigation; implementation/test open |
| R17 | Router retries or fails over after one gateway POST | More provider attempts than approved | Pin and verify effective zero-retry/no-failover behavior and fault-test each case; reject config or topology drift | Open feasibility gate |
| R18 | One final-DENY probe is reused for the post-restart check | Restart accepted without post-restart ingress proof | Distinct one-use pre- and post-restart probes, each with calibrated ACA diagnostics and fresh ARM corroboration | Design mitigation; implementation/test open |
| R19 | Fresh four cases are funded by reusing old slot/receipts or exceeding aggregate liability | Duplicate allocation or invalid G1 result | New packet and explicit budget, account for old attempts/liability, four ordered case records and independent settlement evidence | Open approval gate |
| R20 | Financial or process state drifts after a settlement receipt and before the next case | Paid request starts against an unverified account state | Independent fresh sole-writer baseline and immediate pre-dispatch snapshot after slot consumption; signed fresh evidence and no intervening remote operation or wait | Design mitigation; implementation/test open |

## Open Decisions

- Is a dedicated VM, internal ACA environment/VNet, and ongoing patch/monitor ownership acceptable?
- What maximum open-lease window is acceptable for this bounded isolated test?
- Must closure terminate existing proxied streams, or is blocking new requests sufficient? The recommended design terminates streams but still treats provider dispatch as uncertain.
- Can the required new dedicated environment and independently operated diagnostic path be provisioned without exposing runner exec or secrets?
- Which trusted UTC source and rollback tolerance will enforce the absolute deadline across process restarts?
- Which signing format/key custody and reviewer identity process will produce the machine-verifiable exact-packet approval?
- Can ACA HTTP diagnostic evidence distinguish an ingress-policy denial from an app-generated 403 with sufficient correlation and completeness?
