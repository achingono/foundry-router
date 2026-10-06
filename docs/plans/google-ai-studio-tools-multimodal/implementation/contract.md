# Implementation contract — 2026-10-05

**Implemented** for the restricted code subset, extending the reviewed parent plan against predecessor HEAD `153b1b8`.
The predecessor code gate is recorded in its evidence; inspect/run its regressions again.

## Scope and decisions

Implement A for explicitly configured signature-free function models and structured text;
implement B initially for inline PNG images. Each capability defaults off. Declare exact
feature combinations separately. Configuration must affirm `unsigned` tool continuation;
`bound_history_required`, native transport, PDFs, audio/video and generated media remain
disabled because the carrier/parser/public-schema/billing gates are unresolved. No new
public continuation field, crypto, principal, tool executor or media fetcher is introduced.

Official sources fetched on 2026-10-05:

- https://ai.google.dev/gemini-api/docs/openai — function declarations, auto/named tool choice,
  image_url data URIs, structured parsing, streaming, thought-signature compatibility.
- https://ai.google.dev/gemini-api/docs/image-understanding — JPEG/PNG/WebP, 258 tokens for
  small images and tiled larger images. Use a required operator-declared conservative
  per-image token ceiling for its configured pixel bound; never use base64 as tokens.
- https://developers.openai.com/api/docs/guides/function-calling — Responses function_call,
  function_call_output, call_id, strict schemas, arguments delta/done events and history replay.

No model IDs or live support inferred from these pages. Signature docs redirected to a
minimal page; no lossless public Responses carrier was established. Required/named/none
choices and serial/parallel output are locally enforced; provider violations are billable
failures. Strict mode is preserved in translation and enforced locally before completion.

Use a bounded nonrecursive-reference schema subset: type, properties, required,
additionalProperties, items, enum, title, description. Reject all refs/patterns/unions and
unknown keywords, depth > 16, > 512 nodes, > 64 KiB schema, > 128 enum values. Strict object
schemas require all properties required and additionalProperties false. Function declarations
must specify strict explicitly (true/false); JSON-schema text requires strict true, name and
schema. No implicit provider normalization/default downgrade is performed. Bounded JSON parser
rejects duplicate keys/nonfinite numbers and overdeep data before schema validation.

Function histories retain complete ordered assistant turns, distinct provider call IDs,
text and parallel calls, and tool results. Require declared names, unique IDs and one result
per unresolved call before another message/turn. Completed function arguments must be valid
JSON objects; strict arguments additionally validate against their unchanged schema.
Signature-bearing provider output is rejected, never silently dropped.

Streaming state is per request, bounded by call count, identity/argument bytes and total
output. Emit provisional deltas only after identity is known; never complete calls until
final validation. Finish usage can arrive after arguments. Length/filter outcomes are
incomplete; malformed successful arguments/JSON become response.failed with known usage
or the full reservation, without retries. Preserve absolute reservation and intake deadlines.

Immutable per-request validation context (tools, choice, parallel flag, format) is passed
explicitly to non-stream translation and stream decoders; no shared adapter mutation.

Image inspection initially permits only PNG, using Pillow with declared/actual format checks,
dimensions/pixels/bytes
bounds, container/CRC checks followed by bounded RGB/RGBA raster decode (no OCR, transcoding or filesystem writes). Only
user input_image data URIs with auto detail supported; no remote/file URLs. Initially restrict
both dimensions to <=384 pixels and <=147456 pixels total (the documented 258-token tier).
An operator ceiling must be >=258; admission adds separate message framing overhead and uses
the pool-wide maximum ceiling in Google-only image pools (mixed Azure/Google image profiles are rejected). Token-priced media must be explicitly affirmed. Non-metered
backends still require token bounds. Large/tiled images await a separate metering gate.
Retain the 2 MiB default body cap and bounded intake timer starting before body read.
Async timers do not preempt synchronous work: schema traversal shares a node/work budget and
rejects branching constructs; JSON depth scan and aggregate bytes bound parser input. Image
inspection is bounded container/raster decode over capped bytes/pixels, with no metadata
decompression (reject PNG ancillary chunks), and deadline checks between bounded parts.
Measure parser work at the configured aggregate caps; retain disabled formats if unbounded.
JPEG/WebP remain disabled: Pillow verify does not establish their raster integrity and WebP
opens a native animation decoder before dimension checks. PNG container/CRC validation is
followed by bounded raster decode at <=384x384; restrict to 8-bit noninterlaced RGB/RGBA,
reject ancillary chunks and trailing bytes. Compressed input and decoded pixels are both capped.

## Independent plan review

Session `review_implementation_plan` reviewed this amendment before runtime edits. Four Major
findings fixed above: strict defaults, token lower bounds, immutable validation context and
synchronous work limits. Fifth parser finding addressed by restricting enabled images to PNG
and bounded decode. No Critical/Major design findings remain for this restricted scope.

Pinned OpenAI Python client tests cover model_dump/replay of standard function items and
stream events. No extension-client or live-provider compatibility is claimed.

## Verification

Focused schema/tool/media/routing/settlement/stream tests; full suite and >= 80% coverage;
ruff, format, mypy; Azurite, Docker build/health smoke; independent deep review;
docs links and final diff. Sonar script currently absent. Live tests require operator
credentials and spend limits, absent here, and remain Planned.
