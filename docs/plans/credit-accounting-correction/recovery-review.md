# Independent recovery review

**Verdict: Approved for the exact bounded recovery/restore packet.** No Critical or Major findings.

Reviewer: independent `credit_plan_review` / `gpt-6-astra` session, which authored neither recovery script nor packet. Reviewed [recovery packet](recovery-packet.md), private recovery script, approved handoff guard definitions, preserved acceptance slots, promoted snapshot and recovered local snapshot. No production mutation or inference performed by this reviewer.

Reviewed SHA-256:

- Recovery script: `2415b6c3969f45c8ef4256906f62951216cb9e671d4412fb43af17e413c22e0e`.
- Packet: `be72d84359b149fdd1db2927cc38752485c09b4e475ba8f0a3305985781b93ed`.
- Preserved recovery snapshot file: `e2d5f5734e4db00df339201636fabe1b41b51a4d4f17fd94847a912c9be6b40a`, captured at 2026-10-29 15:29:46 UTC.

Independently executed `rehearse`: all four process/cost/request/balance drift refusals passed. The real saved snapshot matches promoted revision, replica and PID1 start ticks; reconciliation found exactly two successful requests on the expected model/backend, USD0.000250 request cost and corresponding account debit/balance reduction, with zero recovered debit. This is evidence from supplied live snapshots, not an independently executed Azure query.

The restore path requires a fresh replica-local snapshot, exact executor ingress restrictions, the sealed promoted configuration, unchanged process, quiet accounts and a sole healthy active revision. It reconciles request costs to the backend's credit group and each group's canonical debit and balance before reopening ingress. It preserves the consumed streaming slot and records a separate settlement recovery receipt rather than fabricating exact stream tokens. After restoration it checks original restrictions, configuration and process continuity. No provider request, image change, secret write or ledger reset is included.

The unavailable streaming token receipt remains an acceptance limitation. The script's failure location, as reported by the coordinator, establishes that terminal/usage validation returned before diagnostic failure; the preserved metrics independently support successful request and settlement, but cannot reconstruct input/output/cache counts. Do not claim a live nonzero cache discount.

Execution conditions: respect the reported 600-second Retry-After window, execute the exact pinned script once after it expires, and stop on any failed guard. Inspect actual state following an ambiguous restoration; no automatic replay is approved. Final ingress restoration and fresh process evidence are pending execution. Existing implementation verification remains applicable; SonarQube script is absent and was not reported as a successful scan. No additional unavailable code-review gate blocks this narrow recovery.
