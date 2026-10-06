# Signed continuation evidence

**Planned**. Templates copied before drafting2026-10-05. No runtime signed capability enabled.
Native Part reference and Thinking guide inspected; Interactions protocol is explicitly excluded.
Actual OpenAI2.8.1 nonstream model validation and streamed ResponseStreamState synthetic terminal
fixtures retain foundry_provider_state under model_dump(exclude_none=True). This is preliminary
carrier evidence, not complete HTTP/client/native signature validation. Independent review pending.

Independent design review passed2026-10-05 with no remaining Critical/Major findings. Resolved
ambiguous native SSE Part identity by explicit signed public streaming over native nonstream
generateContent; repeated-carrier/wire/replay limits, exact projection/hash framing, key/clock
rotation rules, signature quota accounting and STOP-only seal admission. Approval covers
default-off reversible implementation; exact-model/live enablement remains separate.
cryptography50.0.2 installed locally; Fernet source inspected for authentication-before-decryption,
clock/TTL behavior and32byte keys. Pin this reviewed dependency for the codec increment.

## Codec increment

**Partially implemented**: unattached pure Fernet/key-ring/binding/turn and length-framed
canonical digest primitives added; runtime profiles remain disabled. Independent codec review
passed after malformed authenticated shape, canonical key-alias, strict JSON key, expiry/time
and history position bounds were corrected.83 focused codec tests passed; bounded walker also
caps16384nodes before serialization. Separate secret configuration model rejects scope/envelope
key reuse and redacts serialized/error representations;16 focused key-configuration tests pass.
Full suite after codec:884 passed,2Linux skips,15deselected,88.19% coverage; current Ruff/mypy pass.
Docker rebuild with pinned cryptography50.0.2 passed. Caller scope/config integration, aggregate
state preparation/pinned routing/native signing/HTTP SDK/resource/live gates remain required.

## Secret configuration and authentication increment

Optional secret-only FOUNDRY_GOOGLE_STATE_KEYS_JSON now validates bounded duplicate-free JSON,
strict canonical32byte keys, distinct scope/envelope values and owned immutable decrypt-key
mapping. Settings serialization/representation exclude secret configuration and validation
string errors hide inputs. Raw ValidationError.errors()/json() must never be logged.
Successful authentication derives domain-separated nonpublic caller scope and retains the
immutable key-configuration snapshot for later intake-generation matching; user request IDs
do not affect scope. No signed profile/adapter is enabled by configured keys. Independent
config/auth review passed with no Critical/Major findings. Full suite909passed,2Linux skips,
15deselected,88.07%coverage; Ruff/mypy pass. Latest mapping/nonfinite loader refinements have
focused verification; next full validation accompanies continuation integration.

Unattached history projection/carrier helpers:26focused tests passed,97.53%module coverage.
Projection strips carriers only at assistant/call item roots, preserves argument/text/media
data and creates owned snapshots. Repeated occurrence/unique-turn limits run before decrypt.
Independent helper review pending; adapter semantic validation and complete prepared state
remain required. Latest configuration/auth Docker build passed.

Current signed primitives focused suite:139passed; history helper95.88%,codec97.52%,secret
configuration92.98% module coverage. This focused run intentionally reports whole-repository
coverage low because it excludes unrelated tests; full suite is the overall coverage gate.
Safe surrogate handling, exact generation-context defaults and canonical serialized carrier
occurrence bytes now included. No signed profile/native/HTTP state path enabled.

Latest history full suite940passed,2Linux skips,15deselected,88.37%; Docker history image
rebuilt successfully. Unattached PreparedContinuation now verifies contiguous item IDs/turn
positions/prefix digests and same configured backend binding, captures request digest before
awaits and tracks original signature input estimate.10focused tests pass95.92%module coverage.
Codec decrypts each unique token once before matching authenticated configured bindings.
Part reconstruction, deadlines, profile routing, seal admission and public/native HTTP remain
required; helper review in progress.

