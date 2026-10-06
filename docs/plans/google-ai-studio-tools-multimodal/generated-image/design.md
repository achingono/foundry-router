# Finite native generated image contract

**Planned**,2026-10-06. Independently reviewed choices below supersede exploratory alternatives.
Code/client/resource and exact-model gates remain required. Current zero-paid-spend authorization
precludes API-paid-only generated-image live tests.

Sources read2026-10-06: https://ai.google.dev/gemini-api/docs/image-generation ,
https://ai.google.dev/api/generate-content , https://ai.google.dev/gemini-api/docs/pricing .
Native reference specifies responseModalities IMAGE/TEXT and imageConfig aspectRatio/imageSize;
current guide emphasizes Interactions. Keep fixed native generateContent; exact PNG/codec/model
support is unverified. No automatic surface migration.

## Public and native semantics

Default-off image_output native-only feature; standard Responses exact tools shape
[{type:image_generation,output_format:png,size:1024x1024}]. Omit tool_choice: standard auto
permits zero or one image. Text-only STOP is valid completed text. Reject explicit model,
other controls, tool choices, parallel fields, additional tools and structured formats before
admission. PinnedOpenAI2.8.1 accepts this tool and image_generation_call{id,type,status,result};
result is canonical base64PNG. Only actual validated image receives a completed call. Text/image
order follows native Parts. No hostedURL or unrelatedschema/MIME extension. Caller converts
retained image to enabled input_image for replay; no implicit image_generation_call history.
Initial combinations only image_output alone or with enabled bounded input_images, explicitopt-in.

Native candidateCount1,responseModalities:[TEXT,IMAGE],imageConfig:{aspectRatio:1:1,imageSize:1K}.
Thinkingdisabled must be affirmed for exact model; any signature/thought state rejects without
discarding it. Nonstreamonly; streamtrue422beforeegress. STOP may contain0or1image. Safetyblocked
noimage yields normal bounded refusal. MAX_TOKENS/incomplete never emits completed binaryartifact;
retainusage and bounded incomplete/failed public outcome. Multipleimages/unknownMIME/invalidPNG
billablevalidationfailure. No tool execution, media fetching, uploads or transcoding.

## Resource and lifecycle contract

Canonical base64 encoded-length checked before decode; decodedPNG<=1MiB. ExactPNG signature,
one IHDR13first:1024×1024,8bit RGB/RGBA,compression/filter0,noninterlaced.1..62contiguousIDAT,
max64totalchunks,CRC allchunks,IDATaggregate<=1MiB,IEND0last,no trailing/unknown/ancillary chunks.
No speculative metadata: providerPNG ancillary/signaturefailsbillably until separately reviewed.
Zlib CMF/FLG valid,FDICTfalse,exactEOF/no secondstream/unused/unconsumed/trailing; fixedrowfilters
0..4/exactrowcount. Decompress max_length boundedremainingrow+sentinel; never unboundedflush.
MaxexpandedRGBA4195328B. Filter scan only, no reversefilters/rendering/pixeltransformation.

Independent2nonqueued request-owned leases afterauth/semanticeligibility BEFOREquota/credit/
provider; busy503zeroegress. Samelease acrossfailover/providerwait/inspection/cleanup, releases
once. Linuxworker minimalenv no credentials, imports afterlimits AS128MiB/CPU1sec/FSize0/FD32,
stdin<=1MiB+1/stdoutmetadata<=1KiB/stderrdiscard. Wall2sec boundedoriginalintake/reservationdeadline;
kill+reap beforeclosedactivelease reusable. No PDFworker reuse. Readiness boundedselftest shares
capacity; unavailableworker fails beforeadmission. Immutable digest/facts bind validated artifact;
no completedartifact until worker succeeds and nativeSTOP validates.

## Accounting and quota

Choose explicit per-image conservative price, not aggregate text/image tokenprice equivalence.
Meteredpool PricingConfig.image_output_per_image finite>=0 required; profileaffirms priceceiling,
inputpriceequivalence, generated_output_tokens_bound>=2048<=32768 includes image/text/thinking.
Allpool outputprofiles/bounds identical. Server-ownedTOTALoutputceiling deterministic; public
max_output_tokens exactconfiguredbound oromitted, filledbeforeestimate (no unreserved1024default).
Credit-owned typedestimate=inputUTF8/mediaupperbound×inputprice + TOTALoutputbound×textprice +
oneoperatorimagepriceceiling. FIRSTfiniteincrement everybillableattempt settlesfullreservation,
even autozeroimages/refusal/truncation/malformed/cancel. Knownnativeusage retained public/inputTPM
only, neverreducescreditbyaggregateoutputtokens×textprice. Standard confirmednoegress/validating
4xx refundrules retained. Clearly estimated, not exactactualcharge/Azurebalance.

