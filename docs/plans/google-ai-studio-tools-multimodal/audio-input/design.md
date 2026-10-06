# Finite native WAV input contract

**Planned**,2026-10-06; independent API/resource/accounting review before runtime changes.

Use the standard Responses input_file shape on user message content:
`{"type":"input_file","filename":"fixture.wav","file_data":"data:audio/wav;base64,<canonical>"}`.
The pinned OpenAI2.8.1 fileinput schema accepts file_data/filename and has no dedicated audio
Responses content type. Native Google requires inlineData audio/wav; compatibility remains
unchanged and incapable. This is a finite file-media subset, no new extension. Allow missingfilename
or bounded display-onlyfilename (existingfile rules), reject IDs/URLs/extra MIME parameters.

Official Google audio guide read2026-10-06 supports WAV inline input and32tokens/second;
https://ai.google.dev/gemini-api/docs/audio . Exact models/live behavior remain pending. Do not
infer support from names or Interactions schema. Map exactcanonicalbase64 to native inlineData,
preserve orderedtext/media and history. No upload/countTokens/transcoding/playback/tool execution.

Parser accepts one canonical little-endian RIFF/WAVE container containing exactly fmt(16bytes)
then data: PCMformat1, mono,16000Hz,16bits,blockalign2,byterate32000. No unknown chunks,padding,
extensibleformat,compression,externalreferences/trailingbytes. Data nonempty evenlength and
atmost320000bytes (10seconds), maxfile320044bytes; max2files/640088aggregatebytes/20aggregate
seconds perrequest, including history. Read structfields with boundedconstantwork, no codec
library/audio decoding/FFmpeg. Duration derived integerframes/sample rate, never suppliedlabels.
No generatedaudio support. Roleuseronly. Other fileMIMEs explicitlyreject beforeadmission.

Default-off inline_audio feature; require native surface, explicit maxfiles/bytes/seconds and
operator audio_input_tokens_per_second>=32 plus fixed framing64tokens/file and tokenprice
 equivalence affirmation. Initially modelpool homogeneousnativeGoogle whenaudioenabled; separate
logicalpools avoid Azure pricing mismatches. Token ceiling perfile=ceil(configuredmaxseconds*
configuredtokenrate)+64, configuredratebounded32–10000, seconds1–10. Pool uses maximum enabled
backendbound forinputTPM andcredit; strip audio payloadfromtext estimate then addbound; free-tier
zero-price stilltokenlimits. Generatedtext/tool/schema/signatureusage known totals settle once.
No extra quota dimension claimed; exactmodelprovider admission must affirm TPMaudio counting
before liveenablement; otherwise disabled. Pricing dimension token-equivalence explicit, don't
usebase64bytecount ordefaultmissingdimensionzero.

Classification file MIME before PDFprep: typed dispatcher recognizes exact prefixesapplication/pdf
or audio/wav; PDFhelper only ownsPDFpositions, immutable audiofacts optional prepared media object
if needed to avoid repeatedparsing. Prefer frozen PreparedAudio tuple(position,digest,bytes,frames)
APIprep once beforeselection (under signedleasewhenapplicable); adaptervalidatesdigest/profile
without reparsing failover. Ordinaryaudio prep sameboundedintake/deadline; lowcomplexityparser
inprocess finite bytes, no unboundedraster/decompression. Candidate lowercaps rejectprecredit.
Unsupported audio+tools/schema/image/PDFcombos rejectunless explicitlisted.

Tests exactheader/sample/RIFF/trailing/mislabeled/compressed/bigendian/manychunk/aggregate/history,
SDKHTTPinput/replay, nativeorderedmapping, unsupportedmixedcandidate, threeprojectfailover,
429/5xx/billableschemaerror/knownusage/cancellation/redaction/noegress; fullquality>=80%, Docker,
independentreview and8×100Linuxmaxaudio mixedmedia resource measurements. Plan scope includes
other audio codecs as separately gated futureformats, not a claim they are implemented.

## Independent review precision

Enforce canonical encoded length before decoding; RIFFsize=filelength−8 and datachunklength=
filelength−44. Aggregateframes<=320000 at16kHz; ownedfacts revalidate every candidate's lower
file/byte/frame limits. Fileclassification/preparation applies only to Google feature-owned
media and preserves Azure-only input_file passthrough. Optional filename must match bounded
ASCII WAV displaylabel `[A-Za-z0-9_.-]{1,60}\.wav`, explicitnull/pathseparator rejected.

Enabled audio profiles require both audio token-price equivalence and explicit audio_tpm_tokens
affirmation; readiness/config reject missing flags. No provider quota claim from plainRPMalone.
MIME-specific estimation uses WAVaudio bound, never PDFbound; freeprice stillinputTPM. Exactlive
operator evidence remainsseparate before operationalenablement.
