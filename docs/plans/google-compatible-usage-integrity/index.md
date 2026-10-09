# Google compatible aggregate usage integrity

**Planned**. Same-wire 3.8 diagnostic records Google prompt7/completion2/total71 with
no reasoning detail. Router returns completed text but settles9. Aggregate total may include
unattributed provider tokens; do not invent reasoning counts or present estimates as billing.
Historical diagnostic outcomes stay immutable. No replay or production change.

Feature-local Google usage normalization: when valid nonnegative prompt/completion/total
are present, require total>=prompt+completion and set accounting/public output_tokens to
total-prompt, preserving provider text and aggregate total. This is conservative attribution
of otherwise unsplit usage to output, not proof of reasoning. Missing completion remains
incomplete (no synthesized known output). Reject bool/noninteger/negative/totalbelowpartial;
without total retain validated explicit split. Embeddings and generic compatible providers
remain unchanged. Apply the same helper to Google nonstream translation, extract_usage
and streaming absorb_usage; shallow-copy usage/upstream, no input mutation.
Every streaming usage snapshot replaces its known dimensions coherently; a later incomplete
frame clears known output rather than mixing old completion with new prompt/total. Missing
final complete usage retains conservative full reservation. Reject decreasing/conflicting
complete snapshots; duplicate equal snapshots are permitted. Tests complete-then-partial,
partial-then-complete and conflicting snapshots before/after output. Optional details
must not invent reasoning counts. Preserve existing signature/tool/media gates.

Tests: actual Responsesroute nonstream/stream71total settlement.071 and public7/64;
partial/missing/bool/negative/inconsistenttotals, incomplete streams keepfullreserve,
explicit splits and generic unchanged. Full>=80%, lint/format/types, Docker, independent
contextual review/docs before furtherlive. Verifier Google-only effective usage must match
same correction while preserving raw aggregate evidence; legacy3.5 defaults unchanged.

After implementation, supplemental live runner only previously unattempted project1stream
and projects2–5 native/nonstream/conditionalstream. Original p1nonstreamslot remains consumed
and failed; distinct successful local corrections do not reclassify it. Combined old3physical
plus new<=39 and lastp1nonstreamallowance1 unused <=45. All ledgers pinned, slot<=3,
no replay, retriesbounded2/4+RetryAftermax30,all429withheld,no retryafterstreambytes.
Independent runnerreview first. Runtimefix does not promiseprovideravailability.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
