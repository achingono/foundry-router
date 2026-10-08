# Bounded thinkingLevel text track: 3.5-flash-lite and 3.8-flash

**Planned**; prior independent review returned NOT CLEARED with conditions, all folded
in below — implementation may proceed only under them. This is a **separate, bounded
delivery track**: target `gemini-3.5-flash-lite` (`minimal`) and `gemini-3.8-flash`
(`low`); 2.5 validation is not in this track (it stays on its proven budget-0 path),
and completing the full multimodal plan is not a prerequisite. Priorities in order:
(1) exact model/configuration mapping, (2) native nonstreaming text with thinking-level
support and correct usage accounting (one live case per model), (3) streaming text on
the same profiles, (4) access/quota validation across the five projects with routing
that excludes inaccessible combinations, (5) tool calling only if the intended client
requires it. No cap change; project caps and zero-paid-spend stand with all prior
debits carried forward.

## Why a runtime change is unavoidable

`GoogleNativeAdapter` requires `native_thinking_disabled` and hardcodes
`thinkingConfig: {thinkingBudget: 0}`. Official docs make that shape wrong for all
3.x models: they accept `thinkingLevel` instead (`thinkingBudget` is at best
backwards-compatible with unexpected performance), `minimal` returns 400 on 3.7/3.8
Flash, and no 3.x Flash/Lite supports full thinking-off. There is no omission path
in the adapter. Sending the current fixed shape to 3.x would burn ledger budget on
predictable 400s, so a bounded level path is proposed instead.

## Proposal (runtime, feature-local)

- New optional profile field `native_thinking_level: Literal["minimal", "low"] | None`
  (only the two cost-efficient levels; `medium`/`high` explicitly out of scope).
  Explicit `minimal`/`low` is preferred over omitting `thinkingConfig` (which the
  `audio_output` omit precedent would allow): provider-default thinking likely exceeds
  `low`, so an explicit level gives cost determinism, not just correctness.
- Validation matrix, all fail-closed (`GoogleFeatureProfile` validator):
  1. `disabled True + budget None + level None` → budget-0 (unchanged canonical).
  2. `disabled False + level set + budget None` → level path (new).
  3. `disabled False + budget None + level None`, unsigned → reject (no shape).
  4. `budget set + unsigned + level None` → reject (dead config today; stays dead).
  5. Level with `function_tools`/any tool or `json_*`/image features → reject
     (text-only track; combinations stay closed).
  6. Level with `image_output` → impossible by construction (`image_output`
     requires `disabled`, level requires not-`disabled`; stated as proof).
  7. Level with `audio_output` → reject (`audio_output` forces
     `features == {"audio_output"}` with its own omit/disable-zero policy, untouched).
  8. Level with `continuation_policy == "sealed_native"` → reject (sealed keeps its
     own budget/thought ceilings).
  9. Unknown level strings rejected by type.
