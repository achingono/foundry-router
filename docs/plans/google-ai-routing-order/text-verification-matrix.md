# Text verification matrix

**Partially implemented**, reconciled 2026-10-08 after adapter extraction. This is an
analysis of existing artifacts through the local reconciliation phase. The later authorized
follow-up section records new native execution; no production configuration changed.

## Evidence boundaries

The [inventory CSV](../google-ai-studio-capacity-inventory/inventory.csv) preserves the
classified 2026-10-07 native router counts and separately records 2026-10-08 direct probes.
The [inventory narrative](../google-ai-studio-capacity-inventory/index.md) explains the
unclassified pilot and invalid-key attempts. Ledger usage is transport/accounting evidence,
not proof of public response success; its reservation totals are not actual provider usage.
The [fresh survey](../google-ai-studio-capacity-inventory/free-tier-survey-2026-10-08.json)
contains provider status and thinking profile. Direct provider completions clear neither
router translation nor streaming gates. All observations are historical samples.

## Exact combinations

All rows below concern native Responses text. Router columns are classified historical
passes/failures. Direct status is from the fresh nonstreaming survey; quotas are explicit
provider evidence where available. Unknown values remain unknown.

| Project | Exact model | Thinking profile | Router nonstream pass/fail | Router stream pass/fail | Fresh direct nonstream status | RPM / input TPM / RPD |
| --- | --- | --- | --- | --- | --- | --- |
| project-1 | `gemini-2.5-flash` | budget 0 | 1 / 0 | Unverified | 200 | 5 / 250000 / 20 |
| project-1 | `gemini-2.5-flash-lite` | budget 0 | 1 / 0 | Unverified | 200 | 10 / 250000 / 20 |
| project-1 | `gemini-3.5-flash-lite` | minimal | 3 / 0 | 1 / 0 | 503 | Unknown / Unknown / Unknown |
| project-1 | `gemini-3.8-flash` | low | 1 / 2 | 1 / 1 | 200 | Unknown / Unknown / Unknown |
| project-2 | `gemini-2.5-flash` | budget 0 | 1 / 0 | Unverified | 200 | 5 / 250000 / 20 |
| project-2 | `gemini-2.5-flash-lite` | budget 0 | 1 / 0 | Unverified | 200 | 10 / 250000 / 20 |
| project-2 | `gemini-3.5-flash-lite` | minimal | 1 / 0 | 1 / 0 | ReadTimeout | Unknown / Unknown / Unknown |
| project-2 | `gemini-3.8-flash` | low | 1 / 0 | 0 / 2 | 200 | Unknown / Unknown / Unknown |
| project-3 | `gemini-2.5-flash` | budget 0 | 0 / 1 | Unverified | 404 | Unknown / Unknown / Unknown |
| project-3 | `gemini-2.5-flash-lite` | budget 0 | 0 / 1 | Unverified | 404 | Unknown / Unknown / Unknown |
| project-3 | `gemini-3.5-flash-lite` | minimal | 1 / 0 | 1 / 0 | 503 | Unknown / Unknown / Unknown |
| project-3 | `gemini-3.8-flash` | low | 1 / 0 | 0 / 2 | 200 | Unknown / Unknown / Unknown |
| project-4 | `gemini-2.5-flash` | budget 0 | 0 / 1 | Unverified | 404 | Unknown / Unknown / Unknown |
| project-4 | `gemini-2.5-flash-lite` | budget 0 | 0 / 1 | Unverified | 404 | Unknown / Unknown / Unknown |
| project-4 | `gemini-3.5-flash-lite` | minimal | 1 / 0 | 1 / 0 | ReadTimeout | Unknown / Unknown / Unknown |
| project-4 | `gemini-3.8-flash` | low | 1 / 0 | 0 / 2 | 200 | Unknown / Unknown / Unknown |
| project-5 | `gemini-2.5-flash` | budget 0 | 0 / 1 | Unverified | 404 | Unknown / Unknown / Unknown |
| project-5 | `gemini-2.5-flash-lite` | budget 0 | 0 / 1 | Unverified | 404 | Unknown / Unknown / Unknown |
| project-5 | `gemini-3.5-flash-lite` | minimal | 1 / 0 | 1 / 0 | 503 | Unknown / Unknown / Unknown |
| project-5 | `gemini-3.8-flash` | low | 1 / 0 | 0 / 2 | 200 | Unknown / Unknown / Unknown |

