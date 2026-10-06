# Finite native generated audio contract

**Partially implemented behind a startup gate**,2026-10-06; independently reviewed concrete
gated design, local client/resource/lifecycle evidence passed. This extends the parent plan,
not an audio-support claim. Current native reference includes responseFormat.audio MIME/
sampleRate/delivery and speechConfig.voiceConfig; current speech guide emphasizes Interactions.
Exact native model compatibility must be verified rather than inferred from catalog methods.
Sources read2026-10-06: https://ai.google.dev/api/generate-content and
https://ai.google.dev/gemini-api/docs/speech-generation .

## Public schema decision

Pinned OpenAI Python2.8.1 Responses output message content accepts output_text/refusal only;
its audio delta event types do not establish a complete binary nonstream artifact output item.
Do not fabricate standard output_audio or claim standard speech Responses support. Proposed
explicit version1 extension using SDK extra_body:
`foundry_audio_generation:{version:1,format:"wav",voice:"Kore"}` on a Responses request.
Only configured exact finite prebuilt voice identifiers accepted (no stored or replicated voice
IDs, speaker cloning, URLs, multiple speakers). Request plain input string only, optional bounded
instructions, metadata/storefalse; reject tools, structuredformat, history/media/continuation,
streamtrue and extra generation controls initially. Public response preserves ordinary Responses
metadata/status/usage and adds root `foundry_generated_audio:{version:1,id,format:"wav",
media_type:"audio/wav",sample_rate_hz:24000,channels:1,sample_width_bits:16,data:<base64>}` only
for actual validated completed native STOP audio. Ordinary output contains no invented transcript
or binary message; SDK exposes extension via model_extra/model_dump and caller explicitly decodes
base64 WAV. No implicit artifact replay; returned24kHzWAV cannot replay unchanged under the existing16kHz input profile.
Refusal/incomplete yields ordinary refusal/status without completed audio carrier. Nonstreamonly.

## Native and finite codec

Native candidateCount1,responseModalities[AUDIO],responseFormat.audio:{mimeType:AUDIO_WAV,
delivery:INLINE,sampleRate:24000},speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName configured.
Thinking-disabled configuration required only where exact model supports it; no silent native
surface/field migration. Signatures/thoughts/functions/textoutput/unknownmedia reject billably;
STOP exactlyone inlineData WAV required, refusal noaudio valid,MAX_TOKENS nevercompletedartifact.
Full envelope firstpass rejects lateunknownparts before artifact inspection.

Canonical base64 WAV<=480044decodedB (10seconds24kHzmono16bit). Exactly RIFF/WAVE, fmt16 PCM1,
mono24000Hz16bits,blockalign2,byterate48000,dataeven/nonempty<=480000B, noextra/trailingchunks/
metadata/compression. Struct-only constant-workvalidation, no audiodecode/transcode/playback.
Outputmimeexactaudio/wav. Defaultoffprofile audio_output, finite operator TOTALoutputbound
2048..32768, configuredvoicelist eachboundedASCII/prebuilt-only exact IDs, allpoolprofilesidentical.

## Resource, accounting and lifecycle

Reuse existing generated-output global capacity and actual outerASGI delivery owner through
original reservationdeadline; two-slot admission per generatedaudio initially (oneactive),
providerwait/fullbody/validation/downstreamdelivery. Do not instantiate PNGworker forWAV;
WAVsyntax bounded inprocess and readinessnoextraaudiochild. Capacitybeforecredit/quota/provider
but aftersemanticvalidation. Mixedimage/audioresource measurements required.

Credit-owned typed reserve = inputUTF8 upperbound×inputprice + serverTOTALoutputbound×textprice
+ maxduration10×operatorpriceceilingUSDpersecond. Separate audio_output_per_second price must
match profile ceiling; operatoraffirms inputprice and projectinputTPM equivalence, audioquota
via configuredsharedRPM with explicitgenerationrequestsperminuteceiling. Nonmeteredzeroprice
stillconsumestokens/quota. Allbillableoutcomes settlefullreserve, includingrefusal/truncation/
invalidmedia/cancel; knownusagepublic/inputTPMonly. Confirmedvalidation4xxrefund,429freshadmission
failover samelease/profile and noretryafterambiguousdispatch. Emergencyfallbackdisabled.

