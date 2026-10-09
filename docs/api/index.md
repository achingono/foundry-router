# Public API

## Status: Implemented locally; scoped Google Responses text live verification passed; embeddings live verification and `chat/completions` remain unverified/Planned respectively

The service exposes an OpenAI-compatible base URL such as `https://<host>/openai/v1`. Clients provide the logical model name; the current implementation forwards Responses and embeddings requests using deterministic weighted ordering with health-aware retry, cooldown, and single failover. Equal-weight candidates use the lexicographically smallest backend ID.

Azure Responses uses `POST {endpoint}/openai/v1/responses` without an API-version query, substituting the selected deployment name into the body `model`. Azure embeddings retains `POST {endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}`. The initial backend is the highest-weight healthy candidate for the model, with backend ID used as the deterministic tie-breaker. Azure SSE bytes are forwarded unchanged; bounded usage inspection accepts terminal `response.usage` as well as top-level usage.

## Google AI Studio Adapter (Implemented; scoped text live verification)

Configured `google_ai_studio` backends use an explicit Responses/embeddings protocol adapter (`src/foundry_router/api/adapters/`). Google's compatible routes are `POST {endpoint-root}/v1beta/openai/chat/completions` and `POST {endpoint-root}/v1beta/openai/embeddings` with server-owned Bearer authentication. Client authentication is never forwarded. [Live simple-text Responses and streaming](../plans/google-compatible-signature-text/evidence.md) passed for exact `gemini-3.5-flash-lite` on projects 2–5. These samples do not establish embeddings, other models, tools, signed continuation, production enablement or unbuffered stream latency/cancellation. The baseline embeddings subset and opt-in [tools, structured text and bounded inline image input](../operations/google-features.md) retain local mocked verification and separate live gates.

| Public input | Google mapping or outcome |
| --- | --- |
| `model` | Route by logical alias; send the backend `deployment`; return the logical alias |
| `input: "text"` | One user message |
| `input` message array | Ordered `system`/`developer`/`user`/`assistant` text history (`developer` normalizes to `system`); `input_text`/`output_text`/`text` parts preserved in order |
| `instructions` | System instruction preceding history; included in the admission estimate |
| `max_output_tokens` | Positive bounded integer mapped to `max_completion_tokens`; the reserved bound is enforced upstream when omitted |
| `temperature` (0-2), `top_p` (0-1) | Validated and mapped |
| `stream: true` | Upstream requests `stream_options: {"include_usage": true}`; downstream emits Responses lifecycle events |
| `store: false`, `background: false`, `include: []` | Accepted stateless values; omitted upstream |
| `metadata` | Validated; echoed in the public response only, never logged or forwarded |
| `previous_response_id`, stored conversations/background, reasoning, unconfigured features and other unlisted fields | Rejected with HTTP 422 (`unsupported_parameter`/`unsupported_input`) before reservation/egress |

Non-streaming Google success requires a single-choice Chat Completions envelope with an assistant text message and a documented finish reason (`stop` → completed; `length` → incomplete `max_output_tokens`; `content_filter` → incomplete `content_filter`). Usage maps `prompt_tokens` → `input_tokens` and `completion_tokens` → `output_tokens`. Missing usage retains conservative estimates; invalid usage, unknown finish reasons, undeclared/invalid tool calls, and malformed envelopes are sanitized 502 protocol failures. Embeddings accept string/nonempty string lists (float only); the returned count/order/dimensions are validated against the request (including requested dimensions) with mismatches rejected as protocol failures, and actual input tokens are reconciled.