Prepared-continuation full checkpoint950passed,2Linux skips,15deselected,88.40%coverage.
Subsequent exact unsigned native Part reconstruction/digest checks and malformed object-args
fixtures pass13focused continuation tests; combined history/continuation44passed. Final
independent review and full/build verification follows those latest helper edits.

Current pure sealing helper verifies complete projected turn/Part digests and prospective
full-history replay limits (tool-result byte/item headroom and complete carrier occurrence
budgets) before returning owned finalized items.18focused continuation tests pass95.35%.
Latest full suite958passed,2Linux skips,15deselected,88.43%coverage; Ruff/format/mypy pass.
Sealing review and Docker rebuild in progress; no signed profile/runtime path enabled.

Independent sealing-helper review passed with no Critical/Major findings; reviewer additionally
exercised adjacent text Parts, maximum signatures/repeated wrappers and seventeenth-turn
rejection. Full signed lifecycle/profile/native integration remains required.257 changed/new
relative documentation links resolve; diff whitespace clean.

Sealing helper independent review passed. Request-owned SealContext/configuration fingerprint
helper added with8focused tests; binds credential HMAC, endpoint/model/surface/features/limits,
project identity, quotas/pricing and generation context, excluding raw credentials. Independent
review pending. These are unattached primitives; signed runtime remains disabled.

SealContext final review passed after common profile/one-context validation and signed256backend
work cap;10focused tests verify those bounds. Explicit native thinkingConfig/TEXT modality
fingerprint added. Signed profile/pool configuration schema now reserves sealed_native and
bound_history_required plus explicit thinking/signature/price ceilings, but startup rejects
all bound-history pools until the runtime integration is complete. Existing110config/native/
tool tests and23state-config tests pass. No partial signed feature can be enabled.

One unrelated full-suite Table concurrency fixture failed then passed in isolation. Inspection
found existing id(settings)-only cache can skip changed configuration when temporary old Settings
objects are collected and IDs reused. Minimal actual-object identity retention fix is under
independent review; no storage schema or production change is proposed.

Signed schema/helpers/credit identity final checkpoint:971 full tests passed,2Linux skips,
15deselected,88.49%coverage. Current Ruff/format/mypy pass. State-profile startup hard gate
remains until native signing and admission wiring complete. Configuration fingerprint binds
concrete native thinking/TEXT settings; common signed profile context is validated once.
Credit settings identity fix independently reviewed and tested; see [evidence](../settings-identity/evidence.md).

Unattached GoogleSignedAdapter added;5initial focused tests pass85.06%module coverage, covering
lossless adjacent native text/call signature association and known thought usage on safe state
failures. Subsequent negotiation/missing-owned-facts tests added. Adapter independent review
in progress; no runtime signed profile enabled. Existing full971/Azurite14/Docker checkpoint
precedes this latest adapter increment.

Signed adapter independent re-review passed after fixing candidate/content types, null/empty
signatures, whitespace un-replayable Parts, separate signed native turn boundaries, valid
prompt-block refusal and prospective retained signature ceiling.21focused adapter/decoder
tests now pass, including actual OpenAI2.8.1 streamed final item state/model_dump/full replay.
The new decoder buffers bounded native generateContent JSON and emits no events until full
translation/sealing; safe conversion failure retains known thought usage. Stream decoder
independent review is in progress; startup remains disabled pending routing/lifecycle/accounting.

Signed complete-response stream checkpoint992full tests passed,2Linux skips,15deselected,
88.63%coverage; Docker signed-adapter image build passed. Subsequent per-event/aggregate
construction bounds, raw-buffer cleanup, safe failure event and signed EOF-prefetch handling
added with22focused tests. The SDK accumulates completed STOP snapshots; it does not set its
_completed_response for incomplete terminals, which are asserted against raw terminal payload.
No signed profile is enabled; final stream/forwarding review and runtime integration remain.

