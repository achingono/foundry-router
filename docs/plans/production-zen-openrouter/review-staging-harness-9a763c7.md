# Independent staging harness review of 9a763c7

Date: 2026-10-11.
Reviewed commit: `9a763c733e71fa87ca302eed9f31c3e7ad309a16`.
Scope: all six changed files, the six-case plan contract, canonical admin schema,
router retry behavior, persisted state, bounded response handling, settlement and
promotion gates. The reviewing assistant independently reviewed the completed
implementation. Only review/status documentation was edited.

## Disposition

**Harness review gate not cleared.** Seven Major findings below remain open.
One additional dispatch-evidence Suggestion is recorded. All 21 existing offline
tests passed; independent fake-app reproductions confirmed the missing controls.
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
  The native Zen forwarding path can retry the provider when configured for
  multiple attempts; additional pool members can also allow other selections.
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
  four cases. Source confirms native forwarding loops up to configured attempts
  on transport/retryable failures. The normal tests already accept attempts=2.
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
