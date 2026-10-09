# Google compatible envelope diagnosis

**Planned**, independently reviewed 2026-10-08; see [review](plan-review.md). Five [compatible attempts](../google-compatible-text-verification/evidence.md)
returned provider 200 with valid usage but public 502. Their response schema was not retained;
do not infer the exact cause. Project-1 reached the retained 20-request limit.

## Bounded diagnosis

User supplied the existing free-tier key secret and authorized available budget. Reuse the
same cumulative ledger and exact-compatible single POST contract. At most one diagnostic
nonstream dispatch on project-2 (1,088 reserved tokens; max completion 1,024; 25-second total
deadline; no retries), followed only after independent diagnosis/fix review and local checks
by a distinct bounded verification stage on projects 2–5. Preserve original failed cases and
stage halts; no project-1 calls, ledger resets, alternate models, tools or media.

Before the one diagnostic call, add a safe in-memory schema observer to the existing guard.
Observe only bounded nonstream JSON from the exact authorized guard, never headers or
raw error content. Types use a fixed enum (null/bool/int/float/string/list/object/other);
counts are capped at 128 and schema result keys come only from the explicit allowlist.
Capture only presence/type booleans for standard top-level/choice/message fields, counts,
and a bounded allowlisted classification of unexpected message fields. Never retain arbitrary
provider key names or values. Explicit allowlist may include `annotations`, `reasoning_content`,
`reasoning`, `audio`, `images`, `function_call`, `tool_calls`, `refusal` and `extra_content`;
other keys become a count. For each allowlisted field record only type and null/empty flags.
Do not record content, reasoning, nested provider state, raw IDs/errors or full response bodies.
All normal numeric usage/redacted result bounds remain in force.

Synthetic tests must verify redaction with secret-like arbitrary keys and values before live
diagnosis. Append the diagnostic deterministic case to a new immutable retained baseline,
allow only explicit phase-owned case IDs and hold the same cross-phase whole-run lock
used by the original compatible stage. Preserve its original baseline and failed results;
the new envelope baseline is a separate immutable snapshot. Persist the safe result
atomically and treat any ledgered-but-unrecorded diagnostic as consumed/ambiguous, never retry.

## Feature-local repair contract

After exact structural evidence, propose the smallest Google-owned adapter hook for any
documented inert field causing rejection. Generic providers retain strict unknown-field
rejection. Do not drop nonempty reasoning/tool/media/state under a text-only contract;
only explicitly allowlisted inert/null metadata may be normalized, with tests for empty vs
nonempty, type abuse, resource bounds and original immutable characterization fixtures.
If evidence requires broader output semantics, stop that dependent repair and retain its gate.
Obtain independent review of the concrete evidenced repair before runtime edits.

Focused/full quality checks, >=80% coverage, typing, Docker and contextual review precede
any follow-up live acceptance. Record exact scope/results; no production change or authority
claim for synthetic debits. Compatibility streaming remains gated on new-stage nonstream success.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