Google streaming decodes Chat SSE incrementally (split UTF-8, LF/CRLF, multiline data, keepalives, multiple events per chunk, usage-only final chunks) and emits ordered Responses events (`response.created`, `response.in_progress`, `response.output_item.added`, `response.content_part.added`, `response.output_text.delta*`, done events, exactly one `response.completed`/`response.incomplete`/`response.failed`) with consistent IDs and monotonically increasing sequence numbers. Post-commit failures emit a schema-valid `response.failed` carrying the same response identity, continued sequencing, and `failed` status. No synthetic lifecycle event is sent before the first validated upstream event; after the first downstream event there is no retry or failover. EOF without the documented `[DONE]` terminator is a truncation failure. Google attempts are single-shot per backend: only 429 is failover-eligible (admitted fresh with both attempts counted); ambiguous dispatched failures (partial writes, read failures, timeouts, truncated 200 streams, 5xx, cancellation after possible dispatch) settle known usage or the estimate and terminate. Google 401/403 enters backend-local `ERROR_COOLDOWN` without same-request key cycling. Reads, prefetch, and delivery are bounded by the reservation deadline, which routing anchors at reservation creation and retains across failover.

Logical model aliases (Implemented with mocked verification) resolve once at API
ingress before admission: the requested name is replaced by its canonical target in
a shallow request copy, while all non-model fields are preserved exactly. Routing,
estimates, reservations, settlement, and metrics use the canonical pool and its
prices; failover never re-resolves. `GET /openai/v1/models` lists canonical models
in configured order followed by configured aliases in sorted order, each exactly once.
`GET /admin/status` adds a separate `model_aliases` map. Upstream response and SSE
bodies are untouched, so the provider's reported `model` may differ from the alias;
live inference and approval-client compatibility remain separately gated.

Opt-in `google_features` profiles support caller-executed function tools and complete stateless
function-call/result history, serial/parallel arguments deltas/done, JSON-object and strict
JSON-schema text, and user bounded inline images `input_image` data URIs. Explicit tool strictness is required;
JSON schema text requires name/schema/strict true. Named choice requires exactly one call.
Generated arguments/text validate locally before a successful terminal outcome; failures remain
billable and never retry. Refusals and token/filter limits preserve distinct public outcomes.
Public output indices are contiguous independently of provider call indices. Call IDs remain
separate from output item IDs and server reservation IDs; every result turn authenticates anew.

PNG defaults to 8-bit RGB/RGBA noninterlaced at <=384×384. Explicit format opt-in also accepts
bounded baseline JPEG (<=128 dimensions, shared384 coded-block budget) and static lossless VP8L
(<=384 dimensions); see the exact [format limits](../operations/google-features.md). Remote URLs,
foreign file IDs, progressive/larger JPEG, lossy/animated WebP, video and generated
media are rejected. Native PDF input is implemented locally. Finite WAV input is partially
implemented and default-off pending gates. Signed continuation remains startup-gated. See [configured bounds and limitations](../operations/google-features.md).

## Endpoints

Configured `openai_compatible` pools provide **Implemented, mocked-verified** Responses
translation to Chat Completions and float embeddings. They support text-only string/history
input, instructions, metadata and existing generation parameters; unsupported tools,
schemas, media and provider state fail before reservation/egress. Streaming uses the shared
bounded Responses lifecycle decoder and requires the Chat `[DONE]` terminator; no failover
occurs after any downstream event. Missing/invalid response usage retains conservative
settlement, including ambiguous dispatched 5xx and cancellation. Logical models/aliases and
operation filtering apply across mixed provider pools. The upstream must accept the fixed
`max_completion_tokens`/`stream_options.include_usage` dialect; live compatibility remains
an exact upstream/model gate. See [configuration](../configuration/index.md).

Configured `openrouter` pools provide the same **Implemented, mocked-verified**
translation contract against OpenRouter's Chat Completions and float embeddings
endpoints. OpenRouter-only caller fields and attribution headers fail before
reservation/egress and are never forwarded.

Configured `opencode_zen` pools provide **Implemented, mocked-verified** Responses
wire pass-through for Zen's Responses-model rows. Accepted bodies keep their Responses
shape with only the provider deployment substituted; SSE bytes stream unchanged with
bounded terminal-usage inspection. The bounded stateless-text gate rejects unsupported
and foreign fields before reservation/egress with a sanitized 422 for Zen-only pools,
while other capable backends in mixed pools remain eligible. Single-shot dispatch
applies regardless of `retry_attempts`; only pre-output 429 is failover-eligible.
Ambiguous dispatched failures and cancellation retain known usage or the full estimate.
Live Zen compatibility remains an exact upstream/model gate.

