# Evidence

**Planned**,2026-10-06. Concrete [design](design.md) submitted for independent preimplementation
review. Official Google native/speech references read; pinned OpenAI2.8.1 output message accepts
text/refusal only, motivating explicit versioned root extension. No audiooutput code, inference,
credential changes, live evidence or production enablement.

Preimplementation bounded SDK probe confirms Response.model_validate retains version1rootcarrier
losslessly through model_extra/model_dump with ordinaryoutput[]; independent actualSDKmocktransport
create(extra_body) probe also confirmed request/outputcarrier preservation. This is synthetic
schema evidence only, not native transport/codec/live compatibility. Review amendments tighten
input4096UTF8bytes/instructions1024,700000BresponseJSON,explicitomit/disablezerothinkingpolicy,
audioonlynativeadapter,noPNGworker,2outputunits and24koutputnotreplayableas16kinput. Final
independent design clearance pending.

Reviewed concrete design cleared for gated code after finite intake/envelope/thinking/pricing/
replay amendments. Independently read native reference establishes documented AUDIO_WAV/INLINE/
sampleRate and prebuiltVoiceConfig.voiceName fields; exactmodelsremainunverified.

Finite generatedWAV parser and request/profile helpers implemented unattached: mono24kHz16bit,
exactRIFF/fmt16/data,<=480044B/10seconds, canonicalbase64. Explicitaudioonlyprofile/voicelist,
thinkingomit/disable_zeroaffirmation and price/quota dimensions required. Stored/replicated voice
prefixes rejected by prebuiltASCII grammar. Settingsunconditionallyrejectsaudio_output; noadapter/
API/credit/runtimeenabled.40focusedparser/config/request tests pass; fullsuitepending. SDKcarrier
probe syntheticonly. Runtime/resource/billing/lifecycle/live remain pending.

Unattached generated-audio adapter added with exactAUDIO_WAV/INLINE/24k/prebuiltvoice native
mapping, explicitomit/disablezero thinkingpolicy, strictnativeenvelope/state/usage firstpass,
onecanonicalWAV output and version1rootcarrier. STOPrequiresartifact,MAX_TOKENSdiscards validated
binary,refusalordinarysafeoutcome, no fabricatedtranscript/audiooutputitem. SDKResponse strict
validation consumescarrier/metadata/usage andcachedtokens.13focused tests pass; independentcode
review pending. Factory/API/credit/sharedquota integration stillabsent, startupgate remains.

Independent unattachedadapter/credit review cleared27tests after fixing malformed `data:null`
being confusedwith absentartifact in MAX_TOKENS/SAFETY responses. Explicitnonemptystring/
encodedbound firstpass and blockedartifactfinish reject beforedecode;20adapterregressionspass.
Credit helper reserves UTF8input/instructions+64framing, serverTOTALoutputbound and10seconds×
separateconfiguredsecondsprice; seven testsverifymissing/conflict/freefinite dimensions.
No generic outputusage repricing permitted once integrated. Pool/projectquota validator added
understartupgate; explicitgroups,RPM<=ceiling/inputTPM,identicalnativeprofiles,separateprice and
nonmeteredzeroprice/noemergencyfallback required. API/factory/forwardingintegration pending.

Gatedintegration added: nativeaudiofactory/API strictsemanticvalidation/TOTALfill and2outputunit
admission withoutPNGworker, pureWAVreadiness, decodedJSON700000B boundedforwarding andstrictaudio
projection. Allbillableoutcomes retainfullseconds/TOTAL/inputtypedestimate, knownusageinputTPM
only; sameouterASGIdelivery/drainowner aftersuccessfulsettlement.10actualSDKHTTP tests passed
carrier/base64/metadata/billing/refusalMAXinvalid/noegress/responsebound. AddedprojectTPM/capacity
andprovider4xxrefund/ambiguous5xx tests; fullsuitepending. Startupgateunconditional; noaudioruntime
operatorenablement/live/productionwrite. Independentintegrationreviewpending.

Actualaudio middleware delivery tests pass blockedstart/body×cancel/deadline, holding both
capacityunits until actualsend completes/fails, preservingfullbillabledebit andzeroinflight/
draincounter.19SDKHTTPtests include429failoverwithidenticalnativebody/singleownedlease and
freshprojectadmission; rejectedprojectrefund/acceptedprojectfullreserve correct. Fullcheckpoint
beforelatestlifecycle1395passed/89.17%,3Linuxskips,15Docker/Azuritedeselected. Linuxresource,
prebodycancel/finalquality/deepreview/live gates remain open.

