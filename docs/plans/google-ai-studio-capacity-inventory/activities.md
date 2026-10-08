# Google AI Studio capacity inventory activities

1. Inspect catalogs, manifest, ledgers and canonical quota/operations documentation.
2. Review this documentation-only plan in a different agent session before creating the inventory.
3. Create a readable inventory and a CSV with one row per discovered project/model. Record catalog methods separately from native text/streaming outcomes. Leave provider quotas and project IDs unknown unless authoritative evidence is supplied.
4. Count only correctly keyed router validation attempts; separate the initial invalid-credential run and unledgered diagnostic probes. Derive pass/fail from narrative evidence, never from missing usage alone. Preserve small sample sizes and prompt/operation distinctions.
5. Add an operations link and documentation hub link. Provide an authenticated quota capture procedure, without new inference, secret retrieval, infrastructure or production changes.
6. Validate CSV completeness and exact source agreement, relative links, diff and secret boundaries. Obtain independent contextual review using the deep-review prompt. Documentation-only scope requires no runtime coverage, Docker build or code analysis scan; record checks and any unfinished quota gate honestly.

## Review focus

Provider quotas versus test caps/context limits; aliases and shared quota identity; advertised methods versus live-proven operations; missing usage versus failure; historical samples versus current guarantees; native versus compatibility surfaces.

## Authorized live measurement amendment (2026-10-08)

User explicitly requested using the existing Key Vault secret for live rate/limit measurement. This supersedes the documentation-only no-live scope above. Fetch five keys only in memory with the existing redacted credential helper; use the reviewed native text harness and only the documented free-tier 3.5 Flash-Lite/minimal profile for an initial throughput series. Measure provider status, latency, completed router outcome, known token usage, Retry-After and allowlisted numeric quota violation fields; never record response text, prompts, keys, headers or raw errors. Preserve every earlier ledger debit (including the unclassified pilot) in a new cumulative ledger. Existing 20/20,000 per-project caps persist unless the user expressly amends them. Do not mutate the old ledgers or reset allowances. Dispatch bounded serial attempts per project, stop a project on 429, ambiguous timeout, auth failure, overrun or cap, and make no automatic retries. At most one provider request is active globally initially. Use a finite timeout and retain unknown usage. A successful burst establishes only observed throughput/lower bounds; exact ceilings require explicit provider quota metadata or authoritative capture, and RPD cannot be inferred from a short run. Independently review the amendment and one-off execution script before live use. Validate the observer/budget merge offline; no runtime application changes.

## Working-path rate ramp amendment

User expressly removed earlier request/token caps, authorizing available/needed budget with zero paid spend. Authenticated project-1 discovery succeeded and now advertises 50 models; direct 2.5 Flash-Lite budget-0 inference completed in 0.355s with five tokens while 3.5 Flash-Lite and Gemma probes timed out. Next finite stage: at most 60 serial 2.5 Flash-Lite requests per project, 64 generated-token ceiling/128-token conservative reserve each, 10s timeout, no retries, stop each project on any failure, 429 or reserve overrun. Durable write-ahead per-attempt records own this newly authorized stage without modifying old ledgers. Preserve numeric quota values, bounded quota metric/ID and model/location dimensions only; never error messages or inference content. Separate provider results from router compatibility. Successful bursts provide observed lower bounds; quota violations may identify exact limits but only for the named bucket/dimension at the observed time. Independent preexecution review required.

## Exact free-tier model survey amendment

All five refreshed authenticated catalogs return 50 models. Rate ramp established explicit 10 RPM for 2.5 Flash-Lite on projects 1–2, while projects 3–5 returned 404. Survey all 13 exact previously documented free-tier text models with one direct call per model/project (65 calls maximum), at most five globally/one per project. Use 256 output tokens plus 64 conservative input reserve, 12s total deadline/10s inactivity and 256KiB streamed response bound. Known profiles remain explicit (2.5 Flash/Lite budget 0, 3.5 Lite minimal, 3.8 low); others use provider defaults for direct inventory evidence only, not router enablement. No retry or further ramp on a rejected model. Write-ahead ledger and sanitized quota identifiers/dimensions retained; malformed/empty/truncated output is not a completed result. Unknown or absent thoughts are not zero. This finite stage is covered by user's expanded zero-paid budget; independent preexecution review required.

