# Public API

## Status: Partially implemented

The service exposes an OpenAI-compatible base URL such as `https://<host>/openai/v1`. Clients provide the logical model name; the current implementation forwards Responses and embeddings requests using deterministic weighted ordering with health-aware retry, cooldown, and single failover. Equal-weight candidates use the lexicographically smallest backend ID.

The router uses `POST {endpoint}/openai/deployments/{deployment}/{operation}?api-version={api_version}` for the configured Azure OpenAI-compatible backend. The initial backend is the highest-weight healthy candidate for the model, with backend ID used as the deterministic tie-breaker.

## Endpoints

| Method and path | Requirement |
| --- | --- |
| `POST /openai/v1/responses` | Implemented; normal and streaming forwarding |
| `POST /openai/v1/embeddings` | Implemented; embedding forwarding |
| `GET /openai/v1/models` | Required; list configured logical models |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Readiness based on usable configuration/backend state |
| `GET /admin/status` | Implemented; authenticated configuration/model snapshots and live health/credit diagnostics |
| `GET /metrics` | Partially implemented; Prometheus text-format runtime metrics |
| `POST /openai/v1/chat/completions` | Optional; must not delay Responses support |

Malformed requests return a clear 4xx without contacting Foundry. Unknown models return an OpenAI-compatible model-not-found error. When credit-safe estimated capacity is unavailable, the router returns `503` with `insufficient_credit_capacity` and does not dispatch upstream. Retry/failover occurs only for retryable upstream failures and never after meaningful streaming output has begun.

## Authentication

All `/openai/v1/*` endpoints require client authentication. The `/admin/status` and `/metrics` endpoints require separate admin authentication.

### Client Authentication

Provide **one** of:
- Header: `api-key: <your-client-key>`
- Header: `Authorization: Bearer <your-client-key>`

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

**Response (200 OK - Streaming)**
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: {"id": "resp_abc123", "object": "response", "created_at": 1699999999, "model": "gpt-5.4", "output": [{"type": "message", "id": "msg_abc123", "role": "assistant", "content": [{"type": "output_text", "text": "Quantum"}]}]

data: {"id": "resp_abc123", "object": "response", "created_at": 1699999999, "model": "gpt-5.4", "output": [{"type": "message", "id": "msg_abc123", "role": "assistant", "content": [{"type": "output_text", "text": " computing uses"}]}]

data: {"id": "resp_abc123", "object": "response", "created_at": 1699999999, "model": "gpt-5.4", "output": [{"type": "message", "id": "msg_abc123", "role": "assistant", "content": [{"type": "output_text", "text": " quantum bits..."}]}]

data: [DONE]
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
- `authentication_error` - Invalid or missing credentials
- `internal_error` - Unexpected server error

## Streaming Behavior

- SSE events are forwarded without buffering the full response
- Each event boundary is preserved
- Errors occurring after streaming begins are forwarded as SSE events
- No retry or failover after meaningful streaming data has been sent
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
