# Evidence

**Planned**. Aggregate offloadedparse Linux67.25ms loopdelay/rawparse28.22ms; no runtimeeditsbefore
independentreview. No providertraffic.

Original complete-string regex rejected before code: independent2MiB runs measured up to657MiB
processpeak and73ms. Revised deterministic str.find/disjointsegment scan proposed; no runtime
change until review.

**Partially implemented**,2026-10-06. Independent revised design review approved deterministic
constant structuralregex plus str.find/disjointsegment backslashparity. Reviewer compared147,257
exhaustive/random malformed/escaped/Unicode cases against previous depthscanner; detectionmatched.
No complete-string regex entered runtime.92focused schema/client/HTTP tests passed, including
2MiBplaintext/backslashes and600kescapedquotes, exact32depth, malformed/duplicate/nonfinite,
2000seeded validstructuralstrings. Full/Docker/Linuxmeasurement and runtime review in progress.
Quote-heavy worstcase latency remains unverified; signedstartup gate retained.

Runtime deepreview cleared noCritical/Major. Independent147,265 malformed/valid/depth/node fixtures
matched priorparser returnvalues and exceptionclasses/messages. Local maximalstring fullparser
measurement:2MiBplaintext1.61ms,escapedslash7.64ms,600kescapedquotes52ms; processpeak approximately
53MiB. Disjointsegment slicing andrstrip have finite linear memory, with possible4byteUnicode
storage; no exact1×inputbyte allocationclaim. Quoteheavyglobal latency remainspending.
Fullsuite1074passed,2Linux-onlyskips,15Docker/Azurite deselected;88.79%coverage, Ruff/format/mypy
passed. Dockerbuild/health and Linuxaggregate measurement inprogress.

Docker build/health passed. Network-disabled Linux512MiB/2CPU aggregate signed replay8×100 now
records86successes/714preadmission503, zero postdispatchfailures;36,544,512incrementalRSSbytes,
19.90ms maxloopdelay,173.28ms maxrequest, rawparse0.47ms andsnapshotencoding1.82ms. The same
fixture previouslyhad67–77ms loopdelays. This closes the specific aggregate signature latency
regression; quote-heavy worstcases and maximumcombined media/state remain separategates.
Fullsuite1074passed/88.79%coverage, Ruffwholetree/format/mypy/deepreview passed. No providercalls.

2026-10-06 hybrid escaped-run optimization implemented after independent design review.
Ordinary strings retain str.find/parity; dense escaped runs use anchored disjoint alternatives
with finite256atomregex state and linearforwardprogress. Originalstrictjsondecoder/duplicate/
nonfinite/depth/node/byte semantics remain.31focuseddepth tests and160scanner/state/signedHTTP
regressions pass. Independent99,531differentialprototypecases matched originalguard.

Current-source Linux microbenchmark (local-only `quote-run-linux.json`), networknone512MiB/2CPU:
2,000,002Bplain2.44ms,quotes22.13ms,backslashes7.96ms,oddbackslashquote8.17ms;
1,200,002BUnicodeescapedstructural21.41ms, all lossless,peakRSS57420KiB. This is scanner evidence
only. Earlier source-mounted HTTP probes inadvertently imported installed prechangepackage;
current-source runs explicitlysetPYTHONPATH=/app/src. Their failures remain recorded but do not
measure the newscanner. OnecallerSDKprobe43.31msloop/43,245,568BRSS passes; fullmaximumhistory
SDK8×100failsRSS152,846,336B/loop158.35ms despite26validcompletions/774preadmissionbusy and
correctbilling/cleanup. Do not claim fullresourcegate from prototype/microbenchmark/onecaller.
Further profiling/review needed before enabledprofile claims; startup remains closed.

Final scoped hybrid deepreviewclear: noCritical/Major; independent167focusedJSON/intake/state/
signedHTTPtests pass. Full1422passed/89.18%,3Linuxskips,15Docker/Azuritedeselected,15.42sec;
Ruffcheck/format522files,mypy61sourcefiles pass. FullSDK125itemloadfailure remains authoritative;
next verification-only attribution will measure synchronous router/SDK/mockprovider/harness
stages and separate preencodedHTTP/decode scope, preserving failed originalSDK evidence.
No additional runtime changes, payload/capacity/timeouts or enabledprofiles proposed.

Current runtime Docker build/synthetichealth also passed27.92sec. Independent implementation
review additionallyran39,531valid/malformed differentialcases with no semanticmismatch. This
closes scopedoptimizationcodeverification; fullquote/historyresourcegate remainsfailed. See
[next attribution design](../signed-continuation/resource-attribution-design.md).

The separately reviewed [standard decoder string scanner](decoder-string-design.md) replaces
only manual quote/backslash skipping in the structural-depth prescan. Strict `scanstring` advances
to the end of a string; its temporary decoded string is immediately deleted before final strict
JSON decoding. Byte, container/value depth, duplicate, finite and node limits remain unchanged.
Mixed Unicode may allocate approximately four times input bytes plus overhead; this is bounded
and explicitly documented rather than assumed equal to UTF-8 bytes. Forty-two scanner tests and
141 JSON/canonical/history/actual SDK signed tests pass locally, including malformed Unicode,
maximum mixed-wide strings and 33 empty containers. Final deep/full/Linux/resource checks pending.

Final scanner review cleared 180 focused tests (one Linux PDF platform skip) and 44,531
implemented old/new differential cases with no Critical/Major findings. Full 1,485 tests pass,
three platform skips, 15 Docker/Azurite deselected, 89.26% coverage; Ruff/format (535 files),
mypy (61 source files), whitespace pass. A narrowly scoped typeshed attr-defined annotation is
required because its json.decoder stub omits the CPython scanstring primitive. Linux Python3.12
passes all 141 scanner/canonical/history/actual SDK signed tests. Runtime Docker check pending.
