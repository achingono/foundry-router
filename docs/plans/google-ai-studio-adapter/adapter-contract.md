# Planned Adapter Contract

## Status and Boundary

**Design target** for the first release. W1 must confirm provider-specific fields and Responses
event schemas against the references in [Inputs](inputs.md) before implementation.

Proposed files are `api/adapters/base.py`, `api/adapters/azure.py`, and
`api/adapters/google_ai_studio.py`; add a framing helper only if it keeps the Google translator
small. The adapter protocol exposes capability checking, request conversion, response/error
conversion and a per-request incremental stream decoder. It uses typed transport-neutral
values. `api/routes/openai.py` packages client errors; `forwarding/` invokes conversion inside
its existing HTTP lifecycle. Adapters do not import route handlers, issue HTTP requests,
select backends, alter stores or construct credential headers.

The request remains immutable. Each attempt resolves its own adapter and converts from the
original logical model/body. The backend client substitutes the configured provider model once
and owns the allow-listed URL and credential. Azure uses identity conversion, preserving its
Responses v1 and deployment-scoped embeddings behavior and raw SSE byte contract.

Forwarding needs a typed outcome carrying public response/events, normalized usage if known,
whether dispatch occurred, whether generation may be billable, and retry eligibility. Extend
the existing `BackendRequestResult`/settlement boundary minimally; do not use downstream HTTP
status alone to decide whether failed translation releases a successful provider generation.

For Google, classify attempt outcomes as confirmed pre-dispatch, confirmed non-generation
rejection, or potentially billable. Retry/failover is allowed only for the first two classes
and only under the existing attempt/delay bounds. Partial writes, response-read failures,
timeouts after dispatch and truncated successful streams are potentially billable: retain
quota consumption, settle known usage or the credit estimate, and stop without another
dispatch. Do not overwrite the credit reservation with a second attempt. A 5xx is not proof
of non-generation; W1 must document any safely retryable provider rejection classification.
This deliberately narrows Google retries while leaving the existing Azure policy intact.

## First-Release Request Matrix

| Public input | Google mapping or outcome |
| --- | --- |
| `model` | Route by configured logical alias; send the selected backend's `deployment`; return the logical alias |
| `input: "text"` | One user message with text content |
| `input` message array | Preserve ordered `system`, `developer`, `user`, `assistant` text history; normalize developer instructions to the supported system representation without changing order; reject if W1 cannot establish safe equivalence |
| Text content parts | Accept role-appropriate `input_text`/`output_text` and text strings; preserve text and part order, with no silent dropping |
| `instructions` | System instruction preceding input history; include it in the admission estimate |
| `max_output_tokens` | Positive bounded integer mapped to the verified Google token-limit field; send an enforced limit matching the reservation when omitted by the caller |
| `temperature`, `top_p` | Validate supported numeric ranges; map only where W1 confirms provider support |
| `stream` | Boolean; for streaming request the documented usage option if available |
| `store: false`, `background: false`, `include: []` | Explicitly accepted stateless/no-background/no-extra-output values; omit upstream |
| `metadata` | Validate Responses limits; retain only for public response echo, never logging or forwarding it to Google |
| `previous_response_id`, nonempty `conversation`, `store: true`, `background: true` | Reject with HTTP 422 and `unsupported_parameter` before reservation/egress |
| Tools, tool choice, function-call items/results, structured `text.format`, reasoning, images, audio, files, provider extensions, other unlisted fields | Reject with HTTP 422 and `unsupported_parameter` or `unsupported_input` before reservation/egress |

Validate nested keys and content types as well as top-level fields. Do not stringify arbitrary
JSON, coerce booleans to numbers, silently discard fields, or accept Chat Completions `messages`
as a replacement for Responses `input`. Freeze explicit default/null handling in W1 fixtures.
An empty/invalid required input uses the existing request validation error convention.

