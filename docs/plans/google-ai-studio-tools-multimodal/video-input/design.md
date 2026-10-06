# Finite native video input contract

**Planned**, 2026-10-06. Review before implementation.

Use standard Responses user input_file with file_data canonical data:video/avi;base64,...;
optional display filename `[A-Za-z0-9_.-]{1,60}\.avi`. No extension, paths, URLs or IDs.
Pinned OpenAI 2.8.1 supports input_file. Official video guide read 2026-10-06 lists video/avi
and default one-frame-per-second static processing; it now emphasizes Interactions. The
separate generateContent API reference confirms inlineData video MIME and videoMetadata.fps
(default 1, range (0,24]). Remain on fixed generateContent/streamGenerateContent; no implicit
Interactions migration. Native part uses videoMetadata:{fps:1} plus inlineData video/avi.
Sources: https://ai.google.dev/gemini-api/docs/video-understanding and
https://ai.google.dev/api/generate-content . Exact model and raw AVI codec support are unverified.

Finite initial format: canonical RIFF AVI, one uncompressed DIB video stream, no audio.
Exactly LIST hdrl (avih, LIST strl containing strh and strf), then LIST movi containing 00db
frames; no index, additional chunks, metadata, external references, compression or trailing
bytes. Positive bottom-up DIB RGB24, width/height 1–64, row stride rounded to four, zero row
padding, 1fps, 1–4frames (1–4seconds). No pixel transformations or rendering. File<=65536B,
at most two clips/131072B/eight frames/eight seconds across all history. Validate RIFF/list/chunk
sizes, exact fixed headers, counts, duration and every frame size against actual bytes before
admission. avih 56bytes, strh 56bytes, strf BITMAPINFOHEADER40bytes. Reject reserved flags,
nonzero initial frames, unsupported rate/scale/start, mismatched width/height/rectangle/count,
negative height/compression, and container layout drift. Maximum encoded allocation checked
before base64; canonical base64 roundtrip; immutable facts position/digest/bytes/frames/pixels.
Candidate revalidates identity and lower file/count/frame/byte/pixel caps without parsing again.
No FFmpeg/PyAV dependency or subprocess: finite container bounds plus explicit raw frame lengths
bound parser work and eliminate codec expansion. Provider codec acceptance remains a live gate;
configuration declaration and local fixtures cannot prove it.

Default-off native-only inline_video feature, Google-native-only logical pools. Require explicit
video_input_tokens_per_frame >=258 (bounded <=100000), video_token_pricing and video_tpm_tokens
affirmations. Reserve full configured frames × rate + full configured file byte bound +64/file,
including history. This deliberately includes conservative file/metadata overhead, never a
claim of actual Google tokens; input TPM and credit remain separate. Free-tier zero price still
consumes input TPM. No audio track so no audio token dimension. Unknown price/quota semantics
reject startup. Explicit combinations with tools/schema/image/PDF/WAV; no implicit combos.
MIME-specific estimator uses video bound and never PDF/WAVbound; preserve Azure-only files.

Tests: container/header/layout/size/frame/timing/padding failures; aggregate/history and mutation;
SDK create/stream and replay; exact native ordering/metadata; candidate lower caps and project
failover; freeTPM; paid known/missingusage failure; deadlines/cancellation/redaction/noegress;
Linux 8×100 maximum audio/video and combined media/state resource measurements. Full suite,
80%coverage/Ruff/format/mypy/Docker/docs/deep review. Live validation only after isolated exact
model/free-tier configuration exists. Other codecs/video output remain unsupported separately.

## Independent review precision

Frame bytes are Windows bottom-up B,G,R DIB24; no channel conversion. Server injects fps1;
public videoMetadata fields are rejected. AVI handler DIB-space and stream type vids only.
avih: microseconds/frame1000000, maxbytes/sec=framebytes, padding=0, flags=0, totalframes=N,
initialframes=0, streams=1, suggestedbuffer=framebytes, width=W,height=H, four reservedzeros.
strh: vids,DIB-space, flags/priority/language/initialframes=0, scale=rate=1, start=0,length=N,
suggestedbuffer=framebytes, quality=0xffffffff,samplesize=0, rect=(0,0,W,H).
strf:40,W,H,planes1,bits24,BI_RGB0,sizeimage=framebytes,x/yppm0,colorsused/important0.
Exact chunk/list end arithmetic and zero padding, aggregateframes<=8, perframepixels<=4096,
width/height<=64; all lower candidate limits revalidate immutable facts. Native Part
videoMetadata with inlineData and video/avi MIME supported in cited reference/guide; exact
raw DIB codec acceptance remains live-gated. No implementation before review clearance.

Row stride=((W*3+3)//4)*4; framebytes=stride*H; each 00db exactly framebytes with zero row padding.
Token rate>=258 is an operator-affirmed upper bound for the exact model; fixed fps is not proof of rate.

Smallest canonical file=224 header/list bytes+8 frameheader+4 rowbytes=236bytes.
