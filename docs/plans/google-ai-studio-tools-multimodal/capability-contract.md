# Tools and Multimodal Capability Contract

## Status and Ownership

**Design target**. Every new field or behavior below is proposed; T1 must pin exact vendor
and public-client schemas. This contract extends the predecessor's immutable request, typed
attempt outcome, bounded transport/SSE and independent settlement/cleanup requirements.

| Boundary | Planned responsibility |
| --- | --- |
| `api/adapters/` | Tool/schema/media protocol validation and conversion; per-request stream state; typed capability decisions |
| Small adapter helpers | Bounded schema validation, media metadata inspection and continuation-envelope handling only where independently testable; avoid a generic plugin framework |
| `auth/` | Stable internal authenticated-caller scope if a sealed continuation extension is enabled; no caller-supplied identity |
| `config/` | Validated per-backend surface, feature profile, supported combinations, media/resource limits and optional continuation-key references |
| `backends/` | Configured origin/base-path enforcement, surface-specific operation mapping and credential injection; no media URL fetcher |
| `routing/`, `credit.py`, `ratelimit.py` | Candidate eligibility, conservative feature-aware estimates/prices, reservations and attempt consumption |
| `forwarding/`, `cleanup.py` | Deadline/backpressure, terminal outcomes, usage normalization and exactly-once settlement/cleanup |

The planned base adapter remains small. Add focused `google_tools.py`, `google_media.py` or
`google_native.py` only when actual responsibilities justify them. No provider adapter may own
a global conversation cache, execute tools, fetch schema/media URLs, or create another HTTP pool.

## Capabilities and Routing

Extend `supported_operations` with a validated feature profile on each configured Google model
backend. Proposed profile dimensions include function tools, parallel calls, JSON-object/schema
text, inline images, inline PDFs, audio/video input, generated image/audio output, supported
combinations, and continuation policy. Omitted new capabilities are disabled. Profiles identify
an API surface and bounded media/schema settings; they do not trust a client feature claim.

Capability eligibility is the intersection of adapter implementation, operator-declared model
support, the request's exact combination of features, and any continuation binding. A model
supporting tools and images individually is not automatically enabled for tools plus images.
Apply the same rules before reservation and on failover. Preserve valid Azure requests by
excluding incompatible Google backends rather than globally tightening Azure input schemas.

Declare continuation policy at the logical-pool boundary as well as on backend profiles. A pool
that enables a signature-dependent backend uses `bound_history_required`: any function-call
history must include a valid continuation carrier before candidate filtering, even if another
healthy Google/Azure backend would accept unsigned history. A missing or stripped carrier is
a request error, never an opportunity to select an unbound backend. Keep ordinary unsigned tool
workflows in a separate pool; reject inconsistent pool/backend continuation settings at startup.
This conservatively restricts mixed pools and does not change Azure-only unsigned pools.

If no configured candidate can support the request, return a safe 422 before egress. If capable
candidates exist but are cooled/exhausted, retain 429/503 semantics. Readiness validates enabled
profiles, parser/price/key completeness and usable pool entries; it does not claim to probe live
feature availability. Admin diagnostics expose configured feature IDs, never signatures or keys.
Model discovery keeps logical IDs and must not advertise unverified capabilities as universal.

## Function Tools and Results

| Responses concept | Planned Google compatibility mapping |
| --- | --- |
| Function declaration in `tools` | Chat tool `{type: function, function: {name, description, parameters, ...}}`, preserving verified strictness semantics |
| `tool_choice` | Verified mappings for `auto`, `none`, `required` and a named declared function; reject unsupported values/combinations |
| `parallel_tool_calls` | Pass only when honored by the selected model/surface; enforce serial/parallel output contract |
| `function_call` output item | Separate stable router item `id`, provider `call_id`, declared `name`, JSON-string `arguments`, status and required continuation carrier |
| Previous `function_call` input items | Reconstruct the original ordered assistant `tool_calls` turn, preserving IDs, arguments and verified opaque provider state |
| `function_call_output` input item | Tool-role message with matching `tool_call_id`; initial result content is bounded text only |

