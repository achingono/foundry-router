# Google 3.8 Responses diagnostics

**Planned**, retry amendment requested by the operator. Operator explicitly requests fresh 3.8 diagnostics and availability through the
router. Historical successful native calls and intermittent provider 503/UNAVAILABLE do not
prove compatible Responses behavior. All previous execution ledgers remain immutable and
exhausted. This newly authorized diagnostic run has a separate finite ledger, not a reset.

Use the existing referenced five-key free-tier array, all five projects, as requested by the operator. At most three
logical cases per project (15 total), each with up to three provider attempts (45 total), 1,024 output tokens and 64 estimated input tokens each;
reserve 1,088 tokens per call, maximum 48,960 reserved tokens total and zero paid spend.
No ramps, quota-exhaustion probes, other models, tools/media or production changes.
Authentication/parameter failures and overruns stop traffic. Unknown started attempts remain
consumed and cannot be replayed on resume. Within a running logical request, explicitly
observed transport timeout or provider 500/502/503/504 may retry at most twice before
meaningful streaming output. Respect bounded Retry-After and backoff; if provider wait
exceeds the finite run allowance, record withheld retry. All 429 responses stop traffic because their exhaustion dimension is not safely classified.
Every physical attempt is independently reserved and observed before retry. No retry after
stream output; no retry of completed calls or on process resume. Report first-attempt and
eventual success separately, attempts, wait time, latency and settlement/cleanup.

Per project: one direct native generateContent probe with thinkingLevel low; one request
through the actual local router Responses route using Google compatible Chat Completions
with provider-default thinking. Only after compatible nonstream success, one router stream
with usage, completed text, settlement and cleanup verification. Native failure does not
assert compatible failure. Exact model gemini-3.8-flash, same simple bounded prompt. Existing
strict guards validate endpoint/auth/body; never retain secrets, prompts, outputs or state.

Preserve provider status/error enum, timeout phase, fixed safe structural envelope summary,
usage and public completion/settlement flags. Capture bounded errors using an allowlist
(INVALID_ARGUMENT, UNAVAILABLE, RESOURCE_EXHAUSTED, PERMISSION_DENIED, NOT_FOUND,
UNAUTHENTICATED, INTERNAL); unknown statuses become other, no raw messages. Timeout/unknown
records stay consumed and stop. Hold original shared stage lock plus new whole-run lock.
Before any awaited dispatch persist attempt ownership; enforce no replay on existing ledger.

Initially retain existing verifier timing; if direct evidence identifies the short verifier
timeout as limiting, propose a separate bounded timing amendment. Verifier model selection
becomes parameterized with original 3.5 defaults preserved. Real runtime remains unchanged
unless a concrete evidenced defect is independently reviewed. Focused/full checks and
contextual independent runner review before dispatch. Subsequent rollout requires exact
five-project production configuration and separate evidence; this diagnostic alone does
not authorize production cut-over or claim deployed 3.8 availability.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)

## Real-use retry amendment

Use bounded 2-second then 4-second minimum waits, honoring provider Retry-After up to
30 seconds; values above 30 seconds withhold the retry. This is a diagnostic retry transport around the actual router route, not production retry
configuration. Conservatively withhold stream retry after any provider bytes, even before
public text. All 429s withhold retry. Logical case deadline is 100
seconds, individual provider attempt deadline 25 seconds. At most 45 physical attempts,
48,960 reserved tokens across independent projects, zero paid spend. Tests cover transient
recovery, permanent failure, timeout, backoff, daily quota rejection, stream output boundary,
per-attempt durable reservations and no replay. Compare direct native and router behavior;
retry handling must remain explicit about whether it is runtime behavior or diagnostic-only.
Production settings remain unchanged. Independent amendment/runner review before traffic.

Completed diagnostic attempts that exhaust transient retries retain all reserved budgets.
They may proceed to the next independently planned surface/project so all five projects
can be assessed. An observed provider timeout is classified transient; unrecorded process
interruption remains ambiguous and cannot resume. Parameter/auth/quota failures, protocol
rejection and overruns still stop the run; streaming is withheld after nonstream failure.