Oneimage/request: explicit projectsharedquotagroup acrossallmodel/keytraffic and hardconfigured
RPM<=operatoraffirmedimageIPM. Requireimage_output_quota_via_rpm plus explicitIPMceiling/inputTPM;
unknownadditionalquota dimension disables. No protectedquota fallback maybypassIPM; initially
reject imageoutputconfig if emergencyfallback enabled. Nonmeteredkeys still require dimensions/
TOTALoutputbound/tokenquotaaffirmations; zeroprice never implies missingdimension allowed.

## Gates

ActualSDKnonstream/base64consumption and order,autozeroimage/refusal/truncation/signatures;
PNGmetadata/decompression/containerbounds; outputleasebeforeadmission/workerdeadline/cancel;
perimageprice/inputTPM/IPM/missingusage/paidfailure settlement; noegress/redaction.
Linux8×100 maxPNG/lateinvalid/providerwait/combinedcapacities in512MiB; measurewholeparent+children,
observedincrement<=128MiB. Fullquality>=80%/Docker/deepreview/docs. Exactmodel livepaidinference
requires separate authorization. Largerformat/streaming/generatedaudio remain separate contracts.

## Reviewed combined-capacity amendment (2026-10-06)

Exact simultaneous1048576B input-image aggregate and1048576B generated output exceeded the
128MiB incremental sampled parent+children RSS target in full HTTP8×100 synthetic Linux checks
(161935360B), despite correct output/settlement and consumed-output clients. Do not enable this
combination from smaller-input evidence. Independently reviewed amendment: any output request
in an inline-image-enabled output pool reserves both output slots before readiness/admission,
so only one combined-capable request may progress. Output-only pools keep one-slot leases and
up to two concurrent requests. No wait queue, payload-cap increase or credit/quota change.
Acquire/release requested slots atomically under a short threading lock; lease retains both
through provider wait/failover/child cancellation/reap. Actual same exact-cap workload must pass
before this amendment supplies resource evidence. Startup gate remains closed.

## Reviewed delivery-ownership amendment (2026-10-06)

Pending independent review: preserve the generated success response's output lease through
bounded ASGI downstream delivery, rather than releasing capacity when the API handler returns.
Forwarding records the original reservation deadline in the same lease. After routing/settlement
returns successfully, API wraps the success response with a Response subclass owning the same
body/headers and lease; ownership transfer occurs only then. Wrapper __call__ uses timeout_at
that deadline around response-start/body send, and always closes the lease. Route errors or
metrics/settlement failure before transfer close in API finally. Cancellation/double close remains
idempotent, active worker still reaps before release. No new billing or retry after delivery
begins. Test blocked response-start/body, cancellation and capacity retention with direct ASGI
send; actual SDK response unchanged. Only generated success responses need this ownership.

The independent weighted admission review passed39tests/1Linuxskip; exact late-invalid combined
and mixed output-pool capacities now also pass, as recorded in evidence. Delivery ownership
review remains separate and pending; resource measurements do not close downstream backpressure.

Independent review found a route Response wrapper insufficient: two existing BaseHTTPMiddleware
layers can drain its body into intermediary streams before actual network send completes.
Revised independently reviewed proposal: pure ASGI generated-output delivery middleware installed after
both HTTP middleware registrations (outermost user layer). Private scope.state marker identifies
that actual delivery owner; after routing/settlement succeeds, API transfers lease and immutable
original reservation deadline via state only when marker is present. Forwarding binds that
deadline to lease before artifact processing. Outer real-send wrapper enforces timeout_at on
response-start and body sends; middleware finally closes transferred lease after final delivery,
error or cancellation. No marker on isolated bare-router harness means no transfer and its
existing route-finally close remains explicit limited-scope evidence. Ordinary/SSE paths have
no owner and unchanged sends. Test actual main.app stack blocked start/body and cancellation;
route-only wrapper design cannot close this gate.

## Reviewed generated-output drain ownership correction (2026-10-06)

Actual middleware blocked response-start cancellation exposed active-request count leakage:
existing BaseHTTPMiddleware classifies the internal response as StreamingResponse and defers
its decrement to an iterator that may never start. Full suite waits the30second shutdown timeout.
Independently reviewed correction: after call_next returns, if generated delivery owner already
owns the successful image lease, transfer one `_decrement_active_requests` callback to that owner
and skip the ordinary stream iterator wrapper for this response. Outer owner finally closes
lease and runs callback via protected cleanup, exactly once despite cancellation. Ordinary/SSE
responses retain existing behavior; pretransfer errors keep existing finally decrement.
Actual main.app blockedstart/body×cancel/deadline tests must assertcounterzero andfullbilling.
