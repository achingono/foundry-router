# Independent direct-probe review of 607da09

Date: 2026-10-11.
Reviewed commit: `607da09612c9c4b99bffba7ef9bdbed1f0404a25`.

Scope: all five changed files, the direct-probe amendment, the full probe
implementation and its fourteen tests, plus the shared locking/atomic-write
helpers and existing plan's dispatch/redaction requirements. This independent
review was performed in the current session after implementation; the reviewer
made only the review/status documentation edits. Previous paid-run clearance
does not cover this new direct-provider execution path.

## Current disposition

**Direct-probe amendment review gate cleared.** Follow-up review of
`8164eadd0c67bb281b480567af608fbd0029e087` closes the remaining DP-1 and DP-3
gaps; DP-2 remains closed. No unresolved Critical or Major findings remain in
this scoped review. All 27 focused tests pass. The historical findings and
partial dispositions below are retained; the final follow-up supersedes their
open statuses. No live request or credential retrieval was performed by this
reviewer.

## Initial disposition at 607da09

Three Major findings were open. All fourteen original tests passed, but the
additional offline reproductions demonstrated incomplete no-replay,
response-memory-bound and structural-redaction guarantees. The original
findings below are retained as history; follow-up statuses supersede them.

### DP-1 — Major: Persist dispatch intent before network execution

- **File/Module:** [Probe execution and result loading](../../../scripts/quality/openrouter_direct_probe.py),
  lines 155–178 and 255–269 at the reviewed commit; dispatch reporting at
  lines 219–223.
- **The Issue:** The only budget record is written after `run_probe` returns.
  The shared lock serializes invocations and the final write is atomic, but
  neither records a request that was accepted upstream before a process crash
  or failed result write. A missing results file is treated as a new empty run.
  Additionally, `dispatched` is set only after `client.post` completes, so a
  timeout during a dispatched request is reported as undispatched.
- **Why Static Analysis Missed It:** The individual HTTP and atomic-write calls
  are valid; the defect is their ordering across an interruption and subsequent
  invocation, and the interpretation of a failed response read.
- **Impact:** Restart can repeat a billable generation and exceed both the
  one-request-per-model limit and the three-request amendment budget. Failure
  evidence can also incorrectly imply no dispatch occurred.
- **Recommended Fix:** Durably reserve a fixed probe/model slot before egress,
  separately from its final structural outcome, under the existing stage lock.
  Retain uncertain slots on failure; missing outcomes or lost initialized state
  must block replay pending review. Record conservative dispatch intent and
  preserve observed status on failure. Test crash/write-failure recovery,
  deleted initialized state, and timeout after transport entry.
- **Offline reproduction:** Injecting an `OSError` into the first result write
  allowed the first fake request to complete without a record. Restoring writes
  and rerunning the same temporary directory dispatched all three requests:
  four total calls, with the first model sent twice. A separate fake transport
  timeout made one call but returned `dispatched: false`.
- **Current status:** Closed in the final follow-up of `8164ead`; `7f0c207` had only partially addressed lost-state and pre-header accounting requirements.

### DP-2 — Major: Enforce response bounds while reading from transport

- **File/Module:** [HTTP response handling](../../../scripts/quality/openrouter_direct_probe.py),
  lines 205–231 at the reviewed commit.
- **The Issue:** `await client.post(...)` reads and buffers the complete response
  before returning. The later `aiter_bytes()` loop therefore checks an already
  buffered body. The content-encoding rejection likewise occurs after HTTPX has
  had the opportunity to decode the response.
- **Why Static Analysis Missed It:** The code contains an explicit byte-limit
  check, but its effectiveness depends on HTTPX's eager-read semantics.
- **Impact:** An oversized or compressed upstream body can consume substantially
  more memory than the stated 1 MiB bound before rejection. The timeout bounds
  the request duration, not the accumulated bytes within that duration.
- **Recommended Fix:** Open a streaming response within the overall timeout and
  client context. Check encoding/status at headers, count raw identity bytes as
  they arrive, stop at the limit and close the response on every exit. Keep JSON
  decoding bounded after collection. Test a multi-chunk oversized body and an
  encoded response, asserting early termination rather than only the final
  error category.