Parse ordered histories without collapsing tool results into user messages. Require unique IDs,
valid declared names and exact argument bytes/semantics under the pinned protocol. Every tool
result must match one preceding unresolved call in supplied history; reject orphans, duplicate
results and cross-turn ID reuse. Require a complete result set for each parallel turn before
resuming generation in the initial implementation. A turn may contain text and multiple calls;
preserve item order. The router does not persist history; callers replay the required history.

The caller executes tools and supplies results in a new request. The router never interprets
arguments as commands, retrieves a requested path or URL, or runs another inference automatically.
Treat generated arguments and caller results as untrusted data. Built-in/hosted tools are rejected
explicitly. Media-valued tool results are a later combined-capability contract, not implicit image
support. A tool name or continuation token does not authorize access to any external system.

Validate function names/counts, argument JSON, object shape, schema depth/size and required fields
with a bounded shared validator. Preserve declaration semantics; never remove `strict`, required
fields, enums or constraints to make a provider accept the schema. Provider calls to undeclared
tools, duplicate call IDs, malformed completed arguments or invalid strict-schema values are
billable protocol failures, settled under the predecessor policy.

## Streaming Function Calls

Maintain a bounded map by provider choice/call index. Preserve fragmented names/IDs and assemble
interleaved arguments separately; never dispatch a tool from a delta. Once call identity is known,
emit stable `response.output_item.added`, documented `response.function_call_arguments.delta`
events, validated argument completion and `response.output_item.done`, then the response terminal
event. Pin the exact schemas and sequence-number rules in T1.

Do not mark a call completed until its arguments and required continuation state are available
and validated. Partial/length-limited arguments remain incomplete; no invented closing braces or
synthetic successful calls. A malformed late call terminates the response safely, without retry
or replay of earlier calls. Clients must use completed call/response outcomes, not speculative
deltas, as execution triggers; test the actual client integration behavior. Native APIs that emit
only complete arguments may yield one argument delta after completion; do not fabricate timing.

Keep the predecessor's no-retry-after-first-downstream-event rule, late terminal usage handling,
absolute initial-reservation deadline, bounded arguments/items/total output, and independent
cleanup on cancellation or disconnect. Argument completion does not imply response usage has
arrived or that quota/credit may be released early.

## Thought Signatures and Continuation State

T1 must determine where each supported model/surface returns signatures, which turns/parts need
them, whether they arrive during streaming, and the required replay ordering. Treat them as opaque
provider state; never interpret them as visible reasoning, fabricate them, discard required bytes,
merge/reorder signed parts, or place them into prompts. A native transport does not by itself solve
loss through the public Responses client.

Prefer a documented standard carrier only if both the provider mapping and the pinned Responses
client preserve it losslessly. Do not repurpose a Responses reasoning/encrypted-content field
with unrelated Google data. If no such carrier exists, the concrete fallback design is a versioned,
explicitly opt-in router extension, provisionally `foundry_provider_state`, attached to the
replayed output items. Its name/schema must be approved in the T1 API decision and documented as
an extension. Request negotiation and full-history replay must be tested through the real client;
unknown fields being silently discarded is a failed capability gate.

The extension carries a bounded authenticated-encrypted envelope produced with a vetted library,
not custom cryptography. It contains only the opaque provider state and binding data needed to
replay it, not prompts or a copy of the whole conversation. Bind it to the authenticated caller,
logical model, exact backend/model/surface/configuration generation, originating response/call
IDs, ordered signed output parts and a canonical digest of the replayed history prefix. Exclude
the envelope itself from that digest. Specify canonicalization and signature-to-part association
in T1; a mismatched or rewritten history is rejected, not silently repaired.

The current auth layer does not expose a principal. Add a nonpublic caller scope derived from
the matched configured client credential under a server secret; never use `x-request-id`, a
client-provided user ID or a raw API key in the envelope. Client-key rotation invalidates prior
bindings unless an explicit, reviewed stable-principal mapping exists. The envelope contains
a version, key ID and expiry; cap its encoded/decoded size and state lifetime. Server envelope
keys come from secret configuration, with bounded overlapping decryption keys for rotation and
readiness failure if an enabled profile lacks valid keys. No secret values appear in examples.

