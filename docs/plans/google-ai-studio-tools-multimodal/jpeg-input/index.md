# Bounded static JPEG and WebP input

**Implemented** local code amendment to the full tools/multimodal plan. This closes two image-format gates;
remaining signed continuation, document, additional-media and live gates stay open.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)

## Objective and scope

Extend the current small inline PNG input to independently opt-in baseline JPEG and static
WebP, retaining 384-pixel dimensions, byte/aggregate/body limits, auto detail, Google-only
image pools and the existing conservative configured token ceiling. Do not accept progressive
JPEG, metadata-bearing or animated WebP, larger images, PDFs, media URLs or files.

## Concrete parser design

Add `image_formats` to GoogleFeatureProfile, default `["png"]`; allowed values `png`, `jpeg`,
`webp`, unique and nonempty. No new feature combination: these are formats of `inline_images`.
MIME selects an explicitly enabled format and must agree with validated bytes. Encoded-length
and aggregate checks precede base64 decoding; each image is released after inspection.

JPEG preflight validates SOI, bounded segment lengths/count (32), one baseline 8-bit SOF0 with
three components and <=384x384 dimensions/pixel cap, one complete sequential SOS, entropy
stuffing/restart markers and terminal EOI with no trailing bytes. Allow only bounded JFIF APP0,
DQT/DHT/DRI segments; reject all other metadata, unsupported SOFs, multiple scans and embedded
payloads. Require SOF before SOS. Raster-load with Pillow only after preflight, in RGB and with
matching format/dimensions. Input, coefficients and output are bounded; no metadata decoding,
rendering, filesystem, fetch, OCR or transcoding.

WebP preflight validates exact RIFF/WEBP size, a single VP8 or VP8L chunk with padding and no
trailing data. Validate VP8 key-frame/start code and unscaled 14-bit dimensions or VP8L magic,
version and packed dimensions before Pillow opens its native decoder. Reject VP8X, animation,
EXIF/ICC/XMP and additional chunks. Raster-load only after <=384x384/pixel validation; verify
static RGB/RGBA matching metadata. This corrects the prior WebP blocker by bounding dimensions
before native decoder construction. Decoder input/output remain capped.

Use vetted Pillow for raster integrity; structural preflight is a format allow-list rather
than a replacement codec. Catch specific parser exceptions and expose only existing safe errors.
Retain native-memory allowance per image (384*384*4 plus decoder allocations) in measurements;
async intake timers do not preempt synchronous work, so the finite input/pixels/segments are
required. Tests must reject corrupt/truncated/oversized/metadata inputs before egress.

## Measurement and verification

Add a reproducible local benchmark of actual body parse -> adapter validation -> upstream
mapping/JSON encoding with 8 simultaneous callers, 100 requests each, adversarial incompressible
384x384 images at existing aggregate bounds, separate PNG/JPEG/WebP runs. Record wall latency,
RSS including native allocations, encoded bytes and event-loop scheduling delay; include
invalid-container maximum-size cases. Retain the 2 MiB body cap and one-replica policy.
Focused tests cover format opt-in, no-egress rejection, combined tools/schema ordering,
conservative estimates and known/missing-usage lifecycle; run required full checks and independent
review before claiming the format code gate. Measurements describe local concurrency only.

## Entry criteria and roles

Independent session must review this exact parser/resource/metering design before edits.
Owner: runtime contributor. Reviewer: independent session. Live enablement: operator, after
exact model/profile/client and finite-spend evidence, separate from this code amendment.

## Independent review dispositions

The independent session found two Major clarifications, addressed before runtime edits:

- JPEG: require unique three-component IDs, sampling 1..4 with summed H*V <=10, quant/Huffman
  selectors <=3, each declared component exactly once in SOS, Ss=0/Se=63/Ah=Al=0. Validate bounded
  DQT/DHT/DRI structures before scan (8-bit quantization, valid table selectors/counts, bounded
  Huffman alphabet and non-oversubscribed code lengths), reject duplicate tables/frame/scan.
  JFIF APP0 is exactly its 14-byte header, version 1.00..1.02, zero thumbnail dimensions and
  no appended payload. WebP checks reserved/version/header bits and zero padding explicitly.
