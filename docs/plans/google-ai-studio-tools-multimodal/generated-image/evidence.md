# Evidence

**Partially implemented helpers**,2026-10-06; generatedimage Responses runtime remains Planned.
Consolidateddesign independentlyreviewed; code-onlyPNGhelper clearance conditionalonlifecycle/
resource/SDK/accounting gates. No generatedimageprovidercalls/productionchanges.

Finite1024RGB/RGBA PNG syntax, CRC/64chunk/contiguousIDAT/zlibmax_length/exactrows/filters and
EOF checks implemented. Ancillary/signatures rejected. zliberrorsnormalizeValueError; onebyte
header split supported. No rendering/rewrite/codec dependencies. Linuxworker limitsAS128MiB,
CPU1/FSize0/FD32; finiteinput/outputfacts. Two requestowned leases retainactivechild aftercaller
cancel, deadlinekill/reap before reuse; submissionfailure and childexitrace fixes included.

28focused tests pass,1Linuxactualworker test skippedlocally. Includes validfilters/colors,
metadata/truncation/excessdeflate/CRC/secondstream/headerfragment, capacity/cancel/deadline,
submissionfailure/pipefailure/stdoutoverflow/wrongmetadata/exitrace. Latestfullsuitepending.

Direct Linux near-maximum worker measurement (local-only `measurements/output-png-linux-near-max.json`):
8×100,1027053B PNG/4195328Bexpanded,syntheticproviderwait+realchild,networkdisabled512MiB/2CPU:
98valid702capacitybusy, sampledparent+childRSSgrowth36528128B,maxloop1.94ms,request69.23ms.
Cgrouppeak51556352B differsfromsampledsum70496256Bdueaccounting/share scope; neitheris asserted
sameabsolutepeak. Benchmarkimageprecededlatestparser/leasefixes; fixedimageverificationpending.
This doesnot provefullHTTPadmission/accounting/output/combinedcaps or exact1048576Bwirelimit.

Remaining: API-owned precreditlease/readiness; native/publicartifactconversion, typedfullimage
estimate/settlement andhardIPM quota; SDK/HTTP/lifecycle/redaction/resource/fullquality/deepreview;
exactmodelpaidlivegate undernewauthorization. Parentgoal staysactive/incomplete.

Latesthelper checkpoint1231passed/88.87%coverage,3Linuxskips,15Docker/Azuritedeselected;
Ruff/format/mypy pass. Rebuiltfixedimage actualLinuxchildinspection passes. Delayedspawn and
repeatedcaller-cancel regression retainsbusy slotpastdeadlineuntilspawn/kill/reap completes.
Scopedrealworkerresource artifact remainsnearcap andprecedingimageversion; notfullHTTPevidence.

Unattachedcredit helper now returnsfulltypedinputUTF8/media + serverTOTALoutputbound×textprice
+ separateimagepriceceiling; billablehelperretainsentirereserve.13focusedtests coverfreefinite
TPM,invalidbounds/missingprice/nonfinite/booleanprice,conflictingpublicceiling andinvalidinput.
API/profile/nativeartifact/accountingintegration remainsPlanned; noenablement fromhelpers.

## Gated HTTP integration checkpoint (2026-10-06)

**Partially implemented**: native request modality mapping, standard ordered
`image_generation_call` composition, metadata/usage preservation, server-owned total-output
bound, full typed estimate on every billable outcome, shared-project RPM/IPM/input-TPM
prerequisites and independent pre-admission output leases are connected. Settings still
unconditionally rejects `image_output`; there is no operator enablement bypass. Synthetic tests
mutate their own settings only. Azure image-tool pass-through remains unchanged.

Actual worker readiness uses the same request slot before quota/credit admission and is also
checked by health readiness. Invalid semantics reject before acquiring a slot. Known usage
updates input quota without reducing image cost. Worker errors, timeout and cancellation retain
full reserve; confirmed validation 4xx refund; ambiguous 5xx charge. No retry follows artifact
validation failure. Scoped independent review cleared Critical/Major findings after correcting
Azure estimator interception, worker OS-error handling and semantic-before-worker admission.