## In-flight runtime integration checkpoint, 2026-10-05

**Partially implemented**. Startup still rejects bound-history pools. API now owns sealing
context and continuation preparation, checks authenticated key-snapshot identity, validates
ordinary history/media semantics before decrypting, and passes immutable state through
selection and forwarding. Replay pins the backend; both emergency cooldown/quota fallback
and retry/failover are disabled for prepared continuations. Configured signed adapter setup
failure rejects before admission. Signed public streams explicitly request native generateContent.

Every signed request, including fresh history, binds its full body snapshot. Immediately before
native URL/auth capture, forwarding verifies transport settings identity, current key snapshot,
and backend fingerprint. Signed estimates remove only allowed public carriers, use UTF-8
prompt ceilings for text-only requests too, and add server signature/thinking bounds.
Native candidate+thought usage survives billable sealing failure and settles once.

Independent runtime review identified and fixes addressed admission fall-through, emergency
fallback, fresh-body mutation, transport config mutation, and text-only estimates. Raw signed
intake is constrained to at most 2 MiB by startup validation. Concurrency/deadline checks,
maximum-state measurements and remaining cancellation/delivery cases still gate enablement.

- 15 new HTTP tests pass: nonstream/stream signed text replay, repeated request accounting,
  dropped/modified/caller/configuration state, pinned 429/cooldown with emergency mode,
  billable signature failure with known quota usage, fresh-body/backend mutation before dispatch,
  and UTF-8 token bounds. Tests explicitly own otherwise startup-disabled profiles.
- Full local checkpoint: **1011 passed, 2 Linux-only skips, 15 Docker/Azurite deselected**;
  **88.66% coverage**. Ruff, formatting, and mypy passed.
- Initial full suite's Docker check was blocked by sandbox socket access; rerun requested
  through the permitted local Docker escalation. No provider calls or secret reads.

## Bounded intake checkpoint

**Partially implemented**, startup gate retained. Signed preparation acquires one of two global
nonqueued slots before owning the nested JSON snapshot. It runs finite ordinary validation,
context/fingerprints and token decryption in a shielded executor task. Worker finally releases
the slot; submission/snapshot failure releases once; abandoned exceptions are consumed.
Deadline checks run between history items, decryptions and configured backend fingerprints.
Caller timeout/cancellation leaves the worker owning its slot until actual completion.

Five intake tests cover saturation before snapshot, timeout/cancellation with held slots,
exception/submission/snapshot failure and recovery. Latest full local checkpoint:
**1016 passed, 2 Linux-only skips, 15 Docker/Azurite deselected, 88.77% coverage**;
Ruff/format/mypy passed. Earlier runtime Docker build/health and 14 actual local Azurite tests
passed; updated intake Docker revalidation is in progress.

Synthetic macOS full HTTP experiments (8 callers × 100 attempts) are saved under
[measurements](measurements/). These are preliminary measurements, not enablement evidence:
maximum individual-signature replay had 531 successful responses/269 saturation failures,
23,691,264 incremental RSS bytes and 36.22 ms maximum loop delay; 120,000-byte instructions
replay had 600 successes/200 saturation failures, 32,833,536 incremental RSS bytes and
**73.37 ms maximum loop delay**, requiring further full-path work before claiming the event-loop
gate. A 64-Part output exceeded the repeated-envelope limit and was safely rejected; its invalid
workload resets synthetic backend cooldown only in the harness to inspect repeated failures.
That run saw 122 billable validation failures/678 saturation or cooldown failures, 10,059,776
incremental RSS bytes and 13.80 ms loop delay. It does not prove accepted 64-Part replay.
No real credentials/providers, no paid traffic. Linux/full-history/repeated-carrier/combined maxima
and timeout/delivery lifecycle measurements remain required.

## Full-path resource refinement in progress