- Backend validator amendment (`config/__init__.py` native branch): accept
  `disabled is False` iff `native_thinking_level is not None and
  native_thinking_budget is None and continuation_policy != "sealed_native" and
  `{"audio_output", "image_output"} & features` is empty; else keep the existing
  reject. Level profiles are harness/live-track only: production pools must not
  include them, and `credit.py` thought-reserve (which reads `native_thinking_budget`,
  `None` on level profiles) is unchanged — any future production level pool needs
  its own credit/thought-reserve design.
- Sealed-delegate hardening (both `model_copy` sites: `GoogleSignedAdapter.__init__`
  and `google_intake.py` ordinary construction): strip `native_thinking_level` (and
  `native_thinking_budget`) to `None` in the `update`, and assert `level is None` on
  the constructed ordinary profile. `model_copy` skips validators, so base-profile
  validation alone cannot close this; without the strip a level would leak into the
  unsigned delegate, and the signed adapter's unconditional `thinkingBudget` overwrite
  would then silently clobber it (reverse mixing hazard). Unit test: a sealed profile
  copy never emits `thinkingLevel` and never emits a mixed dict.
- Adapter, single structural branch (no convention-based promise):
  `thinkingConfig = {"thinkingLevel": level} if level is not None else
  {"thinkingBudget": 0}`, with an exact-dict assertion in tests that the level shape
  contains no `thinkingBudget` key and the budget shape contains no `thinkingLevel`
  key. Otherwise the existing budget-0 shape is byte-unchanged. No other request
  field changes.
- Strict usage change (required, not optional): `translate_success(strict=True)`
  currently raises on any `thoughtsTokenCount > 0`, which the budget-0 path satisfies
  vacuously but `minimal`/`low` do not guarantee. Specify a level-pathed acceptance
  predicate: when the dispatching profile carries a level, strict mode accepts
  `thoughts` into output tokens (`output = candidates + thoughts`, dimensions still
  bound-checked exactly as today); `tools` still rejects; budget-0 strict behavior is
  unchanged. Strict-mode tests cover thought acceptance, bound violations, and the
  unchanged budget-0 reject-any-thoughts path.

## Proposal (harness)

- `GuardedTransport.__init__` takes an explicit `expected_thinking: dict` parameter;
  `isolated_settings` takes thinking disabled/level parameters; `run_text_case`
  threads the model→level binding through both. The allowlist is exactly two shapes —
  `{"thinkingBudget": 0}` (2.5 track, unchanged) and `{"thinkingLevel": "minimal" |
  "low"}` — compared by JSON equality against the decoded request body (no
  subset/superset match); any other thinking content, including right-shape
  wrong-level (e.g. `minimal` for 3.8-flash) or a mixed dict, raises before
  `ledger.reserve`, preserving the existing reserve-after-match ordering.
- Execution maps model to level from a reviewed two-row table
  (`LEVEL_BY_MODEL = {"models/gemini-3.5-flash-lite": "minimal",
  "models/gemini-3.8-flash": "low"}` with per-cell docs provenance: `minimal` valid
  on 3.5-flash-lite per the official thinking table, `Supported (Default)`
  (https://ai.google.dev/gemini-api/docs/generate-content/thinking), and the
  3.5-flash-lite stable model guidance defaulting to minimal; `low` valid on 3.8-flash
  per its model page, `Supported (low, medium, high)` with `minimal` returning an
  error (https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)); any model
  absent from the table or any level mismatch refuses with zero requests. Same
  single-dispatch, no-retry envelope with **per-project** halt-on-overrun (a halted
  project stops only itself; other projects continue); streaming rows still rejected.
- Pilot budget (explicit amendment to the 512-token reservation, not a silent
  increase): a 64-token inclusive output limit can exhaust itself in thinking and
  return no usable answer, so each pilot allows **1,024 total generated tokens**
  (`max_output_tokens`) and reserves that allowance plus a conservative 64-token
  input estimate — **1,088 reserved tokens per case** (`LEVEL_OUTPUT_TOKENS = 1024`,
  `LEVEL_INPUT_ESTIMATE = 64`, `LEVEL_RESERVED_TOKENS = 1088`). Project request/token
  caps and zero-paid-spend stand; all prior debits carry forward.
- Staged pilot gating: run one model on one project first; proceed only after
  completed non-empty text with valid known usage. A protocol-valid but empty
  `MAX_TOKENS` truncation (finish on token limit with no usable text) remains a
  **failed usability gate** even when usage settles. Live proof asserts the observed
  `thoughtsTokenCount` per level rather than assuming zero.
- Returned signatures/state decision (live-observed: 3.x text parts may carry a
  `thoughtSignature` with zero thought tokens): `_native_output` accepts parts shaped
  exactly `{"text", "thoughtSignature"}` with a non-empty string signature **only when
  the dispatching profile carries a level** (`drop_signatures` flag), extracts the
  text, and counts the drop; all other profiles keep rejecting signature state, and
  empty/non-string signatures and bare signature parts still reject everywhere.
  Dropped signatures are never persisted, replayed, forwarded, or logged; presence is
  recorded in pilot evidence and unit tests, never in client-visible fields. No history
  or tool support may be claimed from this track; the full signed-continuation
  subsystem is not required for the text pilot and stays out of scope.
- Manifest rows for the two models keep reviewer-approved statuses only; no new
  status is proposed — the existing executable status plus the reviewed table
  carries the level binding.

## Required tests and verification

- Profile validation: full matrix above, unknown level rejected, 2.5 budget-0 path
  JSON-semantically identical to before (`generationConfig.thinkingConfig ==
  {"thinkingBudget": 0}`, no `thinkingLevel` key) — JSON-semantic, not byte
  identity, since the guard compares decoded bodies.
- Adapter units: exact upstream body per level; sealed-copy clobber test; strict-mode
  thought acceptance/bound tests; rejection paths unchanged.
- Harness: per-shape accept plus cross-shape reject (budget vs minimal vs low vs
  mixed vs absent) with `dispatched is False` and no ledger mutation on reject;
  offline execute tests with mocked CLI/provider covering level mapping, refusal of
  unmapped models, and leave-no-state failures (mirroring the existing execute-path
  suite).
- Full suite ≥ 80%, Ruff/format/mypy/Docker, deep review, docs and link/secret
  review before any live dispatch under the new shape.

## Confinement

The first implementation lives in the isolated validation runtime only: level profiles
are constructed by the live harness's init-only settings, and no ordinary application
configuration may include them. Ordinary application enablement is a separate decision
gated on this track's accounting proof (thought-inclusive usage settlement) and live
proof (completed text plus valid usage per model). Backend validation accepts level
profiles so the isolated harness can build real settings; that acceptance must not be
read as application enablement.

## Explicitly out of scope

`medium`/`high` levels, streaming, tools, sealed interplay, Pro (thinking-enabled
contract stays separate), cap or status-semantics changes, production changes.