- **Offline reproduction:** With the body cap temporarily reduced to 32 bytes,
  a fake response generator produced all ten 16-byte chunks (160 bytes) before
  `response_bound_exceeded` was returned. The configured bound was not enforced
  during transport consumption.
- **Follow-up status:** Closed by independent review of `7f0c207`; streaming bounds and encoding rejection verified.

### DP-3 — Major: Bound and validate structural metadata before persistence/display

- **File/Module:** [Envelope classification and CLI rendering](../../../scripts/quality/openrouter_direct_probe.py),
  lines 109–110 and 288–298; persisted-result validation at lines 155–178.
- **The Issue:** Any string in upstream `finish_reason` is copied verbatim into
  structural evidence and subsequently printed by the CLI. This is an arbitrary
  provider value, not a constrained classification. The results loader validates
  only the probe IDs/duplicates, so it also accepts unvalidated structural fields
  and display values on resume; the fresh classifier is not a sufficient output
  boundary for persisted data.
- **Why Static Analysis Missed It:** The returned field is named as metadata,
  and tests place secret markers in exceptions/content rather than in that
  metadata or persisted result envelopes.
- **Impact:** A malformed upstream reason or corrupted persisted result can
  retain/display content or secret-bearing text despite the structural-only
  contract. It can also defeat the intended bounded evidence schema.
- **Recommended Fix:** Emit known finish-reason enum values only; represent
  unknown strings with a fixed category plus type/length metadata. Define a
  bounded result schema, including fixed probe/model binding, statuses, flags,
  field-name lists, numeric limits and allowed error/content classifications.
  Validate that schema before writing and again before resume/display; reject
  unexpected fields and check the serialized result-size limit before writing.
  Add secret-marker and corruption tests for metadata and saved results.
- **Offline reproduction:** Setting `finish_reason` to a synthetic sensitive
  marker caused `classify_envelope` to return that exact marker, which survived
  JSON serialization. The CLI reads and prints that field without sanitization.
- **Current status:** Closed in the final follow-up of `8164ead`; `7f0c207` had only partially addressed outer-envelope and total-size validation requirements.

## Verification and review limits

- `.venv/bin/python -m pytest tests/unit/test_openrouter_direct_probe.py -q
  --disable-warnings`: 14 passed. The tests establish ordinary classification,
  fixed request construction and replay avoidance after successful persistence;
  they do not cover the failing lifecycle/bounds/metadata cases above.
- Additional reproductions used fake HTTP transports, synthetic marker strings
  and temporary result directories only. Existing router/probe live state was
  neither read nor modified; no halted run was reset or replayed.
- The CLI constructs the fixed three-model requests and has no user-supplied
  endpoint/body option. This review does not flag that ordinary request
  construction as an extra issue. The open findings concern execution lifecycle
  and evidence boundaries.
- The repository's contextual deep-review categories were applied. No SonarQube
  scan was performed; the conditional scan script is absent. The reported full
  suite was not rerun, and no coverage, lint/type or Docker claim is made by this
  documentation-only review.
- Plan relative links, whitespace and the final documentation diff were checked.
  No runtime code, tests, credentials or production configuration changed.

## Follow-up review of 7f0c207

Date: 2026-10-11. Reviewed commit:
`7f0c207e4418b6998401c27405bfa111b2d9e9e0`. The same independent reviewer
checked the fixes and new tests; no probe implementation changes were made.

### DP-1 — Major remains open: lost state and pre-header timeouts

The new pre-egress reservation correctly blocks replay after an outcome write
failure while the results file remains present. That part is verified by the
new tests. Two previously requested lifecycle checks are still missing:

- `load_probe_results` treats every missing file as a fresh run. There is no
  durable initialization identity separate from `results-probe.json`. In a
  temporary directory, completing three fake probes, deleting that file and
  rerunning sent all three again: six dispatches for the same fixed probe set.
  Require explicit one-time initialization with a separate durable identity (or
  equivalent existing-state guard); a missing initialized record must refuse.
- `run_probe` still assigns `dispatched = True` only after response headers
  arrive. An upstream can accept the POST and then fail or time out before
  headers. A fake transport that was entered once and raised `ReadTimeout`
  returned `dispatched: false`. The new timeout test covers a stalled body after
  headers, not this case. Preserve conservative dispatch intent before the send,
  or report uncertain dispatch explicitly; lack of headers does not prove zero
  egress. The reserved slot must remain consumed either way.

