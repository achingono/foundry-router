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