## Working-model quota ramps amendment

The 65-probe survey completed. Extend its reviewed bounded probe to at most 40 serial calls per model/project combination that returned completed output in that survey, excluding 2.5 Flash-Lite already measured. At most five calls globally/one per project, same256 output/320 reserve/12s wall/256KiB receive, durable per-attempt records and no retries. Stop each combination immediately on failed/ambiguous/truncated output, 429 or observed reserve overrun. Do not ramp failed or inaccessible combinations. This finite stage targets provider-reported quota metadata and observed throughput; exact TPM/RPD remain unknown unless explicitly identified. User's expanded zero-paid budget covers the stage. Independent preexecution review required.

## Input-TPM probe amendment

Seek explicit input-TPM values with at most12 bounded synthetic large-input requests: 2.5 Flash-Lite on projects1–2,3.5 Flash and3.6 Flash across five projects. Each input is800KB repeated benign text (approximately400K tokens, under the discovered1M context limit),64 output ceiling,450,064 conservative token estimate; provider usage can differ and is recorded as numeric actuals when available. Total30s deadline/20s inactivity,256KiB response bound,max5 globally/one/project,no retries,stop on rejection. Context errors/transport timeouts are not TPM evidence. Only explicit named quota violations justify ceiling values. Expanded zero-paid user budget applies; no media/uploads/tools or production changes. Independent preexecution review required.

## Accepted-input TPM boundary extension

400,004 input tokens were accepted with HTTP200 on2.5 Flash-Lite projects1–2 and3.6 Flash all5;3.5 Flash returned503. Extend only those seven accepted combinations to at most3 serial900K-input-token synthetic probes each (1,800,010B benign text,950,064 estimated reservation,64output), under1,048,576 catalog context bound. Same30s wall/20s inactivity/256KiB streamed response/max5 total,no retries,stop any non200 or reserve overrun. HTTP200 truncated output may continue for input-admission measurement, but is never counted as useful completed output. Seek explicit TPM violation; successful input admission remains only observed accepted input, not a sustainable ceiling. Independent review before execution.

## Paced daily-quota probe amendment

Twenty-four model/project buckets now have explicit5or10RPM quota evidence. Pace at most36 additional small requests per verified bucket at13s minimum start intervals (below5RPM), up to24 concurrently globally/one per model bucket (projects1–2 can have six different model buckets active; other projects four). Models are2.5Flash/Lite onprojects1–2,3FlashPreview/3.5Flash/3.6Flash/Robotics onall5. Maximum864 requests, same256output/320estimate/12s wall/256KiB response and write-ahead records, no retries. Stop each bucket atfirst failed/ambiguous/truncated outcome/429/overrun; do not suppress minute rejection or blindly retry. This bounded stage seeks explicit named daily-quota violations; counts without provider daily metadata are lower-bound samples, not RPD ceilings. Expanded user budget applies, zero paid spend; independent preexecution review required.

## Final missing-dimension probes

Daily paced run finished297requests/273completed,19daily20RPDviolations and5availabilityfailed/ambiguousbuckets. One final900K-input probe per missing-TPM combination (2.5Flashprojects1–2,3FlashPreview/3.5Flash/Roboticsall5;17maximum), same30s wall/20s inactivity/256KiB response/950,064estimated reserve,64output,no retries,max5global. Some buckets are daily-exhausted; this is a single explicit diagnostic request for missing dimension metadata, not inference retry or quota-bypass. Preserve every named quota violation independently; daily-only rejections leaveTPMunknown. After this stage no further provider traffic planned; mark unresolved dimensions accurately. Independent preexecution review required.

## Five remaining daily fields

All24verifiedRPMbuckets now have explicit250,000inputTPM;19have20RPD. One final small direct probe for3.5Flashprojects2–5and3.6Flashproject3 after at least60s and prior provider retry-delay cooldown. Maximum5calls, same reviewed small-probe bounds/write-ahead/no retry. These buckets stopped on availability failures earlier; success leavesRPDunknown, explicit daily rejection mayfillit. No additional ramps; independent preexecution review required.
