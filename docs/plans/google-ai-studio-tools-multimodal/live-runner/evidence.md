# Evidence

**Planned**. Five bounded model-list GETs succeeded;61models/project,44generateContent. No
inference calls. Live runner/design and exacteligiblemanifest awaitindependentreview.

**Partially implemented** dormant CLI and durable ledger,2026-10-06. Code-only independent
review cleared the architecture; manifest has61unique exact IDs matching all5catalogs,
13free-tiertextpricing rows, zero protocolapproved/dispatcheligible cases. Dryrun and --execute
both perform zero Azure/provider requests; --execute rejects missingprotocol evidence.

Ledger locks/atomic durable writes, predispatch debits, project20request/20000token caps,
initial1discoveryGET/project, pessimistic retention and overrun halt are implemented as dormant
helpers. Reuse/concurrency/caps/tampering/overrun tests pass. 43focused tests include ledger,
manifest/CLI and backend constructor optionalsettings injection with ownedclientcleanup.
At that checkpoint actualtransportguard/isolatedapp were pending; subsequentcode-only progress
is recordedbelow. Execution remains unavailable.
No secrets persisted or inference performed. Ledger helpers alone do not prove a completed live
runner. Parent T8 and generated media/signed gates remain incomplete.

Dormant runtime added under code-only review: init-only settings ignore env/dotenv, newFastAPI
router and ownedmemory stores, credential/settings client injection, exactnative single-dispatch
transportguard with durable512token debit beforeproviderawait. Identityencodingrequested;
nonidentityresponsesrejectbeforedecode, boundedresponse andconnectionclose. Success requires
completednonemptypublictext, knownusage, nobudgetoverrun. Incomplete/refusal/missingusage/
overrun fixtures fail. All10runtime fixtures use synthetictransport; no liveexecutionCLIpath.

Ledger invariants now rejectremovedhalt afterrecordedoverrun, duplicate/nonfinite/deep/oversize
JSON and inconsistentcase/totals. These checks detect inconsistency, notmaliciousOSownerrollback.
Manifestbindsowned61exactIDs/methods; no protocolapproved rows. Futureexecutionmustuseonefixed
sessionledger and reviewedimmutablecases; helpernewpaths aretest-only, notbudgetresetpermission.

Latest fullcheckpoint1203passed,2Linux-onlyskips,15Docker/Azuritedeselected,89.05%coverage;
Ruff/format/mypy pass. Dormantruntime finalreview pending; noproviderinference/productionwrites.

Synthetic dormant fixtures committed 2026-10-06: `../live-discovery.json` and
`live-runner/manifest.json` contain 61 synthetic validation IDs (not live provider
discovery and not evidence of model support). Both CLI dry-run and `--execute`
perform zero provider requests; `--execute` rejects missing protocol evidence.
`scripts/quality/google-live-validation.py` accepts an explicit `--catalog` path
and fails closed on missing or malformed catalog/manifest. Seven manifest/CLI
regressions pass from a clean checkout.

Remote reconciliation, 2026-10-06: `45cbb70` supplies the synthetic dormant catalog/manifest
used by offline tests. The earlier actual model-list GET artifacts are preserved separately as
[actual discovery](../live-discovery-actual.json) and [discovered manifest](manifest-discovered.json).
They record discovery only, not inference or approved protocol cases. The CLI's default remains
the committed synthetic catalog; its explicit `--catalog` option permits offline validation of
the preserved discovered manifest. No live inference ran during reconciliation.

Offline validation of `manifest-discovered.json` against `../live-discovery-actual.json` passes
with 61 models, zero eligible cases and zero provider requests. Remote defaults continue to use
synthetic IDs; actual model IDs are preserved only in the separate discovery artifacts.

Reconciled-head dry-run revalidation, 2026-10-06 (`fce71aa`): CLI dry-run (no `--execute`)
against both the synthetic `manifest.json` and `manifest-discovered.json` with
`live-discovery-actual.json` reports 61 models, zero dispatch-eligible cases, zero provider
requests and `protocol_gates_pending` in both cases. Caps verified at 20 requests / 20,000
tokens per project with zero paid spend. No `--execute` run was performed: no caller credential
was supplied in this session, the manifest awaits independent review, and protocol gates remain
pending. No live inference, production reads, or ledger debits occurred.