## Newer router observations and unclassified dispatch

The [2026-10-08 router observer](../google-ai-studio-capacity-inventory/live-results-2026-10-08.json)
records four failed/ambiguous 3.5 Flash-Lite nonstreaming outcomes. Its
[cumulative ledger](../google-ai-studio-capacity-inventory/ledger-2026-10-08.json) has five
new dispatch debits: project-3 was interrupted before result persistence. That dispatch
has no recorded public/provider outcome and stays unclassified. These observations are
separate from the earlier pass/fail columns above and from the direct survey.

No live nonzero `thoughtsTokenCount` settlement proof is recorded. An absent field is not
an observed zero. Synthetic thinking-inclusive usage and signature-handling tests pass,
but that evidence cannot complete the live accounting gate.

## Remaining gates and next execution scope

| Gate | Existing evidence | Required next evidence |
| --- | --- | --- |
| Native 2.5 text on projects 1–2 | Historical router and fresh direct nonstreaming success; complete quota triplets | Bounded native streaming, terminal usage, cleanup and relevant provider failure/admission cases |
| Native 2.5 text on projects 3–5 | Repeated provider 404 observations | Confirm operator entitlement before inclusion; keep unavailable combinations outside rollout scope |
| Native 3.5 Flash-Lite minimal | Historical router nonstream/stream successes; newer router failures and direct 503/timeouts | Fresh bounded exact-combination verification and authoritative quotas; historical success alone cannot establish current availability |
| Native 3.8 Flash low | Historical nonstream success/failures; streaming only project-1 recovered; all direct ramps ended 503 | Fresh streaming/client/usage evidence for selected projects and authoritative quotas; retain failed combinations explicitly |
| Compatibility Responses nonstream/stream | Local adapter tests; repaired 3.5 Flash-Lite passed eight simple-text cases on projects 2–5 | Required additional model/project combinations, quota evidence and unbuffered latency/cancellation if in rollout scope |
| Compatibility embeddings | Local validation/mapping/accounting tests | Exact embedding model, supported-operation configuration, pricing/quota dimensions and bounded live usage evidence; no text-model inference of embedding support |
| Nonzero thinking usage | Synthetic inclusive accounting tests | Provider-reported thought metadata plus public usage and exact local settlement |
| Provider failure/admission through router | Synthetic cooldown, exclusion, retry and settlement tests; direct quota diagnostics | Bounded router traffic proving pre-output 429 handling, no failover after downstream output, and retained dispatched usage/reservations |
| Table-backed real inference | Synthetic persistent/shared credit and health checks | Isolated Table-backed real inference/settlement/cleanup before production cut-over |

These are scoped gates, not a requirement to rerun every historical case. The intended
rollout determines required combinations. Media remains deferred and tools/continuation
conditional under the [completion audit](../google-ai-studio-tools-multimodal/completion-audit.md).

## Capacity and execution inputs

Only four of the twenty text-track combinations above have complete quota triplets.
The inventory's 24 confirmed RPM/input-TPM buckets concern a broader model set; they do
not supply missing quotas for 3.5 Flash-Lite or 3.8 Flash. Across those 24 buckets the five
missing RPD values are 3.5 Flash projects 2–5 and 3.6 Flash project-3. The operator reconfirmed on 2026-10-08 that all five projects are free-tier; the CSV
retains `operator_reported_free_tier`. Actual Google project IDs and additional shared-model/alias
limits remain unknown; operator tier confirmation is not an authenticated provider capture.

Before new execution, bind the supplied Key Vault reference to the project roster and
record a finite request/token/spend allowance plus the applicable durable ledger. The
existing ledger is tied to its historical session and retains consumed debits; creating
an empty ledger would not prove that the historical allowance reset. Keep keys, prompts,
outputs and provider error bodies out of evidence. A new live execution contract or runner
extension needs the repository's independent plan review before implementation.