When a mixed-provider pool contains a capable Azure backend, exclude incompatible Google
candidates without rejecting the valid Azure request. If no configured candidate supports the
operation, return HTTP 422 `unsupported_operation`; if candidates support the operation but
none support the request features, return the relevant unsupported-field error. If capable
candidates exist but are unhealthy/exhausted, preserve the existing 429/503 behavior.
Use identical eligibility during initial routing and failover, before either store reserves.

## Non-Streaming Responses

Accept only a valid Google Chat Completions success envelope with the expected single choice,
assistant message and documented finish reason. Generate stable router-owned response/message
IDs per response; return `object: "response"`, `created_at`, logical `model`, `status`, ordered
`output` message/content items, `error`/`incomplete_details` as appropriate, and normalized usage.
Build the remaining required fields from the pinned Responses contract and accepted request.

- A normal text stop becomes a completed assistant `output_text` message.
- An output-token limit becomes `status: "incomplete"` with the documented reason, preserving
  partial text and valid usage.
- A documented safety/refusal outcome becomes a supported refusal item or an explicit safe
  terminal failure, as fixed in W1. Never invent successful empty text to hide a blocked result.
- Unexpected tools, malformed success JSON, impossible choice counts, invalid usage, unknown
  finish reasons and contradictory response data produce a bounded, sanitized protocol error.
  Missing usage is allowed and retains conservative internal estimates; invalid usage is never
  trusted. Do not present estimates as provider-reported usage or fabricate zero usage.

Map `prompt_tokens` to `input_tokens`, `completion_tokens` to `output_tokens`, and a valid total
to `total_tokens`. Preserve verified cached/reasoning details only when semantics match; do not
add reasoning counts again if they are already included in completion tokens. Parse usage
independently and pass it to settlement even when output normalization fails.

Read Google bodies incrementally with explicit finite limits, including non-streaming successes
and error bodies. `AsyncClient.request()` currently buffers before returning: use the allowed
client's streaming transport for bounded Google reads instead of checking `.content` afterward.
Count decoded bytes, including compressed or chunked bodies without `Content-Length`, and
close promptly on a breach. A limit breach is a protocol failure with conservative accounting.
Recalculate the content type and omit upstream content length/encoding/ETag after translation. Retain only
the existing safe `Retry-After` and `Cache-Control` header policy.

## Streaming Responses

Use an incremental byte/SSE parser supporting split UTF-8 and delimiters, CRLF/LF, multiple
events in a chunk, multiline `data:` values, comments and empty keepalives. Do not treat raw
HTTP chunk boundaries as event boundaries. Request identity encoding or consume decoded
bytes; compressed HTTP bodies must never be parsed as raw SSE.

After validating a translatable provider event, synthesize the pinned Responses lifecycle:
`response.created`, `response.in_progress`, `response.output_item.added`,
`response.content_part.added`, zero or more `response.output_text.delta` events, corresponding
text/content/item done events and exactly one `response.completed` or `response.incomplete`
terminal event. Refusal/error streams use the corresponding verified schema. Every event has
consistent response/item IDs, output/content indexes and monotonically increasing sequence
numbers. Do not forward `chat.completion.chunk` or synthesize Responses events from raw chunks.

Do not declare completion on the first `finish_reason`: Google may send usage afterward.
Wait for the documented terminator, preserving the usage-only event; EOF without the required
terminal evidence is a truncated-stream failure. Handle duplicate termination deterministically
without duplicate settlement. Capture valid usage before discarding provider framing.

Stream text deltas as they arrive. Bound the assembled text needed for final Responses done
events and terminal output, provider event bytes, queued events, idle wait and total lifetime.
Configure/document finite limits. Establish an absolute request deadline at initial reservation
creation, below its expiry with cleanup headroom; retries/failover must preserve that deadline.
Include retry waits, provider prefetch, translation and downstream backpressure in the remaining
budget, rather than starting a fresh timer when the stream begins. A size/time breach emits one
sanitized failure outcome when the client is still writable and closes the upstream;
never accumulate arbitrary output or silently truncate a successful final response.