| Method and path | Requirement |
| --- | --- |
| `POST /openai/v1/responses` | Implemented; normal and streaming forwarding |
| `POST /openai/v1/embeddings` | Implemented; embedding forwarding |
| `GET /openai/v1/models` | Required; list configured logical models and explicit aliases |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Readiness based on usable configuration/backend state |
| `GET /admin/status` | Implemented; authenticated configuration/model snapshots and live health/credit diagnostics (Table-backed code is implemented; multi-replica Azure deployment verification remains pending) |
| `GET /metrics` | Implemented (single-process Prometheus text via `InMemoryMetricsStore`); multi-process aggregation Planned |
| `POST /openai/v1/chat/completions` | Optional **Planned**; must not delay Responses support |

Malformed requests return a clear 4xx without contacting Foundry. Unknown models return an OpenAI-compatible model-not-found error. When credit-safe estimated capacity is unavailable, the router returns `503` with `insufficient_credit_capacity` and does not dispatch upstream. Retry/failover occurs only for retryable upstream failures and never after meaningful streaming output has begun.

Shared-resource credit is **Implemented**. `/admin/status` adds canonical `credit_groups` account
snapshots and a `credit_group` on each backend. Backend credit views are compatible but nonadditive.
`/metrics` adds `foundry_router_credit_group_available_usd{credit_group}` while retaining backend
metrics. Reconciliation adds `last_updated_credit_groups`; the legacy count is a compatibility alias.
Readiness checks unique routable metered accounts. A credit persistence/finalization failure before
response delivery returns `503 credit_store_unavailable`, preventing failover after failed release.
After SSE output, completion failure propagates without a retry. See
[credit operations](../operations/shared-resource-credit.md).

Expired pending reservations now settle conservatively, including legacy/pre-egress rows: retained
valid intent wins, otherwise the full estimate is debited. Ambiguous Table admission stops routing;
context-close errors cannot prevent independently bounded shielded credit/quota/metrics cleanup.
Incomplete Table settings sync returns `503 credit_store_unavailable` without upstream egress.
Post-output stream errors charge actual known usage or the full reserved estimate, preserving the
stream's SSE error and prohibiting failover.

## Authentication

All `/openai/v1/*` endpoints require client authentication. The `/admin/status` and `/metrics` endpoints require separate admin authentication.

### Client Authentication

Provide **one** of:
- Header: `api-key: <your-client-key>`
- Header: `Authorization: Bearer <your-client-key>`

### Client Configuration

Configure clients with the base URL `https://<router-host>/openai/v1` and a logical model ID returned by `GET /openai/v1/models`. This router implements the Responses API; `POST /openai/v1/chat/completions` remains planned.

For OpenCode, use the `@ai-sdk/openai` package, which sends Responses API requests. The `@ai-sdk/openai-compatible` package sends Chat Completions requests and is not compatible with the currently implemented inference route.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "foundry-router": {
      "npm": "@ai-sdk/openai",
      "name": "Foundry Router",
      "options": {
        "baseURL": "https://<router-host>/openai/v1",
        "apiKey": "{env:FOUNDRY_ROUTER_API_KEY}"
      },
      "models": {
        "<model-id-from-models-endpoint>": {
          "name": "<model-display-name>"
        }
      }
    }
  },
  "model": "foundry-router/<model-id-from-models-endpoint>"
}
```

For Codex CLI, configure a custom provider using the Responses wire API:

```toml
model = "<model-id-from-models-endpoint>"
model_provider = "foundry-router"

