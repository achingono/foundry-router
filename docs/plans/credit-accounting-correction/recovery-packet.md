# Acceptance diagnostic recovery and ingress restoration

Status: Executed after [independent approval](recovery-review.md). Ingress restored; see [final evidence](evidence.md). No inference replay or ledger reset.

The original non-streaming acceptance passed with 10 input tokens, 5 output
tokens, zero cached tokens and USD 0.000125 debit. The stream completed the
terminal/usage validation in `execute()` but its following snapshot failed with
an Azure diagnostic WebSocket HTTP 429 (Retry-After 600). The consumed stream
slot remains consumed; its exact token receipt was not persisted and cannot be
reconstructed from metrics. A read-only diagnostic retry already launched before
the error detail was inspected succeeded, proving unchanged PID1/revision/replica.
No further diagnostic attempt was made inside the retry window. Public diagnostic
reads corroborated exactly two successful requests, USD 0.000250 request cost and
the same canonical debit, zero recovery and quiet accounts.

The private recovery script `/private/tmp/router-credit-recovery.py` SHA-256 is
`2415b6c3969f45c8ef4256906f62951216cb9e671d4412fb43af17e413c22e0e`.
It reuses the approved handoff guard definitions and checked helper/source pins.
Four mocked process/cost/request/balance drift refusals passed.

After the reported retry window expires, the restore mode obtains a fresh local
snapshot under exact executor-only restrictions and expected full promoted
configuration. It verifies process continuity, sole healthy active revision,
zero baseline requests, exactly two successful sol requests on the expected
backend, request-cost to credit-group mapping, exact balance reductions and
canonical debit totals, and zero recovered debits. It saves a separate recovered
settlement receipt documenting the unavailable exact stream token receipt;
the original consumed slot is not changed to passed. Only then does it restore
the original ingress restrictions, verify unchanged configuration and local
process identity, and save final evidence. No image/configuration/credit seed
change or provider dispatch is performed. An ambiguous restore is inspected;
the script is not replayed automatically.

Acceptance claim: non-streaming terminal and exact usage/debit validated;
streaming terminal/usage validation reached and settlement independently
reconciled, with exact stream usage receipt unavailable. A live nonzero cache
discount is unverified. These limitations remain explicit in final evidence.

The restoration PUT was accepted; an immediate readback was stale while Azure
reported InProgress. Read-only finalization polled completion and verified the
original rules, expected fingerprint, same process and pricing. No second PUT
was issued.
