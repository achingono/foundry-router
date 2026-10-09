# Google AI Studio capacity inventory

For candidate workloads and the evidence behind them, see [Google model task guidance](../../operations/google-model-task-guidance.md).

**Partially implemented**, compiled 2026-10-08 from historical discovery/pricing (2026-10-06), native router observations (2026-10-07), and refreshed catalogs/live quota measurements (2026-10-08). All **310 project/model combinations** (305 historical rows plus five newly discovered rows) are recorded in local-only `inventory.csv`. Provider quota responses establish RPM for **24 model/project buckets**: 10 RPM for 2.5 Flash-Lite on projects 1–2 and 5 RPM for the verified Flash/Robotics buckets below. All 24 buckets have provider-confirmed 250,000 input TPM; 19 have provider-confirmed 20 RPD. Remaining quotas are explicitly unknown.

The labels `project-1` through `project-5` follow credential-array index order in the validation runner. Operator-supplied quota screenshots (local-only `quotas.md`) now identify all five project IDs and displayed limits for both selected models. All five projects are operator-confirmed free-tier; credential-to-project association and independent tier verification remain uncaptured. The initial inventory used repository evidence only. The user subsequently authorized live measurements using the existing Key Vault secret; live diagnostics are documented below. Keys remained in memory; production settings were unchanged.

## Private capture handling

Screenshots, `inventory.csv`, `quotas.csv` and `quotas.md` contain operator project identifiers.
They are local-only, gitignored and absent from a fresh clone. Retained quota summaries use
project labels. Actual identifiers and credential mappings belong in private operator configuration.
Historical statements below describe the local captures; they do not imply those captures are
available in source control. The subsequent local history cleanup removed these originals from rewritten commits; remote
copies and private recovery material require separate handling.

## Screenshot quota update, recorded 2026-10-09

Captured quotas (local-only `quotas.md`) transcribe 65 visible UI rows. All 310 inventory rows now carry
operator-supplied project IDs; 44 unambiguous catalog matches have separate `quota_ui_*`
fields. These supplement historical provider measurements. Both selected models have numeric
RPM/TPM/RPD on every project; shared buckets and the UI TPM token dimension remain open.

## Observed native text operations

Counts represent classified router validation attempts, not uptime estimates. Simple prompts dominate the historical sample; substantive task quality remains unverified except the recorded project-1 harder probes. The 2026-10-08 large-input probes measure intake/quota behavior rather than task quality. The four tested models have advertised `generateContent` and `countTokens` methods; the CSV preserves each exact catalog method list. Native nonstreaming uses `generateContent`; streaming uses `streamGenerateContent` even though the discovery method list does not advertise it separately.

| Project | Model | RPM | Input TPM | RPD | Native nonstreaming | Native streaming |
| --- | --- | --- | --- | --- | --- | --- |
| project-1 | `gemini-2.5-flash` | 5 | 250,000 | 20 | 1 pass / 0 fail | Unverified |
| project-1 | `gemini-2.5-flash-lite` | 10 | 250,000 | 20 | 1 pass / 0 fail | Unverified |
| project-1 | `gemini-3.5-flash-lite` | 15 | 250,000 (UI TPM) | 500 | 3 pass / 0 fail | 1 pass / 0 fail |
| project-1 | `gemini-3.8-flash` | 5 | 250,000 (UI TPM) | 20 | 1 pass / 2 fail | 1 pass / 1 fail |
| project-2 | `gemini-2.5-flash` | 5 | 250,000 | 20 | 1 pass / 0 fail | Unverified |
| project-2 | `gemini-2.5-flash-lite` | 10 | 250,000 | 20 | 1 pass / 0 fail | Unverified |
| project-2 | `gemini-3.5-flash-lite` | 15 | 250,000 (UI TPM) | 500 | 1 pass / 0 fail | 1 pass / 0 fail |
| project-2 | `gemini-3.8-flash` | 5 | 250,000 (UI TPM) | 20 | 1 pass / 0 fail | 0 pass / 2 fail |
| project-3 | `gemini-2.5-flash` | Unknown | Unknown | Unknown | 0 pass / 1 fail | Unverified |
| project-3 | `gemini-2.5-flash-lite` | Unknown | Unknown | Unknown | 0 pass / 1 fail | Unverified |
| project-3 | `gemini-3.5-flash-lite` | 15 | 250,000 (UI TPM) | 500 | 1 pass / 0 fail | 1 pass / 0 fail |
| project-3 | `gemini-3.8-flash` | 5 | 250,000 (UI TPM) | 20 | 1 pass / 0 fail | 0 pass / 2 fail |
| project-4 | `gemini-2.5-flash` | Unknown | Unknown | Unknown | 0 pass / 1 fail | Unverified |
| project-4 | `gemini-2.5-flash-lite` | Unknown | Unknown | Unknown | 0 pass / 1 fail | Unverified |
| project-4 | `gemini-3.5-flash-lite` | 15 | 250,000 (UI TPM) | 500 | 1 pass / 0 fail | 1 pass / 0 fail |
| project-4 | `gemini-3.8-flash` | 5 | 250,000 (UI TPM) | 20 | 1 pass / 0 fail | 0 pass / 2 fail |
| project-5 | `gemini-2.5-flash` | Unknown | Unknown | Unknown | 0 pass / 1 fail | Unverified |
| project-5 | `gemini-2.5-flash-lite` | Unknown | Unknown | Unknown | 0 pass / 1 fail | Unverified |
| project-5 | `gemini-3.5-flash-lite` | 15 | 250,000 (UI TPM) | 500 | 1 pass / 0 fail | 1 pass / 0 fail |
| project-5 | `gemini-3.8-flash` | 5 | 250,000 (UI TPM) | 20 | 1 pass / 0 fail | 0 pass / 2 fail |