[model_providers.foundry-router]
name = "Foundry Router"
base_url = "https://<router-host>/openai/v1"
wire_api = "responses"
env_key = "FOUNDRY_ROUTER_API_KEY"
supports_websockets = false
```

Set `FOUNDRY_ROUTER_API_KEY` in the environment that launches each client. Codex's shared app-server inherits its environment when it starts, so restart it after setting or changing the key:

```bash
codex app-server daemon restart
codex
```

Use `codex --no-daemon` to run the CLI without the shared app-server.

### Admin Authentication

Provide **one** of:
- Header: `x-admin-key: <your-admin-key>`
- Header: `Authorization: Bearer <your-admin-key>`

Client and admin keys are configured separately and must be disjoint.

## Request/Response Examples

### GET /health/live

**Request**
```http
GET /health/live HTTP/1.1
Host: router.example.com
```

**Response (200 OK)**
```json
{
  "status": "alive"
}
```

### GET /health/ready

**Request**
```http
GET /health/ready HTTP/1.1
Host: router.example.com
```

**Response (200 OK - Ready)**
```json
{
  "ready": true,
  "checks": {
    "config_valid": true,
    "backends_configured": true,
    "models_configured": true,
    "client_auth_configured": true,
    "admin_auth_configured": true
  }
}
```

**Response (503 Service Unavailable - Not Ready)**
```json
{
  "ready": false,
  "checks": {
    "config_valid": true,
    "backends_configured": false,
    "models_configured": true,
    "client_auth_configured": true,
    "admin_auth_configured": true
  }
}
```

### GET /openai/v1/models

**Request**
```http
GET /openai/v1/models HTTP/1.1
Host: router.example.com
api-key: client-key-123
```

**Response (200 OK)**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-5.6-luna",
      "object": "model",
      "owned_by": "foundry-router"
    },
    {
      "id": "gpt-5.4",
      "object": "model",
      "owned_by": "foundry-router"
    },
    {
      "id": "gpt-5.4-mini",
      "object": "model",
      "owned_by": "foundry-router"
    },
    {
      "id": "gpt-5.4-nano",
      "object": "model",
      "owned_by": "foundry-router"
    },
    {
      "id": "gpt-5.3-codex",
      "object": "model",
      "owned_by": "foundry-router"
    },
    {
      "id": "gpt-5.2-chat",
      "object": "model",
      "owned_by": "foundry-router"
    },
    {
      "id": "text-embedding-3-large",
      "object": "model",
      "owned_by": "foundry-router"
    }
  ]
}
```

**Response (401 Unauthorized)**
```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="foundry-router"
Content-Type: application/json

{
  "detail": "Missing authentication: provide 'api-key' header or 'Authorization: Bearer <key>'"
}
```

### POST /openai/v1/responses

**Request (Non-streaming)**
```http
POST /openai/v1/responses HTTP/1.1
Host: router.example.com
api-key: client-key-123
Content-Type: application/json

{
  "model": "gpt-5.4",
  "input": "Explain quantum computing in simple terms",
  "temperature": 0.7,
  "max_output_tokens": 500
}
```

**Request (Streaming)**
```http
POST /openai/v1/responses HTTP/1.1
Host: router.example.com
api-key: client-key-123
Content-Type: application/json

{
  "model": "gpt-5.4",
  "input": "Write a short poem about Azure",
  "stream": true
}
```

**Response (200 OK - Non-streaming)**
```json
{
  "id": "resp_abc123",
  "object": "response",
  "created_at": 1699999999,
  "model": "gpt-5.4",
  "output": [
    {
      "type": "message",
      "id": "msg_abc123",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Quantum computing uses quantum bits..."
        }
      ]
    }
  ],
  "usage": {
    "input_tokens": 15,
    "output_tokens": 120,
    "total_tokens": 135
  }
}
```

**Response (200 OK - Streaming, Azure Passthrough)**
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"id": "resp_abc123", "object": "response", "created_at": 1699999999, "model": "gpt-5.4", "output": [{"type": "message", "id": "msg_abc123", "role": "assistant", "content": [{"type": "output_text", "text": "Quantum"}]}]}

data: {"id": "resp_abc123", "object": "response", "created_at": 1699999999, "model": "gpt-5.4", "output": [{"type": "message", "id": "msg_abc123", "role": "assistant", "content": [{"type": "output_text", "text": " computing uses"}]}]}