Only validate/decrypt allowed versions and key IDs, enforce expiry/binding before reservation,
and reject missing/invalid/reordered state with a safe `invalid_provider_state` 422. Bindings pin
continuations to the original backend; do not reroute signed history to another key/project,
model, provider or surface until portability is proved and separately reviewed. If the pinned
backend is unavailable return the appropriate 429/503; a removed or changed binding requires a
fresh stateless conversation. Test rotation, restart and deployment-drain behavior.

Enforce the pool's history requirement before checking for optional envelope presence or ranking
candidates. If a bound-history pool also has an unsigned backend, that backend may serve fresh
stateless requests only unless it can emit the reviewed authenticated binding for its own replay
history. Until that universal carrier contract exists, exclude it from tool-generating requests
in the bound-history pool. Test dropped state against otherwise healthy unsigned alternatives.

The envelope is not a replay-prevention or billing token: a valid repeated request is newly
authenticated and newly charged, with a fresh server-owned reservation. Tools still execute
only in the caller. No server conversation cache is added. If neither a tested standard carrier
nor the reviewed extension is usable by a client, disable signature-dependent tool capability
for that client/profile and explain the limit; do not claim general coding-agent compatibility.

## Structured Text and Schema Limits

Map Responses `text.format` JSON-object and JSON-schema requests to the exact supported Google
format/configuration. Pin `name`, `schema`, `strict` and default semantics. Support a declared,
bounded JSON Schema subset common to the public and provider contracts. Reject unsupported
keywords, unbounded recursive expansion, remote references and dangerous validation patterns
before egress. If local references are supported, limit expansion/depth/work and reject cycles.

Use deterministic local validation for completed strict outputs as well as tool arguments. Do
not turn a provider's best-effort JSON mode into a strict guarantee, change the schema, repair
output JSON, or silently downgrade `strict: true`. Refusal and length limits retain their own
outcomes; schema-invalid completed output becomes a safe billable protocol failure. Streamed
JSON/text deltas are provisional until the completed object is validated; do not emit a successful
terminal event first. Test tools plus structured text only when the combined capability is enabled.

## Media Intake and Mapping

| Capability | Initial public form / gate | Provider mapping and limits |
| --- | --- | --- |
| Images | Responses `input_image` with inline data URI; mixed text/image content | Verified image content parts; initially declared JPEG/PNG/WebP subset only; actual format/dimensions and detail semantics validated |
| Documents | Responses `input_file` with bounded inline PDF `file_data` and safe display filename, if verified in T1 | Compatibility file part or explicitly configured native inline data; enforce page/byte/complexity bounds |
| Audio input | Only a verified public item shape or an explicitly reviewed versioned extension | Bounded finite audio; validate MIME/codec/channels/sample rate/duration before enabling |
| Video input | Separate public-schema decision; not assumed to be an `input_image` | Bounded clip/frame/time semantics and verified timestamps/frame-sampling policy |
| Image/audio output | Separate public-schema and streaming decision | Bounded artifact bytes/items/duration, public content-type/event framing, output usage and safety semantics |

Do not invent `input_audio`, video or binary output fields and call them standard Responses.
Increment C must document whether a current standard shape exists; otherwise review an explicit
extension before code or retain that capability as Planned. Never disguise generated media as
text or an image-generation hosted tool that the router does not implement.

Reject remote HTTP(S) media URLs, provider file IDs, local paths, `file:`, cloud-storage URIs and
credential-bearing URLs before egress, including URLs hidden in otherwise valid media parts.
Do not fetch or pass them for provider fetching. Accept only narrowly validated inline data;
tool-result/plain text containing a URL remains inert text. Schema `$ref` must not trigger
network access either. No Files API upload or cleanup lifecycle is needed for inline delivery.

Validate outer JSON/wire bytes before parsing and encoded lengths before base64 allocation.
Bound aggregate decoded bytes, part count, pixels, pages, frames, duration, channels and output
artifacts independently; base64 overhead and transformed-request copies count toward memory.
MIME declarations and file extensions are not proof: verify payload type and relevant metadata
with vetted, bounded parsing, reject encrypted/unsupported files, malformed payloads and
decompression bombs. Do not render PDFs, execute embedded scripts, OCR, transcode or follow
embedded references. File names are display labels and must never become filesystem paths.