## Local checks for this reconciliation

The CSV contains exactly twenty selected project/model rows. Historical totals remain
22 classified successes / 17 failures, with the pilot separately unclassified. Fresh
survey records exactly twenty selected attempts. The cumulative observer ledger contains
five new dispatches, of which four have result records; no status was inferred for the
missing fifth. Relative source links were validated. No runtime code changed in this phase.

## Authorized follow-up stage, 2026-10-08

The operator supplied `foundry-router-production-google-keys`, confirmed a string-array
of free-tier keys and authorized all available budget. Read-only Azure discovery resolved
the secret metadata; its value is captured only into memory by the existing runner.
This first finite stage reuses the reviewed native text/stream contracts and carries all
prior cumulative ledger debits forward, retaining the stricter 20-request/20,000-reserved-token
per-project limits. It runs at most twenty new cases: 3.5 Flash-Lite and 3.8 Flash
nonstreaming on five projects each, then streaming only for passing nonstream combinations
within the remaining caps. No retries; first failed/ambiguous outcome stops that model/project
for the stage. Zero paid spend, original body/output/deadline bounds, isolated memory/one
stores and unchanged production apply. Further stages require their concrete protocol and
budget gate; this stage does not create fresh historical allowance by clearing a ledger.

### Follow-up outcomes

[Persisted results](native-text-results-2026-10-08.json) record fifteen actual dispatches;
[the retained ledger](ledger-native-text-2026-10-08.json) includes every prior debit plus
these requests. 3.5 Flash-Lite minimal passed nonstreaming and streaming on all five keys
(ten successes), with valid public text and 8–9 observed total tokens. 3.8 Flash low failed
nonstreaming on all five: projects 1–4 returned public 502 after about 20–21 seconds;
project-5 returned public 503 after 1.33 seconds. Provider status is not captured by this
runner, so the public codes do not identify provider error causes. All five have unknown
usage and retain their full 1,088-token debit. No 3.8 streaming was dispatched after failure.

No overrun occurred. Project-1 cumulative accounting is 19 requests/17,280 reserved tokens;
projects 2–5 each have 14 requests/11,840 tokens. Thought metadata is absent for all attempts,
so nonzero thinking settlement remains unverified. These results establish the recorded
3.5 native text/client/usage cases only; quota ceilings, provider failure/admission traffic,
compatibility Responses/embeddings, Table-backed real inference and production gates remain.


## Compatible text stage, 2026-10-08

[Reviewed stage](../google-compatible-text-verification/index.md) dispatched five 3.5 Flash-Lite
nonstream requests, one per key. Provider returned 200 with 7 input/2 completion tokens each,
but public translation returned 502 in every case. All synthetic $0.009 debits matched observed
usage and reservations cleared. No stream ran after these failures; absent thought metadata
stays unknown. This proves neither successful compatible Responses nor embeddings.
Ledger debits are retained, project-1 exhausted the stricter 20-request stage allowance and
projects 2–5 retain five request slots each; no historical allowance is reset. Provider schema
rejection needs separate bounded diagnosis before any retry stage.

## Repaired compatible text acceptance, 2026-10-08

The operator requires OpenAI-compatible Responses. Following safe diagnosis and independent
review, the [stateless signature repair](../google-compatible-signature-text/evidence.md)
passed eight actual cases on projects 2–5: nonstreaming and streaming `gemini-3.5-flash-lite`
with provider-default thinking. Every public/provider status was 200, terminal public usage
matched 8–9 observed total tokens, synthetic debits matched and reservations cleared.
Project 1 was never dispatched because its cumulative request allowance is exhausted.
The ledger retains all previous failures, diagnostics and full conservative reserves; projects
2–3 now have 18 requests/16,192 tokens and projects 4–5 have 17/15,104.

These exact samples establish simple-text compatible Responses and SSE translation only.
The bounded guard buffers upstream SSE, so latency and upstream cancellation remain unverified.
Thought metadata was absent; nonzero thinking, embeddings, tools/continuation, other models,
authoritative quotas, provider admission and Table/production gates remain open.