data: {"id": "resp_abc123", "object": "response", "created_at": 1699999999, "model": "gpt-5.4", "output": [{"type": "message", "id": "msg_abc123", "role": "assistant", "content": [{"type": "output_text", "text": " quantum bits..."}]}]}

data: [DONE]
```

**Response (200 OK - Streaming, Google-Translated Shape)**

Google-backed streams emit Responses lifecycle events (not raw `chat.completion.chunk` bytes):

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"type":"response.created","sequence_number":1,"response":{"id":"resp_abc123","object":"response","created_at":1699999999,"model":"gemini-2.5-flash","status":"in_progress","output":[]}}

data: {"type":"response.in_progress","sequence_number":2,"response":{"id":"resp_abc123","object":"response","created_at":1699999999,"model":"gemini-2.5-flash","status":"in_progress","output":[]}}

data: {"type":"response.output_item.added","sequence_number":3,"output_index":0,"item":{"type":"message","id":"msg_abc123","role":"assistant","status":"in_progress","content":[]}}

data: {"type":"response.content_part.added","sequence_number":4,"item_id":"msg_abc123","output_index":0,"content_index":0,"part":{"type":"output_text","text":"","annotations":[]}}

data: {"type":"response.output_text.delta","sequence_number":5,"item_id":"msg_abc123","output_index":0,"content_index":0,"delta":"Quantum"}

data: {"type":"response.output_text.delta","sequence_number":6,"item_id":"msg_abc123","output_index":0,"content_index":0,"delta":" computing uses"}

data: {"type":"response.output_text.done","sequence_number":7,"item_id":"msg_abc123","output_index":0,"content_index":0,"text":"Quantum computing uses"}

data: {"type":"response.content_part.done","sequence_number":8,"item_id":"msg_abc123","output_index":0,"content_index":0,"part":{"type":"output_text","text":"Quantum computing uses","annotations":[]}}

data: {"type":"response.output_item.done","sequence_number":9,"output_index":0,"item":{"type":"message","id":"msg_abc123","role":"assistant","status":"completed","content":[{"type":"output_text","text":"Quantum computing uses","annotations":[]}]}}

data: {"type":"response.completed","sequence_number":10,"response":{"id":"resp_abc123","object":"response","created_at":1699999999,"model":"gemini-2.5-flash","status":"completed","output":[{"type":"message","id":"msg_abc123","role":"assistant","status":"completed","content":[{"type":"output_text","text":"Quantum computing uses","annotations":[]}]}],"usage":{"input_tokens":15,"output_tokens":12,"total_tokens":27}}}
```

**Response (404 Not Found - Unknown Model)**
```json
{
  "error": {
    "message": "Model 'unknown-model' not found",
    "type": "model_not_found",
    "param": "model"
  }
}
```

**Response (429 Too Many Requests - All Candidate Backends In Quota Cooldown)**
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json

{
  "error": {
    "message": "All configured backends are in quota cooldown",
    "type": "upstream_unavailable"
  }
}
```

### POST /openai/v1/embeddings

**Request**
```http
POST /openai/v1/embeddings HTTP/1.1
Host: router.example.com
api-key: client-key-123
Content-Type: application/json

{
  "model": "text-embedding-3-large",
  "input": ["First text to embed", "Second text to embed"],
  "encoding_format": "float"
}
```

**Response (200 OK)**
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.00123, -0.00456, ...]
    },
    {
      "object": "embedding",
      "index": 1,
      "embedding": [0.00789, -0.00234, ...]
    }
  ],
  "model": "text-embedding-3-large",
  "usage": {
    "prompt_tokens": 12,
    "total_tokens": 12
  }
}
```

### GET /admin/status

**Request**
```http
GET /admin/status HTTP/1.1
Host: router.example.com
x-admin-key: admin-key-789
```