Use per-request work/deadline/memory limits for media inspection; if a parser cannot be safely
bounded in process, require a resource-limited worker design review or keep the format disabled.
Start an intake deadline/work budget before pre-admission schema/media/state validation; no
reservation exists yet to bound that work. At admission, establish the initial reservation
deadline with cleanup headroom and use the earlier of the remaining intake lifetime and the
reservation deadline thereafter. Neither clock restarts on failover, streaming or backpressure.
Retain no media after request cleanup and avoid on-disk spooling. Start with the existing 2 MiB
body cap; any increase needs concurrent-load measurements and explicit memory admission.
Preserve text/media ordering and content roles; never replace images/PDFs with filenames, base64
text or invented textual summaries. Unsupported `detail`/resolution settings fail explicitly.

## Modality-Aware Estimates, Pricing and Quota

Extend estimation before enabling a feature. Count instructions, tool names/descriptions/schemas,
function-call history/arguments/results, structured-format instructions and provider overhead as
well as user text. Media must use verified conservative token/work bounds based on validated
pixels/pages/duration/frame limits, not base64 character count or caller-supplied usage estimates.
Opaque signature/envelope bytes are not text tokens; account only for documented provider effects.

Prefer deterministic local upper bounds, recorded per configured model/profile. If no safe bound
exists, keep the capability disabled; a provider `countTokens` preflight would be an explicitly
designed new operation with its own allow-list, quota, latency, privacy and failure accounting,
not an unmetered helper hidden inside validation. Enforce output token/media limits upstream.

The current one-input/one-output token-price pair may not cover media or reasoning prices. Reuse
it only when verified equivalent. Otherwise extend the pricing boundary with explicit required
dimensions and reserve the summed worst-case cost, with no missing dimension defaulting to zero.
For heterogeneous pools use a conservative pool-wide pricing bound or add separately reviewed
candidate-specific prices; never select a cheaper estimate and dispatch a more expensive modality.
Use separate logical pools where the current model-based pricing cannot preserve this invariant.

Quota and dollar credit remain separate. Non-metered free backends still need media/token/work
and quota limits. Model-specific additional quota dimensions that the current store cannot
enforce are capability blockers until a scoped accounting extension is designed; do not treat
RPD/RPM alone as complete admission. Keep project grouping conservative and replicas at one.

Normalize provider usage by modality/cache/reasoning only after confirming totals and inclusions,
avoid double counting, and pass valid usage to settlement even on schema/media conversion failure.
Missing usage retains the complete reserved estimate; never return invented provider usage.
Every tool-result HTTP turn gets new reservation ownership. Preserve no retry after downstream
output or ambiguous Google dispatch, backend-local auth cooldown and absolute reservation expiry.

## Native Surface and Additional Media Gate

Add a proposed `api_surface` selector (`openai_compat` default, `native` opt-in) only if T1 finds
a concrete in-scope capability unavailable through compatibility. Keep the provider discriminator
`google_ai_studio`; do not model the same key as a new provider to bypass quota/credit groups.
Validate surface/model/capability combinations before startup readiness succeeds.

If native is needed, implement its contents/parts, function declarations/calls/results,
generation/schema configuration, safety/finish reasons, usage metadata and SSE normalization in
a separate adapter behind the same typed interface. Backend transport owns an explicit allowed
mapping to `generateContent`/`streamGenerateContent` with the configured model and safe API-version
path/query; a body field may not choose a URL. Native tool/signature semantics require their own
fixtures and live evidence. No automatic surface switching during retry/failover is permitted.

For generated media, freeze public non-streaming and streaming forms, incremental binary/base64
framing, finite artifact/aggregate bounds and usage semantics first. Avoid giant single SSE events;
if no supported bounded event representation exists, enable only bounded non-streaming output
and reject streaming before dispatch. No server hosting/download URLs are introduced. Media
output may be enabled only after pricing, safety outcomes, parser/resource gates and compatible
client consumption pass. Audio/video/image-generation success are separate evidence claims.
