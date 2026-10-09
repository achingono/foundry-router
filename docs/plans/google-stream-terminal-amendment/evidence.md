# Terminal amendment Evidence

Synthetic local reproduction: one complete usage object attached to final stop choice plus
[DONE] and EOF gives stop=true,done=true,eof=true,invalid=false,max_tokens9,terminalfalse,
usage-only-final=false under current verifier. This proves a verifier acceptance gap, not
the raw shape of historical live frames. No further Google calls dispatched in this phase.

Strict stop-attached final usage, bounded terminal metadata and final-stage prerequisite
implemented. Root73focusedtests pass, including actual localhost route translation, metadata
persistence, withholding/replay and historical result preservation. Independent contextual
review cleared no Critical/Major findings; see [review](implementation-review.md).
Final full suite:2,019passed,3skipped,18deselected,89.75%coverage. Ruff lint/format and mypy
(70 runtime source files), links/diff pass. Verifier-only code needs no Docker rebuild;
Sonar scanner script absent. [New baseline](ledger-baseline.json) captures unchanged
current cumulative ledger; no new allowance. No live requests dispatched in implementation.

## Bounded live outcomes

[Results](results.json) retain three reasoning streams on projects3–5, all provider/public
HTTP200 with public completed events, matching input/output usage and natural upstream
closure/zero reservations. Public text preceded observed upstream EOF in all three.
Observed totals98/75/90 tokens sum263; synthetic debits .098/.075/.090 USD match those
counts numerically. No overrun occurred; nonzero reasoning metadata remains absent.

All three failed the strict verifier terminal gate: done_seen=true,upstream_eof=true,
stop_seen=false,final_usage_shape=absent. Here stop_seen specifically means a choice
qualifying under the verifier's exact inert index-zero stop predicate, not absence of a
provider finish_reason=stop field. The runtime adapter produced public completed events;
no raw choices/deltas were retained. Do not infer which unknown/inert field or shape
prevented qualification. The conservative-fallback expected-debit check consequently fails
while observed usage debits remain recorded. These flags do not establish provider billing
or runtime settlement failure. Keep results immutable.

The prerequisite withheld project2 cancellation after all new normal terminal gates failed.
Project2 retains one cumulative slot; projects1/3/4/5 have none. No budget reset or cancellation
live claim. Three nonrefundable1,088-token reservations remain in the authoritative ledger.
No further normal retry should consume the last cancellation slot without a new scoped plan.
Production remains memory/one; deployment approval and other roadmap gates remain pending.