Forwarding owns the commit boundary. No synthetic lifecycle event is sent before the first
validated translatable upstream event; after the first downstream event there is no retry or
failover, even if no text delta has been delivered. Pre-commit failures can use bounded retries
only when classified as confirmed pre-dispatch or non-generation rejections; ambiguous
dispatched attempts and malformed provider schemas are terminal failures.
Use `response.failed`/documented error events for post-commit failure, without a second success
terminal event. On client disconnect, stop generation and run shielded bounded cleanup.

Transport-close failure cannot suppress independent credit/quota/metrics cleanup. Billable
success, incomplete output, truncation and post-output failure settle known actual usage or
the conservative reservation exactly once. No upstream body, prompt or output is logged.

## Embeddings

Use the existing Google compatibility embeddings operation and a separately configured model
with `supported_operations: ["embeddings"]`. Accept a string or nonempty list of strings;
initially support float encoding only. Accept requested dimensions only when the selected
model's documented support can be validated; otherwise reject before egress. Reject token-ID
inputs, base64 output requests and unsupported fields explicitly.

Validate the response list, item count and indexes against input order, finite numeric vectors,
consistent dimensions and valid reported usage. Return the logical model alias and standard
OpenAI embedding objects. Do not fabricate missing usage. Use zero output tokens for internal
embedding settlement. Preserve per-request quota admission and reconcile actual input tokens;
provider batch charging must be confirmed in W1 before accepting multi-input batches.

## Errors, Security and Configuration

Use safe OpenAI error objects with bounded messages and stable codes; do not relay provider
error bodies. Client validation errors do not cool a backend or consume a retry. Upstream
401/403 are backend authentication/configuration failures, not client-auth failures; report
a sanitized 502, avoid retries/key cycling for the same rejected request, and expose an
actionable backend-ID diagnostic. Apply backend-local `ERROR_COOLDOWN` using the existing
bounded configured cooldown so subsequent requests can select healthy keys; do not penalize
the whole quota group for one invalid credential. Expiry permits a later probe through normal
traffic; operators may remove/disable or rotate the failing key. Test repeated requests before
and after expiry. Upstream 429 and explicitly classified non-generation retryable 5xx retain
bounded cooldown/failover, including project-group cooldown and bounded `Retry-After` parsing.

Only configured HTTPS origins/base paths may receive credentials; redirects remain disabled.
Reject caller-supplied operation/path/endpoint overrides and credential-bearing query strings,
including Google's `key` parameter. Header stripping must cover backend and client credentials.
Validation errors, logs, metrics and diagnostics may identify configured backend/group IDs but
must never include keys, authorization, prompts, outputs or opaque provider response bodies.

Reuse `provider`, `endpoint`, `credential`, `deployment`, `quota_group`, `credit_metered` and
`credit_group`. Keep Google's existing endpoint-root convention; validate/document accidental
double compatibility suffixes rather than constructing duplicate paths. Add only the required
operation declarations and validated resource bounds. Actual endpoint/model/project/credential
values remain operator inputs; examples and tests use clearly synthetic placeholders.

Keep project-group limits conservative when multiple models share a group; record distinct
model quota buckets as a future design. Replica quota shares are not distributed aggregation.
Non-metered opt-out affects dollar credit only; it does not bypass quota. Paid Google balances
and prices remain local operator estimates, with no claim of Google billing synchronization.

## Follow-Up Capabilities

Function tools and structured output are **Planned** follow-ups, not first-release acceptance
criteria. Their plan must cover function declarations/results, streamed argument assembly,
call IDs, parallel calls, JSON schema differences, refusal handling and model-specific limits.
Before claiming Gemini tool round trips, establish how required thought signatures can be
preserved safely through the public API and client history; do not silently drop them or add
an unbounded server conversation cache. Multimodal and native Gemini support need separate
request, cost/quota, security and streaming contracts.
