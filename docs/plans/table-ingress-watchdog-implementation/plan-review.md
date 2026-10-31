# Independent Implementation Plan Review

**Verdict: Conditionally approved as a plan; implementation remains blocked.**
An independent session found nine Majors in the first candidate and three more
on re-review. The final re-review found those twelve addressed as plan
requirements and no remaining Critical/Major plan finding. No source files,
Azure resources, or provider requests were changed by the reviewer.

| Finding | Plan disposition |
|---|---|
| Runner could inspect supervisor credentials | Distinct OS identities, privilege drop, protected key mount, denied ptrace/FD/memory/token access and Linux bypass tests. |
| Financial state could change after the snapshot | Prove exclusive writer, quiescent reconciliation/reaper/ownership, no rollover and no intervention through forwarding; otherwise block for design amendment. |
| Runner-controlled response was not independent evidence | Gateway signs its actual bounded upstream response witness; verifier independently checks it against the financial snapshot. |
| Session WORM retention could expire before packet/replay window | Attest locked retention of at least eight days against a maximum 30-minute packet and seven-day replay/forensics window; test conditional and denied writes. |
| DENY probes conflicted with normal lease expiry | Separate bounded diagnostic-only phase after successful close, never reopening normal forwarding, with its own scopes inside the packet deadline. |
| DENY/restart proof omitted required transitions | Require pre-DENY origin 200, durable DENY/restart/probe markers, distinct TLS 403s and zero-upstream calibrated evidence, and independently signed restart completion. |
| Four cases did not prove distinct deployments and Table mode | Bind and verify the exact two-deployment × nonstream/stream matrix, effective Table identities, scoped sole writer and production-disjoint mappings. |
| Aggregate budget and pre-dispatch input bound were insufficient | Freeze and inventory prior liabilities, sign one program-wide allocation, serialize it across hosts, and prove the exact provider input/cost bound or separately review a higher reserve within the same budget. |
| A suspended host cannot enforce socket termination in real time | Explicitly blocked pending independent design amendment or a separately specified independent data-plane enforcer; no claim of unconditional TTL closure. |
| Different sessions could consume the same allocation | Bind one session and four slots to the allocation; consume allocation-scoped WORM slot markers before session dispatch. |
| Budget-record retention might expire while liability remains | Use a separate budget WORM container with cycle/audit retention and legal hold until liabilities are independently resolved. |
| Witness did not explicitly require G1 success | Require HTTP 200, completed status, valid bounded usage and clean EOF; reject other 2xx, failed/incomplete/duplicate terminal events and malformed usage. |

The review does **not** resolve or approve the full-host-suspension design
decision. That decision and its independent review must precede implementation.
Clock, WORM, network/identity isolation, financial quiescence, diagnostic
attribution and provider-attempt properties remain unverified. Separate local
implementation review, non-paid Azure feasibility, and exact infrastructure,
budget and four-case execution packet reviews remain required.