**Response (200 OK)**
```json
{
  "version": "0.1.0",
  "backends": {
    "sub_a": {
      "endpoint": "https://foundry-a.openai.azure.com",
      "region": "eastus",
      "deployment": "gpt-4",
      "cycle_start_day": 1,
      "live": {
        "health_state": "ACTIVE",
        "cooldown_remaining_seconds": 0.0,
        "credit_state": "USABLE",
        "available_credit_usd": 180.0,
        "reserved_inflight_usd": 0.0,
        "estimated_remaining_usd": 190.0,
        "active_reservations": 0,
        "current_cycle_start_utc": "2026-08-01T00:00:00+00:00",
        "next_reset_utc": "2026-09-01T00:00:00+00:00"
      }
    },
    "sub_b": {
      "endpoint": "https://foundry-b.openai.azure.com",
      "region": "westus2",
      "deployment": "gpt-4",
      "cycle_start_day": 15
    }
  },
  "models": {
    "gpt-5.4": {
      "backends": {
        "sub_a": 1.0,
        "sub_b": 1.0
      }
    },
    "text-embedding-3-large": {
      "backends": {
        "sub_a": 1.0,
        "sub_b": 1.0
      }
    }
  },
  "config": {
    "reconciliation_interval_minutes": 10,
    "min_credit_reserve_usd": 10.0,
    "min_credit_reserve_percent": 5.0,
    "retry_attempts": 2,
    "retry_max_delay_seconds": 30.0,
    "protected_emergency_fallback": false
  },
  "reconciliation": {
    "last_attempt_utc": "2026-08-21T18:20:00+00:00",
    "last_success_utc": "2026-08-21T18:20:00+00:00",
    "last_error": null,
    "last_updated_backends": 2,
    "consecutive_failures": 0,
    "stale": false
  }
}
```

### GET /metrics

**Request**
```http
GET /metrics HTTP/1.1
Host: router.example.com
```

**Response (200 OK, text/plain)**
```text
# HELP foundry_router_requests_total Total HTTP requests processed by model/backend/status
# TYPE foundry_router_requests_total counter
foundry_router_requests_total{model="gpt-4",backend="backend_a",status="200"} 12
# HELP foundry_router_credit_available_usd Live estimated spendable credit by backend
# TYPE foundry_router_credit_available_usd gauge
foundry_router_credit_available_usd{backend="backend_a"} 124.250000000
```

**Response (401 Unauthorized)**
```json
{
  "detail": "Invalid admin API key"
}
```

## Error Format

All errors follow the OpenAI-compatible format:

```json
{
  "error": {
    "message": "Human-readable error description",
    "type": "error_type",
    "param": "parameter_name",
    "code": "error_code"
  }
}
```

Common error types:
- `model_not_found` - Requested model not configured
- `rate_limit_exceeded` - All backends rate limited
- `insufficient_credit_capacity` - No backend has sufficient safe estimated credit capacity
- `invalid_request` - Malformed request body
- `unsupported_operation` - No configured backend supports the requested operation
- `unsupported_parameter`/`unsupported_input` - Request uses fields no capable backend supports
- `authentication_error` - Invalid or missing credentials
- `upstream_error` - Sanitized backend failure (provider bodies are never relayed)
- `internal_error` - Unexpected server error

## Streaming Behavior

Google provider error envelopes and malformed non-null usage produce a redacted terminal
failure immediately, with backend cooldown and bounded cleanup. Metadata is echoed in
public JSON and SSE response objects and never sent upstream. Blank text history is rejected
before admission; system/developer text-part arrays are flattened in order to system text.
Embedding translation failures use valid reported input-token usage with zero output tokens.

Google delivery uses the same absolute reservation deadline as routing and forwarding.
It bounds actual ASGI response-start and body sends as well as upstream reads. Expiry
closes the stream and runs bounded independent credit/quota/transport cleanup, including
when repeated cancellation interrupts a blocked connection close. Confirmed expiry before
dispatch releases the unused backend reservation; an ambiguous in-flight timeout settles
known usage or the estimate.

Google non-streaming cancellation protection includes normal connection closure and health
updates after a successful read. Reported usage is retained before those awaits, so an
interruption charges known generation usage (or the estimate), retains quota consumption,
and runs bounded connection cleanup without retrying the request.

