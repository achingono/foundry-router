# ADR-010: Default-off Google feature profiles

## Status

Accepted for the restricted code subset; model-specific live enablement Planned.

## Decision

Extend ADR-008's compatibility adapter with exact per-backend feature combinations, explicit
unsigned tool policy, request-local output validation and bounded inline small PNG input.
Preserve strictness and completed arguments/JSON locally; protocol violations after generation
settle valid usage or the full reservation and never retry. Public stream indices track emission
order independently of provider call indices and support OpenAI Python 2.8.1 stateful replay.

Require explicit tool strictness; strict JSON-schema text requires name/schema/strict true.
Use a bounded reference-free schema subset. Restrict PNG dimensions to the documented small
258-token tier and require model-specific conservative ceilings/token-price affirmation.
Image-enabled logical pools must be Google-only until a shared media-pricing contract exists.

Keep signatures disabled: no standard Responses carrier has been established, no sealed public
extension has been approved, and provider state must never be discarded. Larger images, lossy WebP and
PDF isolation, native transport, audio/video and generated media retain independent gates.
No tool executor, media fetcher, upload/store, cryptography or cloud infrastructure is added.

## Evidence

Official Google compatibility/image and OpenAI function-calling pages were fetched 2026-10-05;
the [reviewed contract](../../plans/google-ai-studio-tools-multimodal/implementation/contract.md)
records conclusions and limitations. [Operations](../../operations/google-features.md) documents
configuration/bounds; [evidence](../../plans/google-ai-studio-tools-multimodal/implementation/evidence.md)
separates synthetic/client code gates from live Google verification.

The [image-format increment](../../plans/google-ai-studio-tools-multimodal/jpeg-input/index.md)
adds explicit default-PNG format selection, <=128 baseline JPEG with384-block shared entropy
budget, and <=384 static lossless VP8L. Container preflight precedes native decode; JPEG adds
finite entropy syntax/completeness checks. Concurrent local measurements retain existing body
limits. Exact-model live and Azure performance evidence remain Planned.

The [native/PDF increment](../../plans/google-ai-studio-tools-multimodal/native-pdf/evidence.md)
adds configured native Responses routing and isolated finite PDF preparation. Independent review,
full local tests and actual Linux parser/HTTP/resource gates passed. This supersedes the earlier
native/PDF code deferral above; exact-model live validation remains Planned. Signed continuation
and remaining media directions retain separate API/parser/accounting gates.
