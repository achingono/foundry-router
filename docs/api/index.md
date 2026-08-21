# Public API

## Status: Design Target

The service will expose an OpenAI-compatible base URL such as `https://<host>/openai/v1`. Clients provide the logical model name; the router chooses the configured Foundry deployment and does not expose backend selection as a client concern.

## Endpoints

| Method and path | Requirement |
| --- | --- |
| `POST /openai/v1/responses` | Required; normal and streaming Responses API requests |
| `POST /openai/v1/embeddings` | Required; embedding requests |
| `GET /openai/v1/models` | Required; list configured logical models |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Readiness based on usable configuration/backend state |
| `GET /admin/status` | Required design target; authenticated routing and credit state |
| `POST /openai/v1/chat/completions` | Optional; must not delay Responses support |

Malformed requests must return a clear 4xx without contacting Foundry. Unknown models must return an OpenAI-compatible model-not-found error. When no backend is safely usable, return a clear upstream-style error and never report success falsely.

## Streaming

For `stream: true`, use asynchronous upstream streaming, preserve SSE event boundaries, avoid buffering the full response, and forward errors that occur after streaming begins. A request may fail over only before meaningful response data has been sent; it must never be retried after streaming has started.

## Authentication and Headers

Client authentication is mandatory for a public deployment. The administrative endpoint requires authentication independently of ordinary model access. Forward only safe, relevant upstream headers; never forward or log credentials belonging to another backend.
