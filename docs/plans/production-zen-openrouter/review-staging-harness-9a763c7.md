# Independent staging harness review of 9a763c7

Date: 2026-10-11.
Reviewed commit: `9a763c733e71fa87ca302eed9f31c3e7ad309a16`.
Scope: all six changed files, the six-case plan contract, canonical admin schema,
router retry behavior, persisted state, bounded response handling, settlement and
promotion gates. The reviewing assistant independently reviewed the completed
implementation. Only review/status documentation was edited.

## Disposition

**Harness review gate not cleared.** After the
[follow-up review of febe207](#follow-up-review-of-febe207), SV-2, SV-3, SV-4,
SV-5 and SV-7 are closed. SV-1 and SV-6 remain open; SV-8 is partially addressed.
The findings below describe the original review and are superseded by the
follow-up dispositions. The reviewer also accepts a
[narrower deployment-acceptance contract](amendment-black-box-acceptance.md)
at plan level; its implementation and re-review are pending.
No staging writes, production changes or live requests were performed. The
separate operator/release/maintenance gates in the plan remain open as well.

## Findings

### SV-1 — Major: Reconcile ledger and results before resuming or promoting

- **File/Module:** [Staging harness](../../../scripts/quality/staging_validation.py),
  `execute_validation` (lines 776–819), `_staging_results_passed` (719–749),
  `validate_result` and `load_validation_results`.
- **The Issue:** A saved result causes the loop to skip a case without checking
  its ledger reservation/outcome. Results are written before the ledger outcome,
  so a write failure/crash in that interval leaves a reserved-without-outcome
  case which resume skips instead of blocking. The production prerequisite uses
  an even weaker separate validator: it ignores manifest binding, termination,
  dispatch flags and several type/bound checks. Derived success flags are also
  not fully cross-checked against model identity, token caps and debit evidence.
- **Why Static Analysis Missed It:** Each file is valid independently; the error
  is their cross-file state invariant and the divergent promotion validator.
- **Impact:** Successor paid cases dispatch after unresolved state; contradictory
  or corrupt staging evidence can authorize production validation.
- **Recommended Fix:** Validate the entire ordered prefix and reconcile every
  reserved slot, ledger outcome and strictly bound result before any successor.
  Refuse missing/contradictory state in either direction. Use the same complete
  manifest/result validation for staging resume and production gating, including
  exact identity, mode, counts/caps and evidence coherence. Inject failures at
  each write boundary and test corrupted promotion prerequisites.
- **Evidence:** Injecting failure into the first `record_outcome` after results
  persistence left its ledger outcome `None`; resume nevertheless dispatched
  three successors. Separately, after a fake staging pass, replacing its saved
  manifest with `{}` and setting every result to `terminated_ok=false`,
  `dispatched=false`, `input_tokens=-1` still permitted two production fake calls
  when the explicit production flag was present.
- **Disposition:** Open; blocking.

### SV-2 — Major: Bind the exact six case specifications and aggregate allowance

- **File/Module:** [Manifest validation](../../../scripts/quality/staging_validation.py),
  `validate_manifest` (125–178) and `manifest_fingerprint`.
- **The Issue:** Only run and case IDs are fixed. Pool, provider, deployment,
  prices and streaming mode are accepted from arbitrary shape-valid manifests;
  fingerprinting only freezes those choices after initialization. Unknown case
  keys are also copied into the persisted fingerprint. Each run separately checks
  USD 0.01 instead of the combined six-case allowance.
- **Why Static Analysis Missed It:** These values satisfy the declared types;
  the missing constraint is the independently reviewed authorization envelope.
- **Impact:** A new run can send unreviewed models/provider traffic or an excluded
  OpenRouter stream, exceed the aggregate estimate, and persist arbitrary extra
  manifest values outside the intended redacted schema.
- **Recommended Fix:** Define immutable run/case specifications matching the
  committed manifests, require exact keys and exact pool/provider/deployment/
  mode/prices, and derive the six-case budget from both specifications. Changes
  require a reviewed amendment/new authorization, not a different first manifest.
- **Evidence:** Changing every staging case to `azure_foundry` and an unreviewed
  deployment, plus changing the OpenAI case to streaming, passed validation and
  all four fake cases. Setting every input/output price to 3.0 in both manifests
  validated each run despite their combined USD 0.01152 estimate (USD 0.00768
  staging plus USD 0.00384 production), exceeding USD 0.01.
- **Disposition:** Open; blocking.

### SV-3 — Major: Enforce one provider dispatch, not merely one router request

- **File/Module:** [Setup checks](../../../scripts/quality/staging_validation.py),
  `_resolve_group` (433–448) and retry handling (635–643);
  [router forwarding](../../../src/foundry_router/forwarding/__init__.py).
- **The Issue:** Setup takes the first backend from a pool and only records
  retry settings. It does not require exactly one backend or an effective
  one-attempt policy. HTTPX retries=0 applies only to the harness-to-router hop.
  **Correction from the follow-up:** Zen bypasses the generic retry loop and
  already uses a dedicated single-shot path; the original contrary claim was
  incorrect. Additional pool members can allow other selections on eligible
  failover, which was the valid scope of this finding.
- **Why Static Analysis Missed It:** The limit crosses two HTTP clients and the
  router's routing/retry policy; a fake app with one response per POST hides it.
- **Impact:** One reserved validation case can consume multiple paid provider
  attempts or select an unreviewed backend, violating the six-POST contract.
- **Recommended Fix:** Refuse absent/unproven retry evidence or multi-member
  pools before inference. Verify an effective one-dispatch policy for each
  actual provider path and the exact single backend/account binding. Do not
  silently change production retry policy. If existing deployed policy cannot
  meet the contract, obtain a separately reviewed enforcement mechanism or
  amendment. Test actual router behavior with retryable provider failures.
- **Evidence:** A fake admin response advertising two members in every pool
  (including an extra Azure backend) and `retry_attempts=10` still passed all
  four cases. The normal tests accept attempts=2, which by itself is not a
  defect for the dedicated Zen/OpenRouter paths. The original generic-retry-loop
  attribution to Zen is withdrawn; see the follow-up verification.
- **Disposition:** Open; blocking.

### SV-4 — Major: Bound nonstream and setup responses while reading

- **File/Module:** [HTTP handling](../../../scripts/quality/staging_validation.py),
  `_check_health`, `_read_admin`, `_read_json_response` and the nonstream POST
  at lines 648–656.
- **The Issue:** Nonstream inference and health/admin calls use eager HTTPX
  reads and unrestricted `response.json()`. The 1 MiB manifest bound is never
  checked on nonstream replies. Content encoding is neither rejected nor
  explicitly controlled; even streaming counts decoded bytes. Declaring an
  `encoded_response` category does not enforce it.
- **Why Static Analysis Missed It:** HTTPX buffers/decompresses behind an ordinary
  convenience method; the manifest's bound does not constrain that method.
- **Impact:** An oversized or compressed response can exceed the intended
  memory/work bounds and even be recorded as a passing paid case.
- **Recommended Fix:** Stream every externally supplied response, enforce
  status/encoding policy at headers and bounded raw bytes during reading, use
  bounded parsing, and close on every exit. Give setup responses explicit small
  bounds. Preserve timeout and observed dispatch facts on bound/read failures.
- **Evidence:** Fake nonstream responses containing more than 1 MiB of padding
  were fully accepted; all four staging cases passed. No oversized-response
  failure was recorded.
- **Disposition:** Open; blocking.

### SV-5 — Major: Require complete SSE frames and a valid terminal sequence

- **File/Module:** [SSE reader](../../../scripts/quality/staging_validation.py),
  `_read_stream_terminal` (516–550).
- **The Issue:** The reader buffers the body and parses individual `data:` lines,
  without validating event boundaries or the trailing residual frame. It can
  accept a completed-response JSON line whose SSE event was never terminated.
  The frame bound is applied to each JSON line, not to actual frames; terminal
  selection also treats `response.incomplete` as a candidate completion body.
- **Why Static Analysis Missed It:** JSON parsing and HTTP EOF both succeed;
  neither proves a complete SSE event or a valid response lifecycle.
- **Impact:** Truncated/malformed streams can pass the exact completion gate
  introduced to prevent premature streaming production enablement.
- **Recommended Fix:** Parse frames incrementally at the earliest boundary,
  enforce per-frame and total bounds, reject nonempty trailing partial frames,
  parse multiline data consistently, and require an unambiguous completed
  terminal event with valid usage and no failed/incomplete/contradictory terminal.
- **Evidence:** Removing all final newlines from the fake Zen terminal event,
  leaving the terminal frame unterminated at EOF, still passed the stream and
  all four staging cases.
- **Disposition:** Open; blocking.

### SV-6 — Major: Missing independent upstream evidence must leave the gate open

- **File/Module:** [Case acceptance and promotion](../../../scripts/quality/staging_validation.py),
  `independent_upstream_observed` initialization (585), successful result path
  and `_staging_results_passed`; [activities](activities.md), section 3.
- **The Issue:** Every case records `independent_upstream_observed=false`, yet
  can be marked passed and satisfy production prerequisites. The plan explicitly
  requires recording this limitation and leaving the gate open when deployed
  observation cannot support the public/provider/usage proof. There is no separate
  incomplete-verification status or prerequisite evidence check.
- **Why Static Analysis Missed It:** The schema permits the false flag; the
  conflict is between the execution contract and what 'passed' authorizes.
- **Impact:** Self-consistent public output and local accounting can clear a
  promotion prerequisite despite the specifically required independent proof
  remaining unavailable.
- **Recommended Fix:** Distinguish passing black-box checks from full verification
  eligibility. Keep production gating closed until validated independent evidence
  is attached, or obtain an explicit independently reviewed plan amendment
  accepting a narrower evidence contract. Do not silently weaken the plan in the
  harness or infer that the generic production flag waives the evidence gate.
- **Evidence:** All four normal fake staging results were passed with the flag
  false, and the production path accepted them and executed both fake cases.
- **Disposition:** Open; blocking.

### SV-7 — Major: Settlement tolerance can turn a missing charge into a pass

- **File/Module:** [Debit comparison](../../../scripts/quality/staging_validation.py),
  lines 690–693 and `SETTLEMENT_TOLERANCE_USD`;
  [canonical admin route](../../../src/foundry_router/api/routes/admin.py),
  lines 171–183.
- **The Issue:** The fixed USD 0.000002 tolerance exceeds small valid request
  charges. The claimed six-decimal rounding belongs to the per-backend helper;
  the canonical `credit_groups[group].live.estimated_remaining_usd` consumed by
  this harness is emitted directly from the snapshot without that rounding.
- **Why Static Analysis Missed It:** The arithmetic is valid; its precision and
  acceptance meaning depend on the exact admin field and configured token prices.
- **Impact:** A request with positive usage/prices but no debit can be accepted
  as reconciled, defeating the financial verification gate.
- **Recommended Fix:** Derive tolerance from the precision of the actual
  evidence path and floating-point subtraction, with strict positive-charge
  handling. If the deployed evidence is too coarse to resolve a charge, report
  inconclusive settlement or use finer authenticated evidence; never pass zero
  debit merely because it lies in a wide absolute tolerance. Test the smallest
  charges and zero/wrong debit cases using the real canonical admin schema.
- **Evidence:** A fake OpenAI request with one input and one output token,
  expected cost USD 0.00000075 and actual debit zero, returned `passed`,
  `settlement_matches=true`, `synthetic_debit_usd=0.0`. All four cases completed.
- **Disposition:** Open; blocking.

### SV-8 — Suggestion: Mark router POST entry before waiting for its response

- **File/Module:** [Dispatch evidence](../../../scripts/quality/staging_validation.py),
  lines 645–658 and timeout/transport exception handling.
- **The Issue:** `dispatched` becomes true only after the response body/stream
  has been read. A timeout after the router receives the POST remains false.
- **Why Static Analysis Missed It:** The failure occurs between transport entry
  and assignment; ordinary success-path tests do not distinguish these moments.
- **Impact:** Failure evidence can imply that no request was sent. The durable
  reservation still prevents replay, so this is an evidence defect rather than
  an independently demonstrated extra-dispatch path.
- **Recommended Fix:** Track inference POST transport entry and response headers
  separately; preserve conservative sent/unknown facts through timeouts, bounds
  and read failures. Keep router receipt distinct from proof of provider egress.
- **Evidence:** A fake transport recorded one received inference POST and then
  raised a read timeout; the persisted failed result had `dispatched=false`.
- **Disposition:** Open; non-blocking alone, best corrected with SV-4.

## Verification and limits

- 21 harness tests passed through `.venv/bin/python -m pytest`.
- Independent reproductions used the committed manifests, the test module's
  stateful fake app and targeted variants, temporary directories and synthetic
  credentials only. Results above are fake traffic, not live evidence.
- Reviewed canonical source for admin precision, pool structure and native retry
  behavior, and applied the repository deep-review prompt to the scoped state,
  trust and accounting boundaries.
- Full suite, coverage, Ruff/mypy, Docker and static scanning were not rerun by
  this reviewer. Implementation-reported checks are not represented as review
  runs. The conditional SonarQube script is absent.
- Plan relative links, whitespace and final documentation diff were checked.
  No source/tests, credentials, actual historical ledgers, deployed configuration
  or production state were changed. No live request or staging write was sent.

## Follow-up review of febe207

Date: 2026-10-12.
Reviewed commit: `febe207681e9bd466059f85d2514aed92e590676`.
Scope: all four changed files, prior independent reproductions, actual provider
forwarding selection, result/promotion validation and the narrowing decision.
Only review/status documentation was edited.

### Disposition

**Not cleared for staging writes or live dispatch.** Five Majors are closed;
SV-1 and SV-6 remain open and SV-8 remains a non-blocking partial fix. The
[black-box acceptance amendment](amendment-black-box-acceptance.md) resolves the
reviewer's policy decision, but matching implementation/re-review is required.

| Finding | Status | Review conclusion |
| --- | --- | --- |
| SV-1 | Partially addressed; Major remains open | Reordered writes block the newly created missing-result crash case, but there is still no complete reconciliation or success-coherence check before skipping results |
| SV-2 | Closed for committed specifications | Exact case keys/values prevent model/mode/price substitution; fixed six-case estimate is USD 0.0051456 |
| SV-3 | Closed; original explanation corrected | Single-member pools plus dedicated Zen/OpenRouter single-shot paths meet the scoped attempt policy without changing deployed retry settings |
| SV-4 | Closed | Setup and inference reads now stream with identity-encoding checks, bounds and response context cleanup |
| SV-5 | Closed for reported framing failures | Incremental frames, residual rejection and unique completed terminal checks reject the prior invalid streams |
| SV-6 | Partially addressed; Major remains open pending scoped implementation | Ordinary black-box results now block promotion; an unsubstantiated true upstream flag still unlocks the path |
| SV-7 | Closed for configured prices and tested balances | Tighter tolerance and explicit zero-debit rejection distinguish the smallest tested paid charges |
| SV-8 | Partially addressed; Suggestion remains | Timeout paths harvest entry, but body-bound/header-policy ValueErrors do not; marker also includes setup GETs |

### Remaining SV-1 gaps and test limitations

`execute_validation` still skips any case found in `by_id` without reconciling
its ledger slot. A failed/halted ledger with passing results can return the
passing results, and a saved result beside an unresolved ledger outcome allows
successors. Reordering future writes does not validate historical/interrupted or
corrupted state. `validate_result` still does not require provider/deployment to
match the case, enforce token caps on general resume, or recompute saved debit
coherence from the usage and prices.

Independent evidence:

- Generated the exact old crash state with `9a763c7` and a fake transport by
  interrupting `record_outcome` after result persistence. `febe207` resumed it
  and dispatched three successors while the first ledger outcome stayed `None`.
- After a fake complete run, set the first ledger outcome to failed **and**
  `halted=true`, leaving that ledger internally valid. Resume returned all
  passing results. The new contradictory-ledger test only changes outcome to
  failed while leaving halted false, so it tests the ledger's own validation,
  not cross-file reconciliation.
- With the canonical staging manifest present, saved results whose upstream flag
  was true but provider/deployment were null and debit was zero still allowed
  two production fake calls. Complete model/usage/debit/ledger validation must
  apply equally to resume and production prerequisites.

Required fix remains whole-prefix reconciliation in both directions, before any
skip/return/dispatch, plus one strict success-coherence validator at all entry
points. Test internally valid but contradictory files and actual cross-version
crash state, not only individually invalid ledger objects.

### SV-6 and narrowing decision

The default producer sets the upstream flag false, which now stops normal
production execution. That is useful fail-closed behavior, but checking a saved
Boolean is not validated independent evidence. Copying the committed staging
manifest into the temporary state directory and setting the flags true allowed
production execution without any observer artifact. The current negative tests
omit that canonical manifest, so they can pass because prerequisite loading
fails before reaching the intended evidence assertion.

The reviewer accepts the narrower contract in the amendment: validate deployed
public behavior and local admin-accounting consistency, label that scope, and
make no independent provider/billing claim. Implement that scope explicitly in
the immutable manifests/results and promotion checks, keep the upstream flag
false, and retain strict state validation and explicit operator approval. This
is a planning decision, not clearance for the current promotion path.

### SV-8 remaining evidence issue

A nonstream POST received by the fake router and then rejected for exceeding
1 MiB now correctly fails and halts, but records `dispatched=false`. The
ValueError branches do not call `harvest`. `_EntryMarker` also records every
health/admin GET, not specifically the inference POST. Restrict the marker to
the inference request and preserve entry/header facts on every return/exception;
keep router-request entry distinct from proof of upstream egress.

### Closed findings and independent verification

- 41 staging-harness tests passed; 16 actual-router provider integration/transport
  tests passed, for 57 total.
- Twenty-eight independent case mutations (pool, provider, deployment, mode,
  input/output price and extra keys across all four staging cases) were refused.
  `validate_run_pair` is currently exercised by tests rather than called by the
  executor; exact immutable prices keep the committed six-case total within
  USD 0.01. Do not describe a general runtime pair-loader as implemented.
- Verified the provider dispatch selection precedes the generic retry loop.
  Zen already took `_forward_zen_non_streaming`/`_forward_zen_streaming`; the
  earlier review's contrary retry explanation was wrong. Existing provider
  integration tests cover Zen ambiguous failure and separate-backend 429
  failover; one-member enforcement removes that additional target.
- Independent body-bound reproduction now halts after the first oversized
  response instead of passing. Bounded setup, encoding and cleanup source paths
  were inspected. SV-8 describes the remaining dispatch-fact limitation.
- Valid SSE terminal structures agreed across coalesced, one-byte, seven-byte
  and 64-byte delivery. Unterminated, duplicated, incomplete, malformed and
  failed-event variants were rejected with instrumented response closure.
- One-input/one-output charges passed with real fake-account debits; the prior
  OpenAI zero-debit case now fails. The USD 1e-9 tolerance is a fixed bound for
  the tested magnitude, not a dynamically derived ULP calculation for arbitrary
  account balances. Larger/less precise balances may fail conservatively.
- All checks used temporary state, synthetic keys and fake transports. No live
  requests, actual historical ledger reads, secret access or deployed changes.
  Full suite/coverage, Ruff/mypy, Docker and Sonar were not rerun by the reviewer;
  the conditional scan script is absent. Plan links, whitespace and diff checked.
