# Google stream completion and settlement integrity

**Planned**. The [final cancellation result](../google-final-cancellation/evidence.md)
observed complete numeric counts before terminal completion and a debit reduced to those
counts. Cancellation/transport/protocol failures must retain the original reservation cost
until the owned stream has cleanly ended and decoder completion validation succeeds.
This is a forwarding accounting change; quota input observations remain independent.

## Scope and behavior

At `GoogleAttemptSettlement.capture_stream_usage`, keep the original fallback cost for
ordinary incremental streams during prefetch, cancellation and ownership transfer. Retain
known valid input counts for quota. A signed stream already fully read, validated and marked
`prefetch_finished` may retain its complete-body usage; do not treat `validated` (first
translatable event) or available numeric dimensions as terminal proof.

In `_google_stream_response`, track clean upstream EOF and successful decoder finish
explicitly. Precise cost from both dimensions is allowed only after this proof. Cancellation,
deadline, transport/protocol failure and unstarted response cleanup retain the original
estimate. An already validated complete signed prefetch is equivalent full-body proof.
Keep settlement/cleanup idempotent, no retry/failover after output, existing deadlines and
natural credit release. Malformed usage still falls back to reservation and cannot become zero.
Do not change Azure SSE forwarding or nonstreaming complete-body accounting.

## Verification and limits

First obtain independent plan review. Add actual route cancellation with complete partial
usage followed by delayed remaining output; assert full estimate, observed input quota,
one dispatch/natural cleanup/no retry. Cover prefetch usage-only cancellation and unstarted
response, protocol/transport failure after counts, successful compatible/native stream with
terminal counts, signed complete-prefetch ownership and zero-priced models. Existing tests
that accept partial stream usage must be assessed against this completion contract.
Run focused then full tests >=80%, Ruff/format/mypy, Linux amd64 Docker build/import smoke,
contextual review, links and traceability/operations updates. Commit plan/code transitions.
Sonar scanner is absent. No new live Google calls: every retained request budget is exhausted.
Do not rewrite live failed evidence or claim the local correction clears live acceptance.
No production/deployment/scale-out or billing query.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