The same attempt-wide protection applies to Google streaming before downstream handoff,
including health activation after prefetch and HTTP errors while reading error bodies.
Decoded usage remains available for settlement; ambiguous dispatched failures retain quota
and charge known usage or the estimate. Ownership transfers to the downstream response only
after successful handoff.

- Azure SSE events are forwarded without buffering the full response
- Google SSE is translated incrementally into Responses lifecycle events (never raw `chat.completion.chunk`)
- Each event boundary is preserved
- No synthetic Google lifecycle event is emitted before the first validated upstream event
- Errors occurring after streaming begins are forwarded as SSE events
- No retry or failover after meaningful streaming data has been sent (for Google, after the first downstream event, including lifecycle events)
- Google truncation (EOF without `[DONE]`) is a terminal `response.failed` outcome, never a successful completion
- Empty pre-output chunks are bounded by the router's pre-first-byte timeout and empty-chunk budget
- Stream cleanup runs on successful completion, upstream failure, status-body read failure, and cancellation
- `Retry-After` headers from upstream are honored within configured maximum delay

## Headers

### Request Headers (Client → Router)

| Header | Required | Description |
| --- | --- | --- |
| `api-key` | Yes* | Client API key |
| `Authorization` | Yes* | Bearer token (alternative to api-key) |
| `Content-Type` | Yes | Must be `application/json` |
| `x-request-id` | No | Optional correlation ID (generated if absent) |

*One of `api-key` or `Authorization` required for `/openai/v1/*`

### Request Headers (Admin)

| Header | Required | Description |
| --- | --- | --- |
| `x-admin-key` | Yes* | Admin API key |
| `Authorization` | Yes* | Bearer token (alternative to x-admin-key) |

*One required for `/admin/status` and `/metrics`

### Response Headers (Router → Client)

| Header | Description |
| --- | --- |
| `x-request-id` | Correlation ID for tracing |
| `WWW-Authenticate` | On 401: `Bearer realm="foundry-router"` |
| `Retry-After` | Returned for retryable upstream or exhausted-cooldown responses when available |
| `Cache-Control` | Returned when supplied by the upstream response or required for streaming |

Only `Retry-After` and `Cache-Control` are eligible for propagation from upstream responses. The router does not forward cookies, authorization, content-length, hop-by-hop, proxy, backend tracing, or other backend-specific response headers.

### Forwarded Headers (Router → Backend)

Only safe headers are forwarded:
- `Content-Type`
- `Accept`
- `User-Agent`
- `X-Request-Id` (router-validated correlation ID)
- Custom headers not in sensitive list

**Never forwarded:** `Authorization`, `api-key`, `x-api-key`, `Cookie`, `X-Forwarded-*`, `Forwarded`

Native Google Responses transport is **Partially implemented** with local fixtures: explicit
backend surface maps to generateContent or streamGenerateContent, normalized to the public
Responses protocol. It accepts only reviewed unsigned/thinking-disabled text/tool/schema/image
profiles. Native SSE terminates at clean EOF with valid finish evidence; compatibility continues
to require `[DONE]`. Surface selection is server configuration and never a public request field.
Native foundation independent review passed; document/resource/live gates remain in progress.

Inline PDF input is **Implemented locally**; exact-model live validation remains pending.
Opt-in native user content uses `{"type":"input_file","filename":"fixture.pdf",
"file_data":"data:application/pdf;base64,..."}`; only canonical inline encoding and bounded ASCII
display filenames are accepted. Google URLs/file IDs/paths remain unsupported. The restricted
parser accepts classic uncompressed PDFs with bounded standard-font text and page trees,
rejecting actions, images/compression, encryption and custom font maps. API preparation runs
before reservation in at most two isolated Linux workers; saturated intake returns503 and
invalid documents422. Azure file inputs retain existing pass-through behavior.

