# Stateless Google compatible text signatures

**Implemented** locally, independently reviewed 2026-10-08; live acceptance remains pending. See [review](plan-review.md) and [evidence](evidence.md). The operator requires OpenAI-compatible Responses. Safe exact-model
[diagnosis](../google-compatible-envelope/wrapper-result.json) identified one nonempty
`extra_content.google.thought_signature` string, with no unknown wrapper fields. Current
strict message-state rejection returned public502 despite provider200 and valid usage.

## Concrete feature-local repair

Add identity normalization hooks for generic nonstream assistant messages and stream deltas;
default hooks preserve existing strict validation. Google overrides may strip only an exact
`extra_content = {google: {thought_signature: nonempty string}}` wrapper bounded to 64 KiB
UTF-8, without control characters. Empty/null extra_content remains allowed only as inert
metadata; any unknown wrapper keys, wrong types, reasoning/media/functions or unsupported
state still reject. Never log or expose signature bytes. Do not interpret/decrypt signatures.

Enable this normalization only for ordinary stateless text with continuation disabled and no
requested function tools, inbound signed state or structured/media features. Stateless Responses
already rejects previous_response_id/store/opaque history; preserve those rules. Signatures
support reasoning continuity, which this text-only contract does not offer; stripping this
specifically validated signature is an explicit stateless-output policy, not a continuation
implementation. Document that clients replay ordinary text only and exact signed tool/continuation
round trips remain separately gated. No automatic conversion to a public extension or raw replay.

Google-specific hook checks its request context/profile before stripping; generic providers
retain unknown-state rejection. Preserve usage counts/debit, content, finish reason, SSE event
boundaries and no retry after meaningful output. Apply the same validation to final signature-only
stream deltas, including size/type abuse, without affecting empty normal deltas.

Obtain independent concrete plan review before runtime edits. Test nonstream and fragmented
stream signature envelopes, unknown/wrong/oversize/control types, requested tools/state/media
rejection, generic-provider strict behavior and immutable pre-extraction wire fixtures. Run full
>=80% quality/typing/Docker and contextual review before live verification.

## New bounded acceptance stage

After reviewed local repair, at most eight new dispatches: one nonstream/stream pair per
project2–5, exact3.5FlashLite, samebody/default-thinking/1088-token reserve and25secondcasebounds.
Retain the shared cumulative ledger and a new immutable baseline including all failed diagnostic
cases. Project1 is exhausted and never called. Project2/3 each have four requestslots,4/5five;
each pair fits retained caps. Same whole-stage lock; unique deterministic newcaseIDs; persistent
failure/ambiguity projecthalt; stream only after this stage's recorded nonstream success. No
retries, paidspend, alternative models or productionchanges. Record every outcome/debit before
nextcase. Prior failed stages/baselines/results stay unchanged. Successfulsimpletext alone does
not establish nonzero thinking, embeddings, tools, signedcontinuation or quota ceilings.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
