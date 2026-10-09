# Google tool, structured text and image profiles

**Implemented** with synthetic contracts and OpenAI Python 2.8.1 client replay. Live Google
model/client compatibility remains **Planned**. Features default off; enabling a profile declares
operator-verified support for the exact configured model and compatibility surface.

### Repeated-failure exclusion

The memory runtime now retains exclusions across requests for each backend/operation/
streaming-mode combination. Three qualifying terminal 404/5xx failures open a
30-minute window. This is process-local scheduling state, not a Google quota balance
and not cross-restart persistence. Inspect `/admin/status`'s `combination_exclusions`
and `combination_exclusion_entries_total` / `combination_exclusion_resets_total`.
If alternatives are unavailable, a generation-fenced foreground probe can test an
excluded combination without bypassing quota, credit, or operator-disabled health.
Successful probes clear the window; failed probes re-arm it. Process startup resets
state and logs `combination_exclusion_reset`. Multi-replica aggregation remains
unverified; production remains memory-backed with `maxReplicas: 1` until cutover gates.

Example `google_features` value inside a Google backend (model/key/endpoint remain the existing
backend configuration; use separate Google-only logical pools when enabling images):

```json
{
  "features": ["function_tools", "parallel_calls", "json_schema", "inline_images"],
  "combinations": [
    ["function_tools", "parallel_calls"],
    ["function_tools", "parallel_calls", "inline_images"],
    ["json_schema", "inline_images"]
  ],
  "continuation_policy": "unsigned",
  "image_formats": ["png", "jpeg", "webp"],
  "image_input_tokens": 258,
  "image_token_pricing": true
}
```

`json_object` is separately configurable. A request must match the exact enabled combination.
Parallel defaults to configured parallel support for tool requests; callers can set
`parallel_tool_calls: false` for future calls, but historical parallel turns still require their
capability/combination. Named tool choice requires exactly one generated call. Tools must provide
explicit `strict: true` or `false`; parameters must use the bounded schema subset below.

Defaults/hard bounds:

| Resource | Default | Maximum |
| --- | --- | --- |
| `max_tools` | 16 | 32 |
| `max_history_items` | 128 | 256 |
| `max_argument_bytes`, `max_result_bytes` | 65536 each | 262144 each |
| `max_images` | 4 | 8 |
| `max_image_bytes` | 262144 | 524288 |
| `max_total_image_bytes` | 524288 | 1048576 |
| `image_formats` | `["png"]` | Unique subset of png/jpeg/webp |
| `max_image_pixels` | 147456 | 147456; PNG/VP8L dimensions <=384 |
| `max_jpeg_total_pixels` | 32768 | 32768; JPEG dimensions <=128, <=384 coded blocks per request |
| Schema bytes/depth/nodes | 65536 / 16 / 512 | Fixed |
| JSON nesting/work | 32 / 16384 | Fixed |
| Schema enum values | 128 | Fixed |
| Google SSE event/buffer/assembled output | 256 KiB / 1 MiB / 4 MiB | Fixed |

Image input accepts enabled `input_image.image_url: "data:image/<format>;base64,..."` with
`detail: "auto"` or omitted detail. Format selection defaults to PNG; JPEG/WebP require explicit
opt-in. PNG is 8-bit RGB/RGBA noninterlaced IHDR/IDAT/IEND only, with container order/CRC and
bounded raster decode. JPEG is three-component 8-bit baseline single-scan, <=128 each dimension;
only bounded tables/restart markers and JFIF with no thumbnail are accepted. Sampling/table/code
bounds and exact entropy block count, stuffing/restart/padding/end-marker checks precede Pillow.
Across full history, JPEG consumes <=32768 pixels and <=384 coded blocks per validation pass;
ordinary subsampled128-square images allow one, no-subsampling88-square allows one. WebP is
static single-chunk lossless VP8L, <=384 dimensions, with RIFF/header/size/padding checks before
native decode. Lossy VP8, VP8X, animation and ancillary metadata are rejected. Full raster loading
checks syntax/completeness; syntactically valid pixel changes cannot be identified as corruption.
Remote URLs/files, progressive JPEG and larger/tiled images remain unsupported. Native PDF
input has a separate default-off profile described below.
The initial image ceiling follows Google's documented <=384×384 258-token tier, with additional
framing overhead; configure a larger ceiling when the selected model requires it. Token-price
affirmation means the logical pool's input token price is valid for image tokens; these prices
remain local estimates. Non-metered keys also require ceilings and obey quota/resource limits.

Supported schema keywords: `type`, `properties`, `required`, `additionalProperties`, `items`,
`enum`, `title`, `description`. Types: object, array, string, integer, number, boolean, null.
Root is an object. Strict object schemas require every property required and
`additionalProperties: false`; strict JSON-schema text requires name/schema/strict true.
References, unions, recursion, patterns and unsupported constraints fail before dispatch.
No constraints are stripped or JSON repaired. Completed arguments/text validate locally;
provisional SSE deltas are not an execution trigger. Refusals and output limits remain distinct.