The stage lock and atomic writes alone do not resolve either condition.

### DP-2 — Closed: bounds enforced during response consumption

The request now uses `client.stream` inside the timeout/client contexts, rejects
non-identity encoding at headers, and checks chunk lengths during consumption.
The response context closes on each exit. Offline tests verify that oversized
streams terminate before all chunks are read and encoded bodies are not read.
For accepted identity encoding, HTTPX's `aiter_bytes` has no content decoding to
perform; the original eager-buffering defect is resolved.

### DP-3 — Major remains open: validate the complete results envelope

The finish-reason enum/unknown-length representation prevents the original
marker leak, and per-attempt keys, binding and structure validation now reject
many corrupt values. However, `load_probe_results` does not require the exact
outer keys `{probe, reserved, attempts}` or check the total serialized-size limit
when called with `data=`. The stage writes that returned object directly.

An offline fixture containing empty valid lists, an unexpected root field with
a synthetic marker, and padding was 65,151 bytes (below 65,536). The loader
accepted it. Running the three fake probes retained both unexpected fields and
wrote 67,889 bytes; the next load refused the file as oversized. Thus unchecked
outer content can be repersisted and normal additions can create a record the
same harness cannot resume.

Require exact outer keys and validate the whole serialized envelope before
both intent and outcome writes, not only the individual outcome. Validate
reservation/result consistency in both directions as part of that envelope.
Add regressions for unknown root fields, near-limit records and write-time size
checks; preserve a safely reserved uncertain slot if recording an outcome fails.

### Follow-up verification and limits

- All 22 direct-probe tests passed with the repository virtual environment.
- Additional offline probes confirmed six calls after deleting initialized state,
  a pre-header timeout incorrectly reported as undispatched, and acceptance of
  unchecked outer fields leading to an oversized rewritten result file.
- All probes used temporary directories and fake transports. No existing live
  results, ledgers, credentials, router configuration or provider resources were
  read or modified; no live traffic was sent.
- Updated review/status documentation only. Relative plan links and whitespace
  checks passed. Full-suite, lint/type, coverage and Docker checks were not rerun
  for this scoped review; no new claims are made about those gates.

## Final follow-up review of 8164ead

Date: 2026-10-11. Reviewed commit:
`8164eadd0c67bb281b480567af608fbd0029e087`. The same independent reviewer
checked the remaining fixes, regression tests and resulting execution paths.

- **DP-1 closed:** Initialization now creates a separate durable identity under
  the stage lock. Missing initialized results or identity refuses execution.
  Intent remains durably reserved before transport, and a reserved slot without
  an outcome still blocks replay. The transport-entry marker conservatively
  preserves dispatch on pre-header exceptions; absent response headers no longer
  imply no request was sent.
- **DP-3 closed:** The loader requires exactly the three outer keys, validates
  reservation/outcome consistency in both directions, and checks the serialized
  envelope. Intent and outcome writes have whole-record size checks. The earlier
  finish-reason classification, model binding and per-attempt schema checks remain
  in place. Failed outcome persistence retains the reserved uncertain slot.
- **Verification:** All 27 direct-probe tests passed using the repository virtual
  environment. Additional independent, temporary probes confirmed: deleting
  initialized results refuses without any fourth dispatch; a transport-entered
  pre-header timeout reports dispatch; an unknown root field is rejected; and an
  oversized outcome is refused while a bounded intent remains and restart cannot
  replay it. DP-2 oversized-stream and encoding-before-body checks also passed in
  the focused suite.
- **Disposition:** All three reported findings are closed for the fixed three
  direct probes and their canonical state. This clears the independent review
  gate; it does not claim live diagnosis, compatibility, measured provider cost,
  production readiness, or permission to replay/reset historical router runs.
  The amendment's request limits and other execution prerequisites still apply.
- **Review limits:** No new runtime changes, credential retrieval or live requests.
  Existing live results/ledgers were not read or modified; verification used fake
  transports and temporary directories. Only review/status documents changed.
  Plan links and whitespace checks passed. The reported full-suite/Ruff results
  were not independently rerun; no new coverage, type-check or Docker claim is made.
