# Google compatible text verification

**Planned**, independently reviewed 2026-10-08; see [review](plan-review.md). Close the compatibility-surface text operation gap in
[roadmap 2a](../google-ai-routing-order/index.md). Production remains memory/one.

## Authorized bounded stage

The operator supplied the existing Key Vault string-array secret
`foundry-router-production-google-keys`, confirmed all five projects free-tier and
authorized all available budget. Reuse its reviewed index-to-project credential binding
and the cumulative [native-stage ledger](../google-ai-routing-order/ledger-native-text-2026-10-08.json).
Never reset consumed debits. This stage accepts only the fixed existing cumulative ledger
path; require it to exist before BudgetLedger construction. Validate its native-stage cases
and retained totals against a committed immutable baseline fingerprint, allowing only appended
deterministic compatibility cases. Missing/substituted ledgers refuse before credential fetch
or provider activity; the generic helper's create-new-ledger behavior is never invoked here. Retain 20 requests/20,000 reserved tokens per project,
zero paid spend and at most nine additional dispatches: one nonstream case on project-1
and nonstream/stream pairs on projects 2–5. Stream only after that project's nonstream
success and only within the remaining ledger. Each dispatch reserves 1,088 tokens before
any provider await; output is capped at 1,024. No retries. Stop that project after a failed,
ambiguous or overrun outcome. Failover/admission, embeddings and media need separate stages.

Use only exact `gemini-3.5-flash-lite`, with operator/provider-documented free-tier eligibility
and the prior native 5/5 nonstream/stream passes. Native evidence is not compatible support
evidence. Compatibility's existing text adapter sends no explicit thinking policy: record
provider-default thinking, never mislabel it native minimal. A simple fixed text prompt
minimizes work. If compatible output includes thought-token metadata, record it as supplied;
absence is unknown. This stage does not establish nonzero thought accounting.

## Isolated runner contract

Add a separate reusable verification runner, reusing init-only isolated settings,
credential loading and durable BudgetLedger. Configure one Google `openai_compat` backend,
one logical Responses model and fresh memory health/credit/quota/metrics. Set synthetic
test prices and an explicit local account allowance so usage-driven settlement is observable;
record prices as synthetic, not Google billing. Validate remaining after completion equals
initial allowance minus exact observed input/output synthetic debit, with zero reservations.

The exact transport guard accepts a single POST to
`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`, without query,
userinfo, alternate host/port or redirects, with model `gemini-3.5-flash-lite`, one fixed
user message, `max_completion_tokens: 1024`; streaming adds only `stream: true` and
`stream_options.include_usage: true`. Require selected Bearer credential, strip inbound auth,
disable ambient proxies and request identity encoding. Bound request to 4 KiB, response
to the existing Google response cap, provider/public run to 25 seconds, one connection.
The ledger guard persists before forwarding and retains reserves on unknown/error usage.

Capture only provider/public HTTP code, known validated input/completion/total token counts,
optional supplied reasoning tokens, public completion/text-present booleans, metered debit,
reservation cleanup and elapsed time. No prompts, outputs, raw errors, credentials or
secret values in evidence/logs. Valid full token usage and nonempty completed public text
are required for success. Streaming requires a valid terminal Responses event and no failure
event; preserve the normal decoder's SSE boundaries. Provider guard may buffer the bounded
provider response for evidence, so this stage does not establish live cancellation/latency.

Full usage requires nonnegative nonboolean input/completion/total integers with total equal
input plus completion, completion at most 1,024, and supplied reasoning tokens at most
completion. Reasoning is not blindly added to completion. Charge the ledger with the greater
of reported total and input-plus-completion when those numeric fields are individually valid,
even if inconsistent; an explicit total greater than 1,088 halts. Other malformed/incomplete
usage retains the reserve. Capture inconsistency/overcap as failed accounting evidence,
never successful compatibility. Provider-default thinking inclusion remains unverified unless
exact response evidence establishes it.
Malformed/incomplete usage retains pessimistic ledger debit and conservative local credit.
Unknown thought semantics remain unverified. Explicit usage greater than reservation halts
the project's ledger. Each case has a deterministic unique ID and its persisted safe result;
resume skips recorded attempts, never repeats an already-ledgered ambiguous dispatch.
Hold a separate OS advisory stage lock for the whole run (including provider awaits), so
concurrent processes cannot dispatch overlapping cases or stream before persisted nonstream
success. Persist safe stage results atomically with fsync before moving to the next case.
Any deterministic stage case present in the ledger but absent from safe persisted results
means an interrupted/ambiguous dispatch: retain debit and halt that project for this stage
on resume. A persisted failed result likewise permanently halts that project within this
stage. Validate result identities/status/usage against the same ledger before continuation;
never use historical/native successes to authorize compatibility streaming. Test crash after
reserve/before result, failed-project resume and competing stage lock processes.

## Gates

Independent plan review before runner edits; synthetic exact-body/auth, byte/deadline bounds,
usage, error, stream-terminal and metered-cleanup tests before any live dispatch. Complete
focused/full quality checks and contextual review. Execute only the bounded approved stage
using the user-supplied secret, record every dispatch/failure and preserve ledgers. Update
the exact evidence matrix and commit the transition. No production/provider quota changes.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