Signed native continuation remains **Partially implemented** behind its startup gate; see the
[reviewed signed design](../plans/google-ai-studio-tools-multimodal/signed-continuation/design.md).
Its synthetic OpenAI Python 2.8.1 tool replay recipe serializes function output items with
`model_dump(exclude_none=True, exclude={"parsed_arguments"})`: the streaming helper adds that
client-only parsed field. Keep the emitted arguments string, IDs, status and state carrier exact.
This does not establish live Google or coding-agent compatibility.

Finite WAV input is **Partially implemented** and default-off. Native-only `inline_audio` accepts
user `input_file` with canonical `data:audio/wav;base64,...`; optional filename matches
`[A-Za-z0-9_.-]{1,60}\.wav`. Only RIFF/WAVE fmt(16)/data, PCM mono 16 kHz 16-bit is accepted:
10 seconds/320044 bytes per file, at most two files/20 seconds/640088 bytes across history.
No IDs, URLs, compression, additional chunks or trailing data. Full caller history retains audio.
Exact combinations require opt-in; generated audio is unsupported. See
[audio evidence and pending gates](../plans/google-ai-studio-tools-multimodal/audio-input/evidence.md).

Finite raw AVI input is **Partially implemented**, default-off pending
[video gates](../plans/google-ai-studio-tools-multimodal/video-input/evidence.md). User input_file
accepts canonical data:video/avi;base64 with optional bounded ASCII .avi filename. Only one
raw24-bit bottom-up DIB/BGR stream, one frame/second,1–4frames,1–64width/height, no audio/index/
metadata/compression is supported. At most2clips/8frames/131072bytes across history. Native
videoMetadata.fps1 is server-owned. Exact-model codec support remains unverified.

Generated PNG output is **Partially implemented behind a startup gate**; configured
`image_output` currently prevents startup. The synthetic tested non-streaming request uses
`tools: [{"type":"image_generation","output_format":"png","size":"1024x1024"}]` with
omitted tool choice. Auto may return text alone or one validated PNG as standard
`image_generation_call` with canonical base64 `result`; text/image order is preserved.
The finite PNG inspector accepts only 1024 RGB/RGBA images up to 1 MiB, without ancillary
chunks. Streaming, other tools/formats/sizes and implicit generated-item replay are unsupported.
Refusal and truncation never fabricate completed image artifacts. See
[implementation evidence](../plans/google-ai-studio-tools-multimodal/generated-image/evidence.md).

Generated WAV output is **Partially implemented behind a startup gate**. The finite synthetic
request uses `extra_body={"foundry_audio_generation":{"version":1,"format":"wav","voice":"Kore"}}`
with OpenAI Python 2.8.1 `responses.create`. Only plain nonempty input up to4096 UTF-8 bytes,
instructions up to1024 bytes and bounded metadata are accepted; tools, history, media, streaming
and stored responses are unsupported. A completed response retains `output: []` and exposes
`foundry_generated_audio` through SDK `model_extra` and `model_dump`: version1,id,format`wav`,
media_type`audio/wav`,sample_rate_hz24000,channels1,sample_width_bits16 and canonical base64`data`.
No transcript or standard audio output item is fabricated. WAV is PCM mono24kHz16bit,
max10seconds/480044bytes; it cannot replay unchanged through the16kHz input profile.
Refusal/truncation never returns a complete artifact. Exact Google transport/codec compatibility
remains unverified; see [audio output evidence](../plans/google-ai-studio-tools-multimodal/generated-audio/evidence.md).


Google compatibility Responses supports a locally verified stateless text policy for the exact
`extra_content.google.thought_signature` output wrapper. The adapter validates a nonempty
opaque signature within 64 KiB UTF-8/control bounds and omits it from public output. This
does not retain reasoning continuity: ordinary text replay is supported, while signed tool
continuation remains separately gated. Requests with tools, structured/media features or
continuation state keep strict provider-state rejection; generic compatible providers do not
inherit this Google policy. Usage and SSE text boundaries remain unchanged. Exact live
acceptance is recorded in the [phase evidence](../plans/google-compatible-signature-text/evidence.md).