Latest full local checkpoint: 1291 passed, 3 Linux-only skips, 15 Docker/Azurite deselected,
88.95% aggregate coverage. Ruff/format/mypy (56 source files) pass. Isolated Docker build and
health check passed; Sonar script absent. Existing Azurite evidence predates these feature-local
changes. No live generated image inference or production changes.

A late-invalid HTTP run exposed failed-task traceback retention: sampled parent+children RSS
increment160837632B exceeded128MiB. Deleting completed task/coroutine references in the awaiting
frame removes the cycle; gc-disabled weakref regression through actual worker orchestration
proves immediate artifact release and slot reuse. Independent review confirms cancellation
still retains child ownership through kill/reap.

Repeated valid runs in a single ASGI server/client process exceeded128MiB when each caller
retained its previous parsed image while starting the next request. The harness now explicitly
releases consumed output before the next request; this scope must be preserved when interpreting
results. Client-held artifacts are not covered by server output leases. Primitive settlement
callbacks also avoid capturing large Responses bodies. Both historical failures remain recorded.

Remaining gates: exact1048576B PNG limit and maximum enabled combined input bounds, mixed global
capacities/blocked downstream delivery/disconnect/redaction audit, final Docker/full review/docs,
exact-model native codec/thinking/pricing compatibility. Zero paid-spend authorization precludes
paid-only generated-image live evidence. Generated audio, signed-state final gates and parent
plan completion remain pending.

Latest network-disabled Linux HTTP8×100 results, with consumed-output clients:

| Workload | Provider outcomes | Preadmission503 | Sampled incremental parent+children RSS | Max loop delay |
| --- | --- | --- | --- | --- |
| Near-limit output (local-only `measurements/http-linux-valid-consumed.json`) |81completed200 |719 |109969408B |36.07ms |
| Late-invalid output (local-only `measurements/http-linux-late-invalid-consumed.json`) |94billable502 |706 |103583744B |18.75ms |
| Exact1048576B output (local-only `measurements/http-linux-exact-output.json`) |91completed200 |709 |108965888B |37.16ms |
| Input/output combination (local-only `measurements/http-linux-combined-consumed.json`) |17completed200 |783 |116994048B |33.71ms |

Each run returnedzero inflight credit and bounded expected artifacts/errors. Combination input
used885910decodedB of1048576B allowed and two384×384PNGs; it is not full aggregate-cap evidence.
Exact output fixture uses finite zero-length stored DEFLATE blocks inside one zlibstream;
actual parser and child validate unchanged fixed expansion. Resource image plus read-only latest
source mount recorded; final rebuilt-image verification remains separate. Cgroup and sampled
sumRSS use different accounting and are not interchangeable absolute peaks.

## Reviewed weighted combined admission (2026-10-06)

Exact input1048576B plus output1048576B with two admitted requests exceeded128MiB incremental
RSS:161935360B. Independently reviewed amendment now reserves both output units for requests in
any inline-image-enabled output pool (even text-only auto), limiting that pool to one admitted
request. Output-only pools retain two concurrent one-unit leases. Atomic acquire rollback and
released-flag/multi-release transactions share a threading lock. Weighted cancellation retains
both units through child cleanup; mixed contention/double-close/thread races tested.

Exact combined weighted result (local-only `measurements/http-linux-exact-combined-weighted.json`):8×100,
19completed200/781preadmission503,119824384B sampled RSS increment,40.12ms max loop delay,
zero inflight. Both exact wire limits exercised. Additional late-invalid/mixed capacity and
final review remain required; startup gate stays closed. This amendment reduces admitted
concurrency, not payload caps or billing reservations.