Thinking-protocol docs evidence for the text-first track, 2026-10-07 (official Gemini API
thinking docs, not live proof): `gemini-2.5-flash-lite` does not think by default and
returns no thought content at `thinkingBudget: 0`, so the unsigned thinking-disabled
profile fits it pending live confirmation of zero thought parts/usage. `gemini-2.5-flash`
disables thinking at `thinkingBudget: 0` per the documented range, but public forum
reports describe disable failures under investigation — live proof of zero thought tokens
is required, not docs alone. `gemini-2.5-pro` **cannot** disable thinking (documented
minimum budget 128, dynamic by default), so its pool needs a thinking-enabled profile
(budget >= 128 with thought-token pricing) rather than the thinking-disabled shape; live
proof must confirm thought usage accounting. Proposed manifest transitions (for reviewer
approval, not applied): flash/flash-lite `text_nonstream` toward a docs-evidenced
thinking-disabled case gated on live zero-thought proof; pro `text_nonstream` toward a
thinking-enabled case with thought-usage accounting. Separately, retirement scope is
unresolved: the Vertex model-versions table dates `gemini-2.5-flash`, `-flash-lite` and
`-pro` to 2026-10-20
(https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions), while the
Gemini Developer API deprecations table states 2.5 Pro and Flash are not deprecated with
no shutdown date but restricts new access to prior users
(https://ai.google.dev/gemini-api/docs/deprecations), and forum reports describe 404s
consistent with entitlement rather than retirement. Treat October 20 as **unconfirmed**
for AI Studio free-tier use: execution-day behavior (success vs 404) is itself validation
signal, and per-account prior-use access must be confirmed before spending budget.

Guarded execution path implemented 2026-10-07 (offline-tested, no live run):
`google_live_execute.py` selects only `text_nonstream` rows with the reviewer-approved
`docs_supported_pending_live` status (flash-lite first, then flash; pro and all
streaming/tool/media rows never selected), fetches the credential via Azure CLI into
memory with a 30 s timeout, opens the durable session ledger, and dispatches cases
sequentially round-robin across the five projects within remaining caps — halting a
project on overrun, recording provider errors without retry, and exiting 0/1/2 for
all-passed/completed-with-failures/refused. `--execute` requires `--keyvault-ref` plus
`--ledger`; dry-run behavior is unchanged, and missing-argument, no-eligible-case and
no-`az` paths all fail closed with zero provider requests. Seven offline execute-path
tests pass with mocked CLI and mock provider (all-pass, overrun-halt, missing-usage
no-refund, credential-failure and no-eligible-cases leave no state). Manifest rows for
flash-lite and flash `text_nonstream` now carry the executable status; pro stays blocked
(the fixed `thinkingBudget: 0` helper cannot serve it). Streaming execution is explicitly
not implemented — streaming rows are rejected by selection. No credential was supplied in
this session, so no live dispatch occurred; execution awaits the credential at execution
time plus reviewer release.

First live execution, 2026-10-07 (authorized; `docs_supported_pending_live` flash-lite +
flash rows, 10 cases across 5 projects, ledger `ledger-2026-10-07.json`): all 10 cases
dispatched through the exact-body guard and returned router 502 with no usage recorded;
debits retained at 512 tokens each, no overrun, no halt (per-project ledger now 3/20
requests, 1024/20000 tokens). Two additional direct diagnostic requests outside the
ledger (status-only, then error-message with the synthetic fixture prompt) show the
provider answering 400 `API_KEY_INVALID` for the `foundry-router-production-google-keys`
value on `generativelanguage.googleapis.com` — the key is not valid for this API, so no
model was reached and the retirement/access question is untested. Router behavior itself
validated end-to-end: exact request-shape guard passed, single dispatch per case, 400
mapped to sanitized 502, full debit retained without retry, nothing leaked to logs.
Conclusion: the provider leg is blocked on key validity, not on router behavior; the
secret value in `kv-fr-prod-261004` must be verified (a Gemini Developer API key for one
of the five free-tier projects) before any rerun. No inference content obtained; exit
boxes stay unchecked.

Rerun with per-project keys, 2026-10-07 (operator clarified the secret is a JSON array of
five API keys; `fetch_project_credentials` parses it with index-order mapping key `i` to
`project-i`, strict length match, key material never logged or written; 9 new offline
tests cover shapes, mapping and leave-no-state refusals): **4 passed, 6 failed, exit 1**.
Projects 1–2 return HTTP 200 with completed non-empty text and known usage
(`actual_tokens` 8, no overrun) on **both** flash-lite and flash with `thinkingBudget: 0`
— live proof that thinking-disabled text works through the router with correct usage
settlement. Projects 3–5 return 404 on both models: keys authenticate but those accounts
lack model access, empirically confirming the documented prior-use access restriction
(entitlement, not retirement). Failed debits retained without retry; no project halted.
Cumulative honest spend across both ledgers (`ledger-2026-10-07.json` plus
`ledger-2026-10-07-rerun.json`, discovery counted once): 5 requests and 2048 tokens per
project against 20/20000 caps, zero paid spend. Manifest rows stay
`docs_supported_pending_live` (a `live_proven` status would need reviewer approval);
text_streaming, tools and all other capabilities remain unexecuted and gated.

Separate 3.x thinking-level track, 2026-10-07 (own design, own 1,088-token reserve =
1,024 generated + 64 input estimate, ledger `ledger-2026-10-07-3x.json`): pilot
flash-lite `minimal` on project-1 **passed** (200, completed text, 9 known tokens,
zero thoughts) after a first attempt failed only on the router rejecting the
provider-attached `thoughtSignature` — now an explicit drop-after-capture decision,
unit-covered, never persisted or forwarded. Staged gate cleared: 3.8-flash `low` on
project-1 then passed (200, 8 tokens, zero thoughts), and the remaining eight cases
**all passed** (200, completed text, known usage, no overrun, no halt). Notably,
projects 3–5 — which return 404 for 2.5 models — succeed on both 3.x models, so access
is per model family, not per project alone. Cumulative 3.x spend: 10 requests and
~10,890 tokens reserved/actuals across five projects, inside caps with all prior debits
carried. `minimal`/`low` produced zero thought tokens on the trivial probe in all ten
cases; thought-inclusive settlement remains proven only by offline fixtures, not live
thoughts. Streaming text is next on the same profiles; tools stay conditional.

Harder-prompt probe, 2026-10-07 (sums-of-primes prompt, `--prompt`/`--case-prefix`
support added with prompt bound validation; same 1,088 reserve): 3.8-flash `low` on
project-1 hung provider-side past 240 s with zero bytes twice, and the router case
failed 503 on backend timeout with the debit retained — no usage, no overrun, no halt.
Direct isolation probes then showed trivial-prompt `low` on 3.8-flash returning provider
503 while the hard prompt on 3.5-flash-lite `minimal` returned 200 in ~1 s; the follow-up
router case on 3.5-flash-lite **passed** (200, 24 tokens, zero thoughts). Thought-inclusive
settlement therefore stays live-unproven: the one model/level likely to think (`low`)
is the one currently unreachable for anything but trivial prompts, and trivial prompts
provoke no thoughts at either level.

Streaming series, 2026-10-07 (same profiles, SSE exact-body guard with `alt=sse`,
terminal-event validation, mid-stream cancellation covered offline): 3.5-flash-lite
**5/5 passed** across all projects (200, completed SSE text, 8–9 tokens, no overrun).
3.8-flash streaming failed everywhere at first (one router 503, four 502s); direct
diagnosis showed provider 503 "high demand" on `streamGenerateContent`. A retry round
recovered project-1 (**passed**, 8 tokens) while projects 2–5 still fail (router 502s;
a direct probe on project-2's key stalls with zero bytes). Standing interpretation:
provider-side capacity/stall behavior specific to 3.8-flash streaming on those keys —
nonstreaming 3.8 works on all five projects, and 2.5 models 404 on projects 3–5 while
3.x succeeds there. Access is therefore per model×project×operation, and routing must
exclude persistently failing combinations rather than merely cooling them down (future
work; cooldown already contains the transient). Cumulative 3.x-ledger spend stays inside
caps (heaviest project-1: 8/20 requests, 7616/20000 tokens, nothing halted).

Follow-up attempts recorded in the same ledger: `hard2` 3.8-flash `low` on project-1
still failed HTTP 503 with unknown usage (the reserve stays debited); `hard2`
3.5-flash-lite `minimal`, proving irrationality of square root of two, passed HTTP 200
with 783 total observed tokens. `thoughtsTokenCount` was absent, so this does not prove
live nonzero-thinking settlement. Earlier references to zero thoughts should be read
as absent thought-token metadata, not an explicit observed zero. These attempts are
historical; no additional live inference ran during final exclusion verification.

Combination exclusion implementation cleared independent final review. Full local
verification: **1,584 passed, 3 platform skips, 14 Azurite tests deselected, 89.04%
coverage**, with **99.32%** coverage for the exclusion module; Ruff check/format and
mypy passed. Thirty-seven focused exclusion cases cover streaming-mode separation,
decay/expiry, terminal-outcome classification, exclusive probes, generation/epoch
fencing, release, credit-admissible alternatives, and metrics. This establishes
synthetic routing behavior, not production deployment or distributed persistence.