Independent review approved moving finite signed selection validation and request construction
into the same two-slot shielded worker boundary. These stages now run off the event loop;
ordinary adapters retain existing behavior. Busy construction returns an explicit pre-dispatch
error so admission cleanup releases quota/credit. Focused intake/HTTP tests (20) passed.

Output translation and signed decoder finalization remain synchronous. Review identified that
moving decoder.finish directly into a timed-out worker would race late worker mutation against
transport failure/usage delivery. A separately owned immutable finalize result is required before
that stage can be moved safely. No claim is made that the measured 73 ms event-loop gate is
resolved; startup remains closed. The benchmark script includes actual API intake, selection,
mock native transport, sealing and nonstream/SSE emission, but does not yet prove every
maximum accepted carrier/history combination or Linux behavior.

## Owned output finalization checkpoint

Signed SSE finalization now captures bounded known native usage, gives a worker a local decoder
clone, and publishes a frozen event/result snapshot only after successful await. Original transport
state remains untouched by a late worker after timeout/cancellation. Publication rejects if a failure
terminal already exists. Tests cover late-worker completion after timeout/cancellation and exact
terminal-event identity on successful publication. Nonstream translation likewise runs bounded,
with known usage captured before submission; saturation/timeout charges known usage or reservation
once, with no retry. Independent lifecycle review cleared these changes within helper scope.

- Latest full local verification: **1019 passed, 2 Linux-only skips, 15 Docker/Azurite deselected**,
  **88.67% coverage**, Ruff/format/mypy passed. Previous 14 actual Azurite tests passed.
- Context experiment after worker-stage changes: loop maximum **29.28 ms**, incremental RSS
  **32,718,848 bytes**, but only70successful/12billable stage failures/718 admission/cooldown
  failures. This is **not a passing enablement benchmark**: throughput/saturation/cooldown behavior
  and maximum valid carrier/history combinations need stronger measurement and design refinement.
- Full objective remains partial: larger images, audio/video input, generated image/audio output,
  exact-model live runner/evidence and final operational gates remain required.

## Request-owned capacity refinement

The two capacity slots now belong to entire signed requests from snapshot/preparation through
validated native generation/sealing. Each bounded worker stage reuses its request's lease;
there is no post-dispatch capacity reacquisition. API finally closes the lease after nonstream
translation or signed stream prefetch; an active abandoned worker retains capacity until actually
finished. Close forbids reuse and concurrent jobs on one lease. Slow-client byte delivery occurs
after sealing and does not retain parser/crypto capacity.

Seven intake/lease tests and17HTTP tests pass, including two admitted requests paused in mock
provider transport, a third rejected before dispatch, both admitted requests completing successfully
(nonstream and SSE), and capacity reuse. Isolated helper import tests uncovered and resolved an
adapter factory/state/schema initialization cycle by loading the signed adapter only when selected.

Preliminary8×100 macOS context measurement now has244successes/556pre-admission503 responses,
**zero post-dispatch stage failures**,38.89ms maximum loop delay and31,326,208 incremental RSS bytes.
This improves lifecycle behavior; maximum accepted state/combined workload Linux evidence and
complete timeout/slow-delivery cases remain gates. It is not live provider evidence.

Signed request leases now acquire before PDF preparation, so rejected third signed callers cannot
start a PDF worker. Focused signed/PDF HTTP verification passed24tests with1Linux-onlyskip.
Latest built image passed Docker build/health. A synthetic network-disabled Linux512MiB/2CPU
context benchmark (8×100,120,000-byte instructions/fullhistory replay, mixed nonstream/SSE)
recorded155successes/645preadmission503 responses, zero502postdispatchfailures,26.04ms maximum
loop delay,36,417,536incremental RSS bytes and241.34ms maximum request latency. This establishes
that specific local workload only; accepted maximum state, repeated carriers and combined PDF
work remain unverified.

Additional network-disabled512MiB/2CPU Linux8×100 workload measurements:
- Individual maximum16KiB signature replay:130successful/670preadmission503;11.28ms maximum
  loop delay,20,029,440incremental RSS bytes,109.43ms maximum request latency.