Weighted exact combined late-invalid also passed:47billable502/753preadmission503,
104865792B sampledRSS increment,37.15ms loopdelay,zero inflight,
artifact (local-only `measurements/http-linux-exact-combined-weighted-invalid.json`). Weighted implementation
independent review cleared Critical/Major;39focusedpassed1Linuxskip. Latest full1300passed,
3Linuxskips,15Docker/Azuritedeselected,88.99%coverage.

Mixed output-only one-unit/combined two-unit exact-cap pools passed shared capacity:
22completed200/778preadmission503,97488896B RSS increment,18.37ms loopdelay,zero inflight,
artifact (local-only `measurements/http-linux-mixed-weighted.json`). Synthetic sameproject aliasuses same
credit/quota group. No claims about fairness or other media/state capacity arise from this run.

Final weighted build/synthetic Docker health test passed. Ruff/format/mypy and diff whitespace
checks pass. Changed documentation and parent-plan relative links:297checked,none missing.
Repository-wide link scan additionally found39 preexisting unrelated historical-plan broken
links; these do not justify claiming all repository links valid. Slow generated-response delivery
ownership amendment is now under review and must be closed before local enablement.

## Actual downstream delivery ownership (2026-10-06)

Independent review rejected a route Response wrapper because BaseHTTPMiddleware can drain its
body before final network sending. Revised reviewed implementation installs a pure ASGI user
middleware outside both existing HTTP middleware layers. Private server-owned state carries
lease/deadline only after routing/settlement succeeds. Actual response-start/body sends are
bounded by the immutable original reservation deadline; outer finally closes weighted lease
on send completion, cancellation or failure. No replacement response/retry after sending begins.

Actual main.app stack tests pass blockedstart/body×timeout/cancellation: weightedcapacity stays
busy while send blocks, releases afterward, only oneproviderdispatch. SDK output unchanged.
Bare-router resource harness has no outer delivery marker and closes in route finally; it proves
HTTP/worker/admission resources but does not substitute for actual main.app delivery evidence.
33focused owner/SDKHTTP tests pass; fullsuite/finalreview pending after this increment.

Independent outerdelivery review cleared Critical/Major:46passed1Linuxskip. Actual stack
blocked sends now additionally assert fulltyped billabledebit and zeroinflight aftertimeout/
cancellation; delivery cleanup doesnot alterprior settlement. Finalfull/Docker pending.

Actual blocked-start cancellation initially leaked existing middleware request-drain accounting,
causing full-suite shutdown to wait30seconds. Independently reviewed feature-local correction
transfers one drain decrement callback after successful image response to the same outer owner;
ordinary/SSE tracking is unchanged. Outer finalization detaches callback before awaits and uses
local AnyIO shielding plus protected cleanup. Actualstack fourblockedcases now assertcounter0,
full image reserve billed,zero inflight. Owner regressions prove alreadycancelledAnyIO and
repeatedTaskcancel cleanup executesexactlyonce.33focused stack/owner tests pass, plus9owner
regressions; final verification below when complete. No startup enablement follows these fixes.

Latest final local verification:1313passed,3Linux-onlyskips,15Docker/Azuritedeselected,
89.08%aggregate coverage; Ruff/format/mypy57sourcefiles anddiffwhitespace pass. Added normal
SDK success and semantic422counterzero assertions pass26HTTPtests. Changed/planlink288checked,
none missing (separate broader earlier297scan includedadditionalnewdocs). Sonar script absent.
Generated-image startup gate remains unconditional; exact-model paid/live evidence and larger
parent modalities/state gates remain open.

Final drain-corrected checkpoint1313passed,89.08%coverage,3Linux-onlyskips,
15Docker/Azuritedeselected; suite returns11.84seconds (previous drainleak41.79seconds).
Final Docker build/synthetichealth passed21.54seconds. Independent drainreview cleared35focused
owner/SDKHTTPtests; noCritical/Majorfinding. No livegeneratedimagecalls. Startupgateclosed.
