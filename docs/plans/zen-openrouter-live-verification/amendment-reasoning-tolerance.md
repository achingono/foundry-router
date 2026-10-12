# Amendment: null-tolerant reasoning in translated messages

Date: 2026-10-11. Status: proposed, pending independent review. No runtime
changes under this amendment yet.

## Background

Direct probes proved all three OpenRouter envelopes carry an extra `reasoning`
field on assistant messages while remaining valid (finish `stop`, text
content, coherent usage). The shared Chat translator rejects unknown message
keys, producing provider-200/public-502. See [probe evidence](evidence.md).

## Change

1. Accept the `reasoning` key on translated assistant messages and stream
   deltas **only** for Chat-translated providers (`openai_compatible`,
   `openrouter` via `CompatibleTextAdapter`), and only when its value is
   `None` or empty. Null/empty carries no semantic or cost content and is
   dropped from the translated public body, which keeps its existing
   rebuild-from-known-fields shape. Any other `reasoning` value, and any other
   unknown field, still fails closed with a sanitized 502. Google adapters keep
   their existing strict behavior unchanged.
2. Carry rejected field names in a `TranslatedRejectionError` (`ValueError`
   subclass, so every existing handler behaves identically) and emit one
   debug-level redacted log per translated rejection from forwarding,
   naming only sanitized field names — never values. Sanitization keeps names
   matching `[A-Za-z0-9_.-]{1,64}` (at most 8 per event) and substitutes a
   fixed placeholder otherwise, preventing log forgery and unbounded
   cardinality. No client-visible error text changes; provider bodies are
   still never relayed.
3. Regression coverage: null/empty/absent reasoning accepted (nonstream and
   fragmented stream) with byte-identical public output; content-bearing
   reasoning and other unknown fields still rejected; Google oracle unchanged;
   hostile field names sanitized; no secret or content bytes in logs or errors.

## Rationale

Null-tolerance unblocks the exact observed provider shape without opening the
contract: content-bearing unknowns still fail closed pending per-field review,
and the next unknown field arrives with a debug trace instead of a mystery
502. Forwarding unknown fields to clients stays out of scope, as does any
change to usage accounting (usage totals already include reasoning tokens per
provider convention; local estimates remain estimates).

## Exit criteria delta

- [ ] Independent review of this amendment and its implementation.
- [ ] Offline suites green with the new regression coverage and unchanged
      Google/generic oracles.
- [ ] Live OpenRouter reruns (new run identities) pass with usage/settlement
      evidence, or halts recorded with no further egress.