Callers replay full ordered assistant/function history and one string result per unresolved call.
Calls/results require unique IDs and complete parallel sets; the router executes no tools and
starts no automatic turn. Each continuation authenticates/reserves anew. Signature-dependent
models are unsupported: no reviewed lossless Responses carrier exists, and provider signatures
are rejected rather than discarded. `bound_history_required`, audio/video and generated
media profiles remain Planned. This subset does not establish general coding-agent compatibility.

Enablement requires bounded live evidence for the exact model/profile/client combination in an
isolated memory/one app, including usage, settlement, refusals and streamed replay. No such live
tests ran here. Roll back by disabling features/combinations or draining the backend; callers
using a disabled capability get pre-egress 422. Existing unsigned tools require full history after
restart. No continuation keys or cache need rotation. Production remains memory-backed with one
replica until its separate cut-over gates pass.

See [implementation evidence](../plans/google-ai-studio-tools-multimodal/implementation/evidence.md)
and [API](../api/index.md).

Native transport is **Partially implemented** with local text/tool/schema/image tests; its
independent implementation review and PDF local gates passed; exact-model live gates remain open. Backend `api_surface: "native"` uses
fixed generateContent/streamGenerateContent routes and x-goog-api-key, while omitted surface
keeps compatibility. Native requires Responses-only operation support, a service-root endpoint
and `google_features.native_thinking_disabled: true`, affirming the selected model honors
thinkingBudget0. Embeddings and signed/thought state remain rejected. PDFs require the separate default-off profile. Native histories
combine only leading system instructions; mid-history system/developer messages reject.
Parallel function results form one ordered user turn. Native usage includes candidates+thoughts
and prompt/cache inclusion checks; unexpected thinking fails while known billed usage survives.
Clean SSE EOF with finish evidence is required; late usage is cumulative and no content follows
finish. [Native/PDF plan](../plans/google-ai-studio-tools-multimodal/native-pdf/index.md) records
implemented local protocol/parser gates and pending live validation. No model capability or production deployment is inferred.

PDF runtime is **Implemented locally**, with independent review, Linux HTTP/worker and bounded
mixed/aggregate/late-invalid resource gates passed. Default-off native `inline_pdfs` uses an isolated Linux worker with pinned pypdf,
strict raw/classic PDF/text checks and immutable facts before admission. Readiness performs a
cached owned-fixture worker self-test; missing/wrong dependency or unsupported limits fail ready.
Two busy worker slots return503 immediately; there is no unbounded PDF queue.64KiB/document,
128KiB aggregate,4documents/4pages are hard maxima. Every document reserves full configured page
visual/native-text ceilings plus raw byte ceiling, with actual valid usage settlement. Native
PDF URLs, stored IDs, encryption, compressed/object streams, actions and custom fonts reject.
Exact model/token/pricing/live evidence remains required before enabling a PDF profile. Production
enablement remains separate.

The in-flight signed runtime keeps two request-owned preparation/generation slots. On servers
with a bound-history pool, all Responses JSON intake shares those slots before the model can be
validated, including ordinary models on that server; saturation returns503 before admission.
Use separate router instances for ordinary traffic if that isolation is required. Ordinary-only
servers and embeddings keep their existing parsing path. Signed startup remains gated pending
resource, lifecycle and live validation.

Finite native WAV input is **Partially implemented**, default-off. Independent review,
SDK create/stream/replay, candidate/accounting regressions and audio-only Linux maximum resource
measurement passed; combined media/state resource, cancellation and exact-model live gates
remain open. Require audio pricing and input-TPM equivalence affirmations before configuration;
see [configuration](../configuration/index.md) and [evidence](../plans/google-ai-studio-tools-multimodal/audio-input/evidence.md).

Finite raw AVI is **Partially implemented**, default-off: parser, SDK/native/candidate/lifecycle
and video-only Linux measurement pass. Exact raw DIB codec/model/price/TPM and combined resource
gates remain open; catalog generateContent support does not prove modality support. See
[video evidence](../plans/google-ai-studio-tools-multimodal/video-input/evidence.md).

Generated image output remains **Partially implemented behind a startup gate**. Each eligible
synthetic request owns one of two nonqueued output slots before quota or credit admission,
including actual worker readiness, provider wait, failover, inspection and child cleanup.
Saturation and unavailable workers return503 without provider traffic. Cancellation retains
child capacity through kill/reap. All billable outcomes retain the full estimated image reserve;
known multimodal usage updates public usage and input quota without reducing that reserve.

Full HTTP Linux measurements use synthetic providers, network disabled,512MiB/2CPUs and clients
that release consumed output before requesting another artifact. They do not establish provider
codec, pricing, thinking-disable or production behavior. Preserve the recorded failed resource
runs and scope limitations in [evidence](../plans/google-ai-studio-tools-multimodal/generated-image/evidence.md).
Current zero-paid-spend live authorization excludes paid-only image models.

Image-input-enabled output pools reserve both global output capacity units, so they admit one
request at a time. Output-only pools reserve one unit and can admit two. Health probes share
capacity; under load readiness may report the inspector busy. Both units remain owned through
cancellation and child reaping. This implementation remains gated; no production enablement.