- **3.5 Flash-Lite / minimal:** classified nonstreaming 7 passes / 0 failures (five simple prompts plus two harder project-1 prompts); streaming 5 passes / 0 failures. The harder prompts recorded 24 and 783 total observed tokens. An additional project-1 pilot ledger observation is unclassified, as explained below.
- **3.8 Flash / low:** classified nonstreaming 5 passes / 2 failures (the failures are harder project-1 prompts); streaming 1 pass / 9 failures over two rounds. Initial streaming failed everywhere; project-1 recovered in the second round. Provider capacity/stall failures are distinct from quota exhaustion and model entitlement.
- **2.5 Flash and Flash-Lite / thinkingBudget 0:** each model has nonstreaming 2 passes / 3 failures. Projects 1–2 completed; projects 3–5 returned provider 404, consistent with prior-use access restrictions. Streaming was not executed in this track.

These observations validate the native surface only. They do not establish compatibility-surface Responses/embeddings, function tools, structured output, history, media or other advertised methods. Catalog visibility is not access approval; zeros with `unverified` mean no classified test, not proven zero capacity. Current availability, task quality and production readiness cannot be inferred from these small historical samples. Historical observations contain no live quota-ceiling proof; the new direct rate ramp below records explicit 429 quota values.

## Full catalog and free-tier classification