- Fifteen independently sealed prior turns (new output reaches the16turn cap):145successful/
  655preadmission503;18.37ms loop delay,12,693,504incremental RSS bytes,109.31ms request latency.
- Sixteen repeated carrier occurrences per signed turn, exact16Part replay and new output:
  191successful/609preadmission503;22.20ms loop delay,26,198,016incremental RSS bytes,
  402.28ms request latency. These wrappers are below aggregate wire caps; not maximum bytes.
Each run had zero post-dispatch502 outcomes. Results are saved in measurements; exact aggregate
carrier/signature/wire maxima and signed PDF combinations still require follow-up. Latest full
local verification remains1023passed/88.74%coverage, plus Docker build/health, static checks
and independent lifecycle review. Production and real Google remain untouched.

Actual OpenAI Python2.8.1 AsyncOpenAI HTTP integration passed for both nonstream responses.create
and responses.stream/get_final_response. SDK output model_dump(exclude_none=True) retained each
router provider-state extension; full-history replay through the API restored exact native
thoughtSignature and returned completed.19signedHTTP tests now pass. Dropped-extension rejection
is independently covered. This is synthetic native transport compatibility, not a Google live test.

Final checkpoint for this increment:1025passed,2Linux-onlyskips,15Docker/Azurite deselected;
88.74%coverage. Ruff, formatting, mypy, diff whitespace and255changed/plan relative documentation
links passed. Docker build/health and prior14actualAzurite checks passed within this increment.
Startup gate remains in place; entire plan is still Partially implemented.

## Expiry, key lifecycle and caller tool replay increment

26signedHTTP tests pass. Added exact expiry/no-egress rejection, overlapping decryption-key
rotation and new active-key minting, removed-key revocation, and reconstruction of fresh runtime
objects with store reset in the same process. The latter proves cache-free replay with equivalent
keys/configuration, not actual process/container restart. Authenticated key configuration changed
between authentication and intake returns503 without provider egress.

Signed strict function request→call→caller fixture result→answer now passes using actual OpenAI
Python2.8.1 responses.create and responses.stream/get_final_response over synthetic HTTP.
The streaming helper adds client-only parsed_arguments. The reviewed serializer recipe
`model_dump(exclude_none=True, exclude={"parsed_arguments"})` removes only that top-level helper
field. Exact emitted arguments/IDs/status/carrier remain unchanged. Unfiltered streamed model
output rejects422 before further provider dispatch. No tools execute in the router.

Two additional delivery-generator tests expire before versus after completed terminal handoff;
known candidate/thought usage reaches one credit/quota/metrics/close invocation, and no second
terminal follows completion. This is generator-boundary proof with mocked stores, not an actual
stalled ASGI send/disconnect or durable distributed exactly-once claim.30signedadapter tests pass.

Aggregate-signature Linux experiment used2maximum16KiB signatures per turn,3prior turns with
6repeated carriers/10historyitems, and new2Part output.8×100 yielded139successes/661preadmission503,
zero post-dispatch502,73,560,064incremental RSS bytes and**76.76ms maximum loop delay**. This is
not a passed event-loop gate. Saved artifact records exact fixture dimensions.

Independent review approved moving owned snapshot JSON parsing and pinned request-digest
validation into existing leased workers. Immutable canonical wire bytes are captured under the
lease before the first await; caller-body identity remains checked at selection/build.33focused
HTTP/intake tests passed after these edits. Raw HTTP parsing still runs synchronously; broader
intake changes require a separate evidence-driven design. Startup remains closed.