Generated success output capacity transfers after billing to an outer pure ASGI delivery owner
in the application. It holds the same weighted lease until actual response-start/body sends
complete or fail, using the original reservation deadline. Existing HTTP middleware buffers
cannot release it early. Timeout/cancellation keeps settled billing and releases capacity;
there is no retry or replacement success after sending begins. This remains a gated feature.

The generated-output delivery owner also owns the request-drain decrement after successful
response transfer. It runs once after final send/error/cancellation, including cancellation before
response-start; generated artifacts do not depend on a middleware body iterator starting to
finish drain accounting. Ordinary response and SSE drain behavior remains unchanged.

Generated audio is **Partially implemented behind an unconditional startup gate**. WAV output
reserves both shared output units before quota, credit or provider traffic; saturation returns503.
The finite PCM header/base64 inspector uses no codec or PNG worker, and readiness checks a
bounded WAV self-test. The same reservation deadline, outer delivery owner and drain cleanup
apply after settlement. All billable outcomes keep the full conservative audio reserve;
provider400/403/429 admission failures refund according to existing policy, while ambiguous
5xx/cancellation retain consumption. No inference or production enablement has been performed.
Maximum, malformed-WAV and corrected mixed PNG/WAV Linux synthetic measurements passed;
the initial fixture credit-partition failure remains retained. Independent scoped deep review
cleared the runtime, and zero active reservations passed; exact-model live gates remain. See [evidence](../plans/google-ai-studio-tools-multimodal/generated-audio/evidence.md).

Signed continuation fresh-process replay is **Implemented locally under the startup gate**: 
sequential independent Python3.14 and Linux3.12 SDK/ASGI fixtures retain native signatures,
charge each request and reject changed keys before dispatch. This is synthetic process evidence;
container/TCP restart, maximum combined media/state and exact-model live gates remain open.
See [evidence](../plans/google-ai-studio-tools-multimodal/signed-continuation/evidence.md).

Signed quote-heavy intake uses a bounded escaped-run scanner while retaining strict JSON depth,
byte/node, duplicate-key and nonfinite rejection. Local optimization verification passed; the
full synthetic SDK125itemmaximum-history workload still failed128MiB incrementalRSS/50msloop
limits despite correctcompletions/billing/cleanup. Profiles remain startup gated. A passing
onecaller or scanner microbenchmark does not establish concurrency readiness; see
[resource attribution plan](../plans/google-ai-studio-tools-multimodal/signed-continuation/resource-attribution-design.md).

Signed continuation remains **Partially implemented**, with startup disabled pending aggregate
resource and exact-model live gates. In test configurations containing a bound-history pool,
Responses JSON intake uses two shared signed-work slots before buffering the body. Slow readers
hold their slot until the original intake deadline; saturated requests return safe 503 without
reading the body. Declared oversized bodies return 413 during header checks; unknown-size bodies
can return 503 before their size is known. Unsigned parsing outside those configurations and
embeddings retain their ordinary intake path. This bounds router-owned offloaded body buffers,
not client or HTTP transport memory. Runtime callers supply the original intake deadline.

Timeout or cancellation closes the request's lease but does not release capacity while a parser
thread still runs. Late abandoned parser failures are consumed locally without logging raw
exceptions; active callers still receive normal failures. Resource failures and verified limits
are recorded in [signed continuation evidence](../plans/google-ai-studio-tools-multimodal/signed-continuation/evidence.md).

## Compatible aggregate usage

Google compatible text may report an aggregate token total greater than prompt plus
completion, without separate reasoning detail. The router conservatively attributes that
unsplit excess to output accounting, preserving the aggregate total in Responses and local
settlement. This does not establish reasoning-token semantics or authoritative billing.
Incomplete final stream usage keeps conservative reservation settlement; frames never mix
known output from an earlier snapshot with later partial usage. See the
[usage correction](../plans/google-compatible-usage-integrity/index.md).

The bounded 3.8 live diagnostic verified corrected local Responses nonstream on projects 2–5
and streaming on projects 1/3/4/5; native all five. Project2 streaming exhausted503retries;
project 1 corrected nonstream returned 503. Retain these operation-specific eligibility limits
and preserve original failures. Production3.8 enablement has not been deployed.

## Google canary pre-deployment verification

Default-off `google_pre_output_failover: true` is **Implemented locally** for unmetered Google backends only. It permits existing routing to fail over once to a different eligible backend on pre-output HTTP500/502/503/504, with fresh quota admission and retained first-attempt consumption. It adds no same-key retries and never fails over after any public SSE event. Auth, protocol and ambiguous transport/deadline failures remain terminal; metered behavior is unchanged.

The [one-replica canary](../plans/google-38-production-canary/evidence.md) was not deployed: project3nonstream and project4stream each exhausted three live Google503 attempts. Project4nonstream passed; streaming/cancellation gates remain open. A future separate Google-only canary requires durable quota bootstrap to preserve daily consumption across restart. Existing Azure production, Table cut-over and scale-out remain unchanged; no collector was deployed.