The historical catalogs contain the same 61 models per project. The refreshed 2026-10-08 catalogs contain **50 models per project**, all five authenticated GETs succeeding. The CSV preserves historical rows and adds current presence/method/context columns; 250 rows are currently advertised: 245 historical rows and five new `gemini-nano-banana-2.1` rows. Sixty historical rows are absent from the refreshed catalog. Absence alone does not prove retirement or access denial. The manifest documents free-tier **text** pricing for 13 exact historical model IDs as of 2026-10-06:

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gemma-4-26b-a4b-it`
- `gemma-4-31b-it`
- `gemini-2.5-flash-lite`
- `gemini-3-flash-preview`
- `gemini-3.1-flash-lite`
- `gemini-3.5-flash`
- `gemini-3.5-flash-lite`
- `gemini-3.6-flash`
- `gemini-3.7-flash`
- `gemini-3.8-flash`
- `gemini-robotics-er-2-preview`

The remaining 48 historical catalog models per project lack an affirmative free-tier text classification in this manifest; one newly discovered model per project also lacks historical pricing classification. CSV `unknown_not_in_historical_manifest` marks the newly discovered model; `true` and `false` preserve the historical manifest boolean. `false` means not affirmatively documented by that source, not necessarily paid-only or universally unavailable. Neither pricing classification nor advertised methods authorizes enabling a capability; model aliases/version names remain separate inventory rows until provider-confirmed quota sharing and access are known.

## Evidence and counting boundaries

Sources: [discovery](../google-ai-studio-tools-multimodal/live-discovery-actual.json), [manifest](../google-ai-studio-tools-multimodal/live-runner/manifest-discovered.json), [dated live evidence](../google-ai-studio-tools-multimodal/live-runner/evidence.md), [keyed 2.5 rerun ledger](../google-ai-studio-tools-multimodal/live-runner/ledger-2026-10-07-rerun.json) and [3.x ledger](../google-ai-studio-tools-multimodal/live-runner/ledger-2026-10-07-3x.json).

The CSV counts the ten correctly keyed 2.5 router attempts and 29 3.x-ledger attempts classified by the narrative: **22 passes / 17 failures**. The initial [invalid-key ledger](../google-ai-studio-tools-multimodal/live-runner/ledger-2026-10-07.json) contains ten requests that reached no model and is excluded from model reliability counts. Discovery GETs and direct diagnostic requests are also excluded; direct probes are qualitative context, not a complete request log.

The rerun ledger additionally records `txt-gemini-3.5-flash-lite-project-1` with nine actual tokens, an ID and usage also present in the 3.x ledger. Ledgers lack HTTP/public outcome and attempt timestamps; they cannot establish whether these are duplicate snapshots or distinct successful attempts. The narrative records a signature-rejected pilot before a successful pilot, and transport usage is captured before router translation. Therefore the rerun pilot is retained as **one unclassified ledger observation**, excluded from pass/fail counts. Known usage alone does not establish success; unknown usage alone does not establish failure.

Ledger `tokens` totals retain conservative reservation debits even when actual usage is smaller; they are not actual provider consumption. Test caps of **20 requests / 20,000 tokens per project** and per-case reserves of 512 or 1,088 tokens are validation safeguards, not provider limits. Catalog input/output token limits are per-request context/generation bounds, not TPM/RPD. Earlier narrative “zero thoughts” statements were corrected to **absent thought metadata**; live nonzero-thinking settlement remains unproven.

## Capture current provider capacity

1. Open the authenticated [AI Studio rate-limit page](https://aistudio.google.com/rate-limit). Confirm which real project corresponds to each label using the operator's credential mapping; record actual project ID and current tier through the approved configuration channel. Keep API keys out of the inventory.
2. For every relevant exact model, record RPM, **input** TPM, RPD, quota bucket identity and any shared-model/alias limits exactly as displayed, with source and UTC capture timestamp. A missing or unlisted dimension stays unknown; do not convert it to zero or unlimited. If the provider uses different token semantics, record the discrepancy before mapping it to `input_tpm`.
3. Populate the blank quota fields in the CSV only from that authoritative capture. Blank `rpm`, `input_tpm`, `rpd`, `quota_bucket_id`, `project_id` and `quota_captured_at` explicitly mean unknown. Replace `quota_source=unknown_not_captured` with a dated source reference and confirm tier. Zero observed capacity requires an explicit provider value or verified access result, not absence from discovery.
4. Confirm which exact models share each allowance before aggregating capacity. Multiple keys for one project and aliases for one model do not create new allowances. Current [project-group quota accounting](../../configuration/index.md) is conservative; distinct per-model buckets remain a future design. Do not turn model rows into artificial independent quota groups.
5. Reconcile operation-specific access/reliability separately with fresh bounded validation when authorized. Recheck quotas after provider/tier changes; invalidate stale captures before configuration updates. The user subsequently authorized bounded live rate/limit measurements with as much available budget as needed and zero paid spend. Use finite reviewed stages, retain dispatch accounting and stop on explicit quota rejection; short bursts cannot prove daily limits.

The CSV is an evidence inventory, not executable routing configuration. Unknown quotas must not be installed as untracked groups: the current store does not track groups without configured limits. `credit_metered: false` disables dollar admission only, never quota/resource limits. Provider quotas are allowances, not Azure balances or local cost estimates.

The 2026-10-08 [stateless compatible text acceptance](../google-compatible-signature-text/evidence.md)
is reflected separately in `compatibility_surface_observation`: exact 3.5 Flash-Lite Responses
nonstreaming/streaming passed on projects 2–5 after the bounded signature repair. Project 1
retains its failed pre-repair result and exhausted-stage-budget limitation. Native counts and
provider quota fields remain unchanged. These samples do not prove embeddings, quota ceilings,
unbuffered streaming latency/cancellation or deployment readiness.

Production remains memory-backed with `maxReplicas: 1`. Native thinking-level profiles remain validation-track scoped; this inventory grants no production enablement. See [operations](../../operations/index.md), [thinking-level confinement](../google-ai-studio-tools-multimodal/live-runner/thinking-level-text-design.md) and [combination exclusion](../google-ai-studio-tools-multimodal/live-runner/quota-exclusion-design.md).

## Live measurement, 2026-10-08

Authenticated [refreshed catalogs](discovery-2026-10-08.json) succeeded across all five projects. The [direct rate ramp](rate-ramp-2026-10-08.json) made 28 requests: project-1 completed 11 before a 429; project-2 completed 12 before a 429; projects 3–5 each returned 404 on their first request. Both 429s explicitly identify `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, value **10**, model `gemini-2.5-flash-lite`, location `global`. Provider retry-delay metadata was 44s and 39s. This is direct provider evidence for those two exact RPM buckets; burst acceptance above ten is not a sustainable limit. No input-TPM or RPD ceiling was present in these violations. These counts include only the ramp; other diagnostics remain separate.