The original canonical encoder reparsed its JSON internally, so moving only snapshot parsing
was insufficient. Added a bounded encoding-only canonical_wire_bytes for already parsed owned
JSON; it validates key/node/depth/UTF-8/nonfinite/size bounds without reparsing. General
canonical_bytes retains its strict parse validation. Signed capture uses encoding-only bytes,
then strict snapshot parsing runs under the lease. Seven equivalence/unsafe/exact-size tests
and123state/HTTP/intake tests passed. Updated Docker/full checks are in progress.

Two direct ASGI response-wrapper tests block response-start or first-body send against a50ms
absolute reservation deadline. The unstarted path invokes fallback cleanup once; the entered
signed generator settles known usage and closes its context once. This covers actual ASGI send
awaits in DeadlineStreamingResponse, with mocked stores/context and no real TCP disconnect.
32signedadapter tests pass. Updated encoder image Docker build/health passed; aggregate Linux
experiment is rerunning after synchronous parser removal.

After encoder/parser split aggregate replay still sees68.04ms loopdelay,116success684preadmission503,
zero postdispatch failures;82,649,088incremental RSSbytes. A profiled run uses preencoded caller
requests and times router stages: raw_json_parse40.32ms, snapshot_encode9.24ms, loop72.42ms,
123success677preadmission503 and37,928,960incremental RSSbytes. Remaining mainloop rawJSONparse
is established; [separate intake plan](../signed-intake-json/activities.md) awaits independent review.

Latest full local checkpoint1044passed,2Linux-onlyskips,15Docker/Azurite deselected;88.77%coverage.
Ruff/format/mypy passed. UpdatedencoderDocker build/health passed; previous14actualAzurite checks
remain unchanged. Fullscope stillpartial and startup gate remains.

Deterministic JSON scanner closed the specific aggregate replay latency regression: optimized
Linux8×100 yielded86successes/714preadmission503, no502postdispatchfailures;19.90ms maxloop,
rawparse0.47ms and36,544,512incrementalRSSbytes. Earlier67–77ms fixture is retained forcomparison.
Quote-heavymaximum latency remainsunverified and startupgate stillclosed. Latest fullcheckpoint
1074passed/88.79%coverage;Dockerbuild/health, Ruffwholetree/format/mypy and257relative links passed.
Finiteaudioinput decision nowawaitsindependentreview; otherIncrementC directions remainrequired.

Actual fresh-process replay verification added2026-10-06 after independent approval of the
[verification design](process-restart-design.md). Two sequential interpreters independently own
init-only settings, keys, caller binding, ASGI app and memory stores. First child exits and is
reaped before the second starts; a private bounded pipe carries only synthetic SDK output to
its parent. Exact native signature/Part association survives pinnedOpenAI2.8.1 serialization and
replay, each request separately admits and charges known40input/12output tokens (0.00076USD
local estimate), with zero credit/quota reservations and both signed capacityslots released.
Changed-key second child rejects422invalid_provider_state before any provider dispatch.

[Local3.14.7 evidence](process-restart-local.json) and
[Linux3.12.15 evidence](process-restart-linux.json) retain only status/counts/cleanup/PIDs and
scope. Linux uses networknone512MiB/2CPU with a test-only image layer containing pinnedSDK;
initial runtime-image attempt failed before fixture execution because devSDK was absent.
No production image/dependency or runtime changes were required. This proves fresh interpreter
restart through synthetic ASGI/SDK, not a TCP server/container restart, live provider or deployed
key lifecycle. Startupgate remains closed for combined-resource/live requirements.

Independent deep review cleared the harness after fixing pipe-overflow cleanup: bounded readers
are cancelled/joined, killedchildpipes drained without retention, and processreaped before return;
owned cleanup survives repeated cancellation. Reviewer probes1MBstdout/stderr and threecancels
reapedchildin<=0.05seconds/zeropendingtasks. Five retained regressions pass for replay/changedkey/
stdoutoverflow/stderroverflow/cancellation. Final fullquality checkpoint follows below; Ruff518/
mypy61 passed. No secrets, prompts/signatures/media in retained process evidence.