2026-10-06 resource/lifecycle continuation: the Python3.12 Docker build passed. With network
none,512MiB/2CPUs and8×100 calls, exact480044B WAV output passed at10,567,680B sampled aggregate
RSS increment,30successful/770busy; malformed final data-size header passed at9,900,032B,
36safe502/764busy. Both retained full expected typed debit and zero in-flight reservations.
Artifacts: [maximum](measurements-max.json), [invalid](measurements-invalid.json).
The bare route harness includes actual bounded forwarding/parser/admission/settlement and
clients that release consumed output. It does not claim outer delivery-owner verification;
actual application blocked-start/body cancellation/deadline tests provide that separate evidence.

Mixed exact PNG/WAV run stayed below128MiB increment (107,053,056B), with1WAV/72PNG successes,
but failed the new independent per-partition debit check because the synthetic backend copy
retained the first backend's credit_group. This is a fixture defect, not evidence of passing
mixed settlement. Preserved [failed artifact](measurements-mixed-partition-failed.json).
Harness now gives the second backend its own credit group/allowance and requires positive
admission and correct outcome/debit/in-flight state for every pool. Independent reviewer approved
this strengthened measurement design; its corrected Linux repeat remains unexecuted.
Automatic approval review failed with an external credit-capacity503 before Docker execution;
this was a review-service failure, not an unsafe-action determination. Reviewer session also
failed with the same503; final independent review remains pending. No approval bypass attempted.

23focused lifecycle/SDKHTTP tests pass, including missing/known usage input-quota settlement,
log marker absence, cancellation/deadline during unread provider body (one dispatch, connection
closed, full reserve), and postbilling outer delivery/drain. Ruff and mypy61sourcefiles pass;
final full-suite checkpoint follows below. Settings audio_output gate remains unconditional.
No credentials loaded or provider inference requests made in this continuation.

Final local checkpoint:1404passed,3Linux-onlyskips,15Docker/Azuritedeselected,89.17%coverage
(12.43seconds). Ruff check/format514files and mypy61sourcefiles passed; diff whitespace and
90relative links in the increment/canonical changed docs passed. Sonar script absent.
The previously built Python3.12 image includes the runtime changes; no subsequent runtime edits.
Final independent deep review and corrected Linux mixed measurement remain pending after the
external approval/reviewer service503. Existing Table/Azurite gates are not reestablished by this
memory-only suite; no production/distributed-state claim is made.

A macOS synthetic bookkeeping-only run validates the corrected two credit partitions, known
input-quota counts and released quota reservations for admitted WAV requests, plus the
untouched second credit partition: [fixture check](fixture-bookkeeping-local.json). This disables Linux
RSS sampling explicitly and provides no resource/operational evidence. The harness now also
checks shared project requests/input tokens and empty quota reservations. The local check
admitted no PNG requests on macOS, so it does not establish mixed admission or image settlement;
those strengthened
checks require the pending Linux rerun. Retained earlier max/invalid artifacts predate those
additional quota assertions; they establish their recorded scope only.

Approval service recovered on2026-10-06. Corrected mixed Linux run passed with88,915,968B
aggregate RSS increment,1WAV/58PNGsuccesses and741busy; independent debit, input quota and no
quota reservations checks pass. [Artifact](measurements-mixed.json). Malformed-WAV/valid-PNG
mixed run passed at103,706,624B,1safeWAV502/67PNGsuccesses/732busy,
[artifact](measurements-mixed-invalid.json). WAV invalidity is a semantic data-size header
mismatch detected after bounded wire/base64 intake; PCM samples are not scanned. The artifact's
historical `late-invalid` workload label does not imply an expensive late sample scan.
Nonqueued admission provides no fairness guarantee; few audio admissions establish this finite
fixture's coexistence only. These measurements do not establish signed/PDF/input-media combined
resource behavior. The earlier service failure is resolved for these commands; failed evidence
remains retained.

Independent final deep review ran100focusedtests successfully and found no remainingCritical/
Major issues in finite native output, SDKcarrier, separate pricing/quota, body/usage/settlement,
cancellation/failover and outer delivery/drain. Reviewer requested explicit zero active credit
reservation counts in addition to zero dollar in-flight; strengthened harness rerun in progress.
Exact-model live/free-tier/codec evidence and startup enablement remain unverified.

Final strengthened mixed measurement passed:4WAV/34PNGsuccesses,762busy,78,069,760B aggregate
RSS increment,38projectrequests/152knowninputtokens; both credit partitions active_reservations0,
inflight0 and exact full typed debit. [Artifact](measurements-mixed-reservations.json).
This closes the scoped mixed-output resource bookkeeping finding. Local runtime code checkpoint
remains1404tests/89.17%; subsequent verification-only signed-process tests lift the full suite
to1406passed/89.17%. No audio runtime changes or live inference since the cleared review.

Required Docker build/synthetic health smoke passed4.76sec;100incrementrelative links pass.
Generated-audio local code/client/resource/review checklist is closed. Exact-model native
voice/codec/thinking/free-tier pricing and bounded live outcomes remain the only enablement
prerequisites for this finite profile; parentcombinedmedia/signature requirements remain separate.