The first [router observer series](live-results-2026-10-08.json) has four persisted outcomes and five durable dispatch debits in its [cumulative ledger](ledger-2026-10-08.json): one project-3 dispatch was interrupted before its result persisted. No provider status or usage was recorded for those five 3.5 Flash-Lite attempts. Projects 1–2 have ambiguous results; projects 4–5 returned router 502 after about 20s. A [direct 3.5 diagnostic](direct-diagnostic-2026-10-08.json) also timed out after 20s. These are unknown provider outcomes, not 429 proof.

A separate [connectivity series](connectivity-2026-10-08.json) returned authenticated discovery 200 with 50 models and direct 2.5 Flash-Lite 200 with five total tokens in 0.355s on project-1; a Gemma-4-31B probe timed out. Root HEAD/GET worked unauthenticated. Basic connectivity therefore does not establish inference availability for each model.

See [current direct text observations](current-observations.md) for per-model completion, quota rejection, other failures and latency. The [exact free-tier survey](free-tier-survey-2026-10-08.json) records one direct text probe per documented model/project with explicit thinking profile, status, timing, numeric usage and any named quota violations. Direct provider results do not close native router or compatibility-surface gates. Unknown usage remains unknown and no provider text/error message is retained.

## Provider-reported RPM inventory

| Exact requested model | Project labels with explicit evidence | RPM | Provider model dimension |
| --- | --- | --- | --- |
| `gemini-2.5-flash-lite` | 1–2 | 10 | `gemini-2.5-flash-lite` |
| `gemini-2.5-flash` | 1–2 | 5 | `gemini-2.5-flash` |
| `gemini-3-flash-preview` | 1–5 | 5 | `gemini-3-flash` |
| `gemini-3.5-flash` | 1–5 | 5 | `gemini-3.5-flash` |
| `gemini-3.6-flash` | 1–5 | 5 | `gemini-3.6-flash` |
| `gemini-robotics-er-2-preview` | 1–5 | 5 | `gemini-robotics-er-2-preview` |

The [working-model ramps](model-rate-ramps-2026-10-08.json) issued 250 requests: 211 completed, 22 explicit 429s, and 17 other failed or ambiguous outcomes. No observed reserve overrun. Each combination stopped on its first failure. The provider maps 3 Flash Preview to model dimension `gemini-3-flash`; keep that identity when accounting for aliases. Distinct dimension labels do not by themselves prove absence of additional shared project-wide limits.

The [large-input probes](input-tpm-probes-2026-10-08.json) accepted 400,004 input tokens with HTTP 200 on 2.5 Flash-Lite projects 1–2 and 3.6 Flash across all five projects. Only one 2.5 Flash-Lite response completed useful output; other 200s were truncated or unusable at 64 output tokens. 3.5 Flash returned 503 on all five projects. This establishes accepted input per request only; no TPM ceiling was returned.

## Provider-reported input TPM

The [900K-input probes](input-tpm-ramps-2026-10-08.json) produced seven immediate 429 responses, each explicitly naming `GenerateContentInputTokensPerModelPerMinute-FreeTier`, value **250,000**, location `global`: 2.5 Flash-Lite on projects 1–2 and 3.6 Flash on projects 1–5. These explicit provider values take precedence over earlier accepted 400,004-token bursts when setting sustained admission limits. No larger prompt was retried after rejection; all seven token reservations remain labeled estimates, not actual consumed usage.

## Provider-reported daily allowance

The [paced daily probes](daily-probes-2026-10-08.json) made 297 requests: 273 completed, 19 returned explicit daily-quota 429s, and five stopped on availability failures. Every daily violation named `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, value **20**. Confirmed buckets: 2.5 Flash/Lite on projects 1–2, 3 Flash Preview and Robotics on all five projects, 3.5 Flash on project 1, and 3.6 Flash on projects 1, 2, 4 and 5. Missing daily values remain unknown; the [remaining daily probes](remaining-daily-probes-2026-10-08.json) returned completed output on all five missing buckets after cooldown, so their daily ceilings remain unknown.

For 2.5 Flash-Lite on projects 1–2 the observed triplet is **10 RPM / 250,000 input TPM / 20 RPD**. Other confirmed complete buckets have **5 RPM / 250,000 input TPM / 20 RPD**. The daily ceiling limits small tasks before token capacity. No daily reset was observed; provider retry-delay metadata is diagnostic evidence rather than proof of reset time.

The [final large-input diagnostics](other-input-tpm-probes-2026-10-08.json) returned 17 explicit 250,000 input-TPM violations, filling every remaining TPM value among the 24 verified RPM buckets. These single diagnostic requests intentionally followed daily exhaustion on some buckets to seek missing dimension metadata; they were not inference retries or attempts to bypass a limit. RPM, input TPM and RPD sources/timestamps/bucket IDs are separate CSV fields. A missing violation never means unlimited capacity.

Quota capture timestamps approximate response completion (recorded request start plus elapsed duration); they are not server-side timestamps.
