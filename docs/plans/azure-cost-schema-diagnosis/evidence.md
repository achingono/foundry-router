# Schema diagnosis Evidence

Prior fixed diagnostic recorded provider-boundary schema rejection after 4.101 seconds; no
accepted ceilings or applied balances. No new billing calls yet.

The verifier-only stream observer forwards each received response once and closes underlying
responses on completion/rejection/cancellation. Exact request resource filters bind group labels,
including groups sharing a scope; per-group page counters and strict safe schema bound evidence.
The existing provider's USD/resource/complete-row acceptance is unchanged. Final observations
join the sole atomic result write under the immutable invocation lock. Sixteen schema/diagnostic
tests passed; Ruff lint/format and strict mypy passed. Independent contextual review cleared
Critical/Major findings after fixing shared-scope attribution and atomic final persistence.
Full verification: 1,876 passed, 3 skipped, 18 deselected; coverage 89.73%. Runtime is unchanged,
so no Docker rebuild is applicable. SonarQube script is absent.

## Single live diagnosis, 2026-10-08

Committed observer `193a65d` ran once. Safe results (local-only `diagnostic-results.json`) record
provider schema rejection after 3.749 seconds. Group `fs-openclaw`, page 1, returned successful
HTTP category, valid JSON/properties, three valid required columns, one consistently sized
row, matching resource membership, no negative/invalid amount, no unknown/duplicate columns,
and **non_USD** currency. That currency contradicts the configured USD-only acceptance
contract and explains rejection for this observed page. No billing amount, actual currency
identifier, resource ID or raw response is retained. Group fs-swarm was not queried after the
failure, so its currency and billing acceptance remain unknown.

Started marker (local-only `diagnostic-started.json`) consumes this invocation; no replay or extra probes.
No ceiling was accepted or balance applied. A currency policy requires explicit operator
inputs and independent review before any conversion; never treat non-USD amounts as USD.
Production remains memory/one and the prepared isolated Table deployment remains unapproved.
