# Independent direct-probe review of 607da09

Date: 2026-10-11.
Reviewed commit: `607da09612c9c4b99bffba7ef9bdbed1f0404a25`.

Scope: all five changed files, the direct-probe amendment, the full probe
implementation and its fourteen tests, plus the shared locking/atomic-write
helpers and existing plan's dispatch/redaction requirements. This independent
review was performed in the current session after implementation; the reviewer
made only the review/status documentation edits. Previous paid-run clearance
does not cover this new direct-provider execution path.

## Disposition

**Changes required before direct live probes.** Three Major findings remain
open; no Critical findings were identified. All fourteen existing tests pass,
but the additional offline reproductions below demonstrate that the no-replay,
response-memory-bound and structural-redaction guarantees are incomplete.
No live request or credential retrieval was performed in this review.

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
- **Status:** Open; no implementation changes made by the reviewer.

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
- **Status:** Open; no implementation changes made by the reviewer.

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
- **Status:** Open; no implementation changes made by the reviewer.

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
