# Signed maximum and combined media resource verification

**Planned**,2026-10-06. Verification amendment to the reviewed signed/native media contracts;
no new capability or increased limit is proposed. Fresh-process restart now passes; parentT2/T5/T7
still require worst-case quoting and combined state/media resource/lifecycle proof before signed
enablement.

Extend the existing synthetic Linux HTTP benchmark with explicit workload fixtures and robust
invariants. Use deterministic owned synthetic settings, fixed MockTransport destinations,
networknone512MiB/2CPU,8callers×100requests, current two signed slots and PDFworker isolation.
Record exact accepted wire/state/media dimensions and preadmission vs postdispatch outcomes;
measure parent+children RSS (existing parent-only sampler is insufficient for PDF), eventloop
latency and bounded wall time. Cap incremental aggregateRSS128MiB and maxloopdelay50ms, preserving
previous measurements as historical evidence rather than replacing a failed run.

First workload: quote-heavy signed request at accepted context/history bounds plus maximum
allowed carrier aggregate. Seed native signature-bearing responses and retain SDK-serialized
carriers in memory. Construct long permitted text using escapedquotes/backslashes within the
real aggregate wire/body/context limits; derive acceptance from actual intake rather than labels.
Do not claim full maxima merely from a2MiB JSON string rejected before signed preparation.
Include malformed unterminated/escaped fixtures as separate safe400/no-dispatch cases.

Second workload: signed user history with maximum enabled finite PDF/audio/video individually
and reviewed explicit combinations, within existing aggregatebody/state bounds. Derive native
media facts from current parsers, not filename labels. Quotes/state may reduce available media
wire budget; document joint feasible maxima rather than independently maxing dimensions that
cannot fit. The first combination should use maximum finite PDF plus signedstate; subsequent
WAV/AVI combine only after corresponding parser/intake/accounting evidence. Never bypass profile
combination validation with model_copy; construct GoogleFeatureProfile through real validation,
then test-owned Settings mutation solely bypasses unconditional signed startup gate.

Provider must assert exact native ordering/media/signature replay and return bounded knownusage.
Retained clients consume/release each output before subsequent request; seeded state remains
bounded. Require at least one success per valid workload, no unexpected postdispatch502, all
preadmissionbusy503 explainable, exact provider dispatch↔successful settlement counts, typed
known/full conservativebilling, inputquota and zero active credit/quota reservations, final
signed/PDFcapacity reusable, no marker in errors/logs/admin/metrics. Include cancellation while
PDFpreparation runs, after reservation, and blockeddownstream delivery under originaldeadline
using existing application tests with new combined fixtures; no retry after ambiguous/output.

Independently review this concrete resource amendment before harness/test edits; review may
select smaller ordered substeps without changing the parent requirements. After any runtime
fix needed by measured failure, require its own feature-local design/review, focused/full>=80%,
Ruff/format/mypy/Docker/conditionalSonar/deepreview/docs. These are synthetic code/resource gates;
exact-model live signatures/codec/pricing and production enablement remain separate.

Independent design review requires explicit successful output-sealing headroom: context canonical
JSON<=131072B (emptycontext98B; quote-onlyinstructions65487chars),metadata<=128B,wire<=2097152B.
Default128historyitems need room for newoutput+nextuser (input<=126). Textoutputsealing requires
canonicalreplay+393984Bheadroom<=2097152 and aggregateexisting+newcarriers<=524288B; exactly
524288B existingcarriers cannot be treated as a successfulgenerationmaximum. Separate intake
limit tests from feasible completion maxima. Existing benchmark's model_copy produced an invalid
sealedprofile; newfixtures must explicitly validate function_tools/sealedpolicy/thinkingfalse/
budget/pricing/signaturefields. Fresh-process harness is corrected to use validatedprofile too;
its existing replay evidence must rerun before restating clearance.

Further reviewed joint facts: PDF65536B/file,131072Btotal,4totalpages; two2page65536Bfiles
exercise bytes/pages together. WAV2×320044B/20sec contributes853456base64bytes. AVI's actual
largest accepted4frame64×64rawBGR file is49408B,2files98816B/8frames;65536B cannot be reached
without forbidden padding/chunks. Their base64 totals plus maximumPDF are1159984B before URI/
itemframing. Adding131072context+524288carriers+393984sealingheadroom exceeds2MiB beforeframing;
reduce joint state/text dimensions explicitly and record real accepted bytes. Tokens<=131072B,
turn repeatedwrappers<=262144B,all existing+new<=524288B,<=16distinctturns/64Parts perturn;
signature16KiBperPart/64KiBperturn cannot all jointly reach maxima dueciphertextreplication.
Seed/replay instructions/tools/text must remain identical under context binding.

Independent reviewer cleared ordered verification implementation with noCritical/Major design
findings: quote-heavy feasible successful max first, signedPDF second, WAV/AVI individually,
then explicit jointfeasiblecombinations. Initialize real init-onlySettings with valid unsignedmedia
profile first so derived pricebounds populate; replace only continuationprofile with validated
sealedequivalent. Streaming success requires actualSDKterminalcompleted/usage/carrier, notHTTP200;
keep seed/load dispatchsettlement distinct and aggregatePDFchildRSS. Prefile cancellation must
prove noreservation/egress; postdispatch cleanup preserves billable consumption. Production/
startup/live gates unchanged.