- Local benchmark acceptance: incremental process peak RSS <=128 MiB at 8 concurrent callers,
  max event-loop scheduling delay <=1 second and max request intake <5 seconds (default intake
  30 seconds). Generate incompressible images within individual bounds; set the aggregate cap
  to the exact decoded bytes of the successful multi-image fixture, never exceeding the existing
  hard maximum, and retain the 2 MiB body cap. Record caps, baseline RSS, environment and observed
  margins. Invalid maximum-size cases measured separately. Any failed threshold keeps the format
  code gate open and prevents enablement; results establish local code evidence only.

## JPEG integrity amendment

Adversarial experiments found Pillow accepts entropy-truncated baseline JPEG when a terminal
EOI remains. Structural marker inspection plus Pillow is insufficient for the corruption gate.
Before JPEG enablement, validate complete baseline entropy without reconstructing pixels:
canonical bounded Huffman tables, exact MCU/block counts derived from frame sampling/dimensions,
bounded DC categories and AC zero-run/category codes (<=64 coefficients/block), stuffed bytes,
restart interval/sequence, all-ones final padding and exact EOI. Limit tables to JPEG selector
space (eight Huffman/four quantization), block count to <=10/MCU and existing pixel/input bounds.
No custom image codec/reconstruction is added; Pillow still decodes the validated raster.
Canonical Huffman decoding must have a finite 16-bit search; malformed/no-code/exhausted input
fails safely. Add terminal-EOI truncation regressions, stuffed/restart/padding/coefficient cases,
and include entropy work in the same benchmark thresholds. Requires independent review before
this dependent implementation. Until it passes, JPEG's format gate remains open.

Independent entropy review requires sampling retained in frame context and blocks decoded in
SOS order; MCU grid ceil(width/(8*Hmax))*ceil(height/(8*Vmax)), exactly Hi*Vi blocks/component.
DC category <=11, AC category <=10, EOB/ZRL index bounds. Restart only at DRI boundaries with
<=7 all-one pad bits, cyclic sequence, no final extra restart; final <=7 all-one padding then
exact EOI and no unused full bytes. A shared finite decode-work counter and deadline checks
between MCUs must supplement byte/pixel caps; benchmark includes this Python work. The guarantee
is bounded entropy syntax/completeness, never detection of syntactically valid pixel changes.

Lossy VP8 remains disabled because its native decoder can tolerate tail truncation. Enable
WebP only for static single-chunk VP8L after bounded load/truncation fixtures. A lossy completeness
checker requires a later review. Native VP8L validation does not detect syntax-valid pixel changes.

## JPEG synchronous-work limit amendment

Random384-square JPEG completeness costs ~105ms/image locally; allowing eight such images at
eight callers cannot meet the <=1s scheduling gate. Propose JPEG dimensions<=128, pixels<=16384
per image and configurable `max_jpeg_total_pixels` default/hard32768 across all request history.
A request-local image-work budget is decremented from validated SOF dimensions before entropy
validation/native decode. All image roles/history share it; repeated preflight/build passes
start their own budget for the same immutable request. PNG and VP8L retain384 dimensions.
JPEG benchmark uses incompressible128-square, two images (exact32768 aggregate pixels),8 callers.
The258-token estimate remains conservative; no largerJPEG claim. Required larger-image follow-up
is still Planned. Budget exhaustion must reject before expensive entropy/native work.

The shared JPEG budget also caps384 coded blocks per pass across history. Standard subsampled
128-square images allow one within32768 pixels; no-subsampling worst entropy allows one88-square
image. The independent reviewer required the coded-block budget because small/unusual sampling
can have disproportionate work. Huffman prefix lookup is fixed65536 uint16 entries per table,
<=128KiB each/<=8 tables, so symbol search does not multiply work by adversarial code lengths.

Final measured work budget is384 coded blocks per pass. Earlier proposals/failed measurements
above document why it was tightened; the final contract is the canonical operations format table.
