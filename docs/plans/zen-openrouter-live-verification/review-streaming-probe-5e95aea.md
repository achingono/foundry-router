# Independent streaming-probe review of 5e95aea

Date: 2026-10-11.
Reviewed commit: `5e95aea8560a9a334238a9e35d63ed8b8a96d4e0`.

Scope: all four changed files, the streaming amendment, the existing direct-probe
state lifecycle, request construction against the router translation contract,
SSE classification/bounds, result validation and CLI output. The reviewing
assistant independently examined the completed implementation in this session.
Only review/status documentation was edited.

## Disposition

**Independent amendment review gate cleared after review of `0addac3`.**
SP-1, SP-2 and SP-3 are closed by the [follow-up review](#follow-up-review-of-0addac3)
below. No Critical or additional Major findings were identified. Clearance
applies to the existing three streaming probe IDs, with their normal durable
state, credential and bounds gates. Historical probe outcomes and halted router
runs remain preserved; deleting or recreating state is not authorized.

The findings below describe the initial `5e95aea` review; their original open
statuses are superseded by the follow-up disposition.

## Findings

### SP-1 — Major: Preserve compatibility with existing nonstream probe results

- **File/Module:** [Probe result validation](../../../scripts/quality/openrouter_direct_probe.py),
  `RESULT_KEYS`, `validate_probe_result` (lines 261–287) and `load_probe_results`.
- **The Issue:** This commit adds mandatory `kind` to every result while extending
  the same canonical results file. Previously committed nonstream probe code
  writes results without that field. The exact-key check rejects those existing
  outcomes before any new streaming probe can start. There is no legacy-schema
  reader or migration path.
- **Why Static Analysis Missed It:** Both versions are internally consistent;
  current tests create and reload state using only the new version.
- **Impact:** The amendment cannot execute from its intended prerequisite state:
  the three already-completed direct probes. It refuses safely, but blocks all
  new diagnosis. Clearing that state would lose the prior no-replay budget.
- **Recommended Fix:** Add narrowly scoped, validated compatibility for the
  exact historical schema and original three nonstream IDs, inferring their
  nonstream kind, or provide an explicit safe schema migration. Preserve all
  historical reservations/outcomes and the initialization identity; retain
  rejection of unknown keys, corrupt state and unresolved reservations. Bind
  kind to probe identity. Test old-state resume dispatching only the three new
  stream IDs and then dispatching nothing on another invocation.
- **Evidence:** Generated three completed outcomes in a temporary directory with
  the actual parent-commit implementation and fake transports. Running the new
  executor against them raised `Invalid probe result` before even creating a
  transport. The synthetic historical results bytes remained unchanged.
- **Disposition:** Open; blocking.

### SP-2 — Major: Distinguish actual SSE termination from content and parse errors

- **File/Module:** [Stream classifier](../../../scripts/quality/openrouter_direct_probe.py),
  `_stream_event_payload` (lines 417–433) and `classify_stream_frame`
  (lines 467–472).
- **The Issue:** `done_seen` is set by a substring search over the whole frame,
  including JSON content and comments, rather than an actual `[DONE]` data event.
  The payload helper also returns the same `None` for malformed data and harmless
  keepalives; the caller leaves `metadata_valid` true for both. A malformed or
  unterminated provider stream can therefore look like clean structural evidence.
- **Why Static Analysis Missed It:** The decoding and boolean operations are
  valid Python. Their meaning depends on the SSE protocol and this amendment's
  diagnostic decision, which ordinary type/lint checks cannot establish.
- **Impact:** The one-shot diagnosis can incorrectly point to terminator/usage
  handling instead of incomplete or invalid provider data. A consumed probe
  cannot be replayed to recover trustworthy evidence without another amendment.
- **Recommended Fix:** Parse SSE data explicitly, recognize `[DONE]` only as the
  complete data payload, and distinguish keepalives from malformed/unsupported
  data events. Record invalid metadata or a bounded parse-error category without
  retaining data values. Test a marker inside content/comments, malformed JSON,
  invalid UTF-8, legitimate terminators and fragmented/mixed-ending frames.
- **Evidence:** A complete JSON event with content containing the literal marker
  and no terminator returned `done_seen=true`, `metadata_valid=true`,
  `truncated=false`. A malformed JSON data frame followed by a real terminator
  returned `event_count=0`, `done_seen=true`, `metadata_valid=true`,
  `truncated=false`, with no error category. Both used fake transports.
- **Disposition:** Open; blocking.

### SP-3 — Major: Apply the frame bound after separating complete events

- **File/Module:** [Streaming read loop](../../../scripts/quality/openrouter_direct_probe.py),
  `run_stream_probe` (lines 737–750).
- **The Issue:** The loop applies `MAX_FRAME_BYTES` to the entire pending buffer
  immediately after appending a transport chunk, before splitting complete SSE
  frames. That buffer can contain several individually valid frames. The
  earliest-boundary splitter is correct, but cannot run before this rejection.
- **Why Static Analysis Missed It:** Every allocation and comparison is bounded;
  the error is confusing arbitrary transport chunk boundaries with SSE event
  boundaries. Existing tests cover oversized data, not equivalent chunkings.
- **Impact:** A valid response consumes its reserved probe and loses structural
  evidence solely because HTTPX delivered more frames together. Smaller chunks
  of the identical response succeed, undermining the intended diagnosis.
- **Recommended Fix:** Keep the total-byte check, extract and bound individual
  complete frames, then bound only the residual incomplete frame. Alternatively
  feed bounded slices into the framer while preserving those semantics. Add
  equivalent coalesced/fragmented and mixed-line-ending cases, plus a genuinely
  oversized incomplete frame that still terminates reading early.
- **Evidence:** A 280,274-byte synthetic stream containing four 70,065-byte JSON
  frames and a terminator stayed below both the 1 MiB total and 256 KiB per-frame
  caps. One coalesced chunk returned `response_bound_exceeded`; 4,096-byte chunks
  returned no error and four classified events. Both responses were closed.
- **Disposition:** Open; blocking.

## Verified behavior and limits

- The fixed streaming body adds `stream: true` and
  `stream_options: {include_usage: true}` to the same model/message/output-cap
  body used by the router. Model selection, endpoint and output budget remain
  fixed in the canonical execution path.
- New stream slots use the existing stage lock, durable reservation before
  dispatch, initialization identity and atomic writes. No-replay checks pass
  for state created by the new version; SP-1 concerns cross-version state.
- Content/reasoning string values are reduced to byte counts, finish reasons
  use allowlisted enums or an unexpected flag, and stream summaries undergo
  schema/serialized-size validation. The findings above concern evidence
  correctness and prerequisite compatibility, not an observed credential leak.
- 33 direct-probe tests passed. Another 140 budget/runtime/stage,
  reasoning-tolerance and Zen/OpenRouter integration tests passed, for 173 total.
- Independent temporary-directory/fake-transport reproductions confirmed all
  three findings. No live request was sent; no actual historical results,
  credentials or halted ledgers were read or modified.
- The repository deep-review prompt was applied to this scope. The conditional
  SonarQube script is absent. Full-suite coverage, Ruff/mypy and Docker were not
  rerun by this reviewer; user-reported checks are not independent review runs.
- Plan relative links, whitespace and the final documentation diff were checked.
  Runtime code and tests were not changed. Billing, quota/admission, Table and
  production gates remain unchanged.

## Follow-up review of 0addac3

Date: 2026-10-11.
Reviewed commit: `0addac3598c121aa5177805a0ce169780ed19ba6`.
Scope: both changed files, the three original reproductions, historical-state
compatibility, SSE parsing and frame bounds. Only review/status documentation
was changed by the reviewer.

**SP-1 — Closed.** `_with_legacy_kind` makes a validation-only copy for precisely
the original three nonstream IDs. The copy still undergoes the complete result
schema, model binding and reservation/outcome consistency checks. Persisted
historical attempts do not gain an inferred field. An independent fixture was
generated by the actual pre-streaming implementation from `5e95aea^` using fake
transports. The new executor sent exactly three streaming requests, with the
expected model/body/URL, then made no calls on another invocation. Historical
outcome fields, reservations and identity contents remained unchanged. Six
mutations (kind-less stream ID, extra key, wrong model, missing status, unreserved
outcome and unresolved reservation) were refused. The shared results file is
still atomically reserialized when appending new outcomes; preservation here
means the historical outcome data, not byte identity of the entire growing file.

**SP-2 — Closed.** Parsed outcomes now distinguish events, terminators, empty
frames and malformed data. Independent fake-transport checks confirmed that
markers inside content/comments do not set `done_seen`; malformed JSON and
invalid UTF-8 leave metadata invalid even when a later real terminator arrives.
Multiline JSON data with `event`, `id` and `retry` fields, mixed LF/CRLF boundaries
and a genuine terminator produced identical valid structures in coalesced,
one-byte, seven-byte and 64-byte deliveries. No content values were persisted
by these checks.

**SP-3 — Closed.** The loop splits and bounds complete frames before bounding
the incomplete remainder, while retaining the total-response cap. The original
280,274-byte reproduction now classifies identically as one chunk or 4,096-byte
chunks, with four events and a terminator. Both genuinely oversized complete
and incomplete frames stop reading before the following chunk. Instrumented
fake response streams confirmed closure on success and bound failures.

### Verification and limits

- 41 direct-probe tests passed through the repository virtual environment.
- Independent reproductions and state mutations above passed using temporary
  directories, synthetic credentials and fake transports only. Actual local
  historical results and halted ledgers were neither read nor changed.
- The repository deep-review prompt was applied to the changed state and parsing
  boundaries. The conditional SonarQube script is absent. The full suite,
  coverage, Ruff/format, mypy and Docker were not rerun by this reviewer;
  implementation-reported verification remains separate from these checks.
- Plan relative links, whitespace and final documentation diff were checked.
  No runtime code or tests were edited and no live requests were sent.
- Independent review gate cleared for at most the three already-defined
  streaming probes. This is not live compatibility evidence and does not reopen
  halted router runs, authorize model substitution, or change billing,
  quota/admission, Table or production gates.