SDKactualextra_body/createandmodel_extra/base64consumption; noimplicitreplay; refusals/truncation/
invalidMIME/container/missingusage, separateprices/fullreserve/IPM/TPM andmixing; actualASGIblocked
start/body/cancel/drainexactonce; syntheticmarkersredacted; Linux8×100maxWAV/lateinvalid/
providerwait/mixedglobalcapacity512MiB withincrement<=128MiB; >=80%fullquality/Docker/deepreview/
docs. Startuphardgate untillocalgatesreviewed; exactmodellivefreeeligibility/pricing neededbefore
liveoutputcalls. No uploads/hosting/executor/newcloudinfrastructure.

## Review questions

- Is root versioned carrier consumed losslessly by pinnedSDK without implying standard audio?
- Does configured native format/voice/thinking policy need separate generation-specific adapter?
- Are accounting persecondbound/tokenpricing and RPMquota dimensions sufficiently explicit?
- Can existing globaloutput/outerdelivery lifecycle be reused without coupling PNGworker toWAV?

## Review amendment: intake and exact thinking policy

Public request input is nonempty UTF8<=4096bytes, optional instructions<=1024UTF8bytes; full
serialized body still obeys existing intake cap. Native content preserves both exactly; no
operator-injected style/transcript rewriting. Exact JSONversioninteger1 and fixedformatwav;
voiceboundedASCII1..32bytesandmemberofconfiguredprebuiltvoiceallowlist<=30entries; nounknownfields.
No caller tokenoverride except exactserverTOTALbound. Nulls/booleans cannot substitute forvalues.

Use a separate generated-audio adapter/request/projection boundary. Profile requires explicit
`audio_output_thinking_policy` enum `omit` or `disable_zero`, with exact-model operator affirmation.
`omit` emits no thinkingConfig and asserts modeldoesnotrequire/disclosethoughtstate;
`disable_zero` emits exactlythinkingBudget0. No fallback/automaticomissiononprovidererror. Existing
GoogleNativeAdapter and nativefoundation thinking policy remain unchanged. Anyreturnedthought/
signature/state stillrejects billably. BackendConfig accepts audioonlynative with its explicit
thinkingpolicy, while startupSettingsgate remainsunconditionaluntilreviewedlocalgates.

Audioadapter may reuse strictnativeenvelope/usage validation functions but doesnotdelegate
requestbuild through unsigned tools adapter, norinvokePNGready/inspect. Globaloutputlease for
finiteinprocessWAV validation uses2units andexistingouterdeliverydeadline/drainowner. Tokenbound
andpersecondreserve arecreditowned; nativeformattedtool/schemapayloads neverinferredfromrequest.

## Review amendment: finite envelope, readiness and replay

Successful audio response decodedJSON wire<=700000bytes beforeparse; at mostonecandidate/
oneinlineData part, boundedexistingnativeenvelope fields andusage. Nativeadapterchecks all
state/finish/envelope beforedecode; unknownmime/rawPCMtext/functionparts rejectbillably.
Canonical WAV encodedceiling4×ceil(480044/3); strictbase64 beforedecode. NativeMAX_TOKENS may
validate/discard finiteWAV butneverattachcompletedcarrier. Refusal noartifact ordinarysafeoutcome.
Ifproviderwireexceeds700000B, retainfullreserve andterminatewithoutretry.

Audio-only profile uses2globaloutputunits but noPNGreadiness/worker. PureboundedWAVselftest
andconfiguration support healthreadiness; no platform requirement for constantworkstructparser.
Returned24kHzWAV is incompatiblewith existing16kHzinputWAV profile: callers cannot replay it
unchanged. Inputreplayrequires separatelyreviewed24k inputprofile; routerdoesnottranscode.
Publiccarrier is consumed/exportedonlyfor thisincrement. Initialschemametadata bounds retain
16entries/key<=64/value<=512characters. ExplicitstoreomittedorFalse only,streamomittedorFalse;
rejectTrue/null/otherfields perstrictpublicallowlist. ExistingAzurepass-through unaffected;
extensioninterpretedonlyGoogleaudioenabledpool, incapableGooglepoolsrejectbeforeegress.