Final verification-only checkpoint:1409passed,3Linux-onlyskips,15Docker/Azuritedeselected,
89.17%coverage (15.38sec), coverageXMLgenerated. Ruffcheck/format518files,mypy61sourcefiles and
whitespace pass. Final revised Linux3.12processfixture rerun passes after pipecleanupreview.
Signed runtime itself unchanged; prior Docker runtime build remains current. Fullsigned gate
stillrequires quote-heavymaximum and combinedstate/media resource evidence plus exactmodellive.

Required Docker build/synthetic health smoke also passed (4.76sec);100changedincrementrelative
links pass. Independent review confirms no remainingCritical/Major for the scoped process
verification. The next [maximum combined resource design](combined-resource-design.md) is under
preimplementation review; this requirement remains unverified and gate stays closed.

Combined-resource design review identified the previous synthetic benchmark's invalid profile:
model_copy bypassed required function_tools and incompatible native_thinking_disabled validation.
The new process harness had inherited that pattern; it now constructs an actual validated
GoogleFeatureProfile(function_tools,sealed_native,thinkingdisabledfalse,budget8,thoughtpricing,
signaturebound100000) and bypasses only the Settings startup gate. Both local3.14/Linux3.12
process artifacts have been regenerated and fivefocusedtests pass2.53sec with this validprofile.
This correction affects verification fixtures only; no runtime code changes. Historical resource
benchmark evidence with invalid copiedprofiles cannot establish supported-profile enablement;
the new combined-resource amendment will replace that gap with actualvalidatedfixtures.

Postvalidated-profile fullcheckpoint1409passed/89.17%,15.29sec; Ruff519files pass. Process
artifacts retain versions3.14.7/3.12.15 and both replay/changedkey cases pass. Remainingcombined
resource design includes exactfeasiblePDF/WAV/AVI/headroom facts from independentreview; no
maximumcombinedpass claimed before actualmeasurements.

Quote-heavy feasible resource harness added after independent approval: validsealedprofile,
exact131072Bcontext,125inputhistoryitems (twooutputParts+nextuser fit128),356616Binputcarriers,
actualSDKwire1584008B and actualcompletedreplay1702704B+393984headroom+256framingfits2MiB;
actualcarrier475536B<=524288. Threeprior2Partturns each32768decoded signaturebytes; this is a
joint feasible maximumquote/history fixture for those selected state dimensions, not every
independentstate/token/turnlimit simultaneously. ActualSDKstreamcompleted+usage+carriers and
nativeoriginalPart/signature replay asserted; no HTTP200-onlysuccessclaim.

[Full current-source Linux measurement](quote-resource-history-linux.json) 8×100,networknone/
512MiB/2CPU:11nonstream/15stream completions,774preadmissionbusy, noinvalidcompletions orretry;
knowncredit/inputquota andzerocredit/quotareservations pass. **Resourcegatefails**152846336BRSS
increment/158.35msloop. [Onecaller current-source probe](quote-resource-current-source-probe.json)
passes43.31msloop/43,245,568BRSS but doesnotcloseconcurrentgate. Previousprobe framingfailure,
oldinstalledpackage probes and original60secloadtimeout remain retained. Harness now checks every
actualnewcarrier/serializedwire/headroom and returns boundedloadtimeout failurefacts.
HybridJSONscanner runtimeoptimization has independentdesignapproval; further implementation
review/profile/clientservercopyeconomics and maximumcombinedPDF/WAV/AVI remain pending.

Scoped hybridimplementationdeepreviewcleared;1422fulltests/89.18%,Ruff522/mypy61pass. Failedfull
quote/historyresourcefixture is still authoritative for actualSDKmixedclient+routerload. Next
reviewedverificationattribution separates SDKserialization, MockProviderJSONdecode and harness
postresponsecanonical checks from synchronous routercriticalsections; preencodedHTTP scope will
be labeled separately and cannot replace the original failedSDKbudget. No gates lifted.
