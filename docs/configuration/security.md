# Security

Google PDF preparation is **Implemented locally**, with independent review/resource/client gates passed; exact-model live validation remains pending.
Owned immutable metadata binds exact inspected data before admission; caller page counts cannot
reduce reservations. The worker inherits OS read/network capabilities but the reviewed parser
performs no document-directed I/O. POSIX CPU/address-space/file/fd limits and parent deadlines
bound work; they are not an OS syscall sandbox. Raw PDF grammar and pypdf interpretations must
agree before forwarding. Only Linux currently enforces the required worker limits.

## Status: Implemented (auth, allow-list, redaction, intake bounds, constant-time HMAC; TLS/network remain deployment responsibilities)

The proxy must not be an unrestricted public relay. Client requests require authentication, and `/admin/status` requires separate authentication. The implemented backend client accepts only each configured backend's HTTPS origin and base path, disables redirects, injects only the selected backend credential per attempt, propagates the validated correlation ID, and strips sensitive headers. Retry/failover reuse the same credential-isolation rules and do not forward client secrets upstream. User input must not create arbitrary outbound destinations or an SSRF path. Public listener TLS and network controls remain deployment responsibilities.

## Request Identity and Intake Bounds (Implemented)

The client-supplied `x-request-id` header is validated, echoed back to the client, bound to structured logs, and forwarded upstream unchanged as a correlation ID. It is never used as the credit reservation/finalization key: the middleware also generates a server-owned `request.state.request_key` (a fresh UUID per request) that is threaded through routing, credit reservation, and streaming finalization instead. Duplicate or attacker-supplied `x-request-id` values therefore cannot cause reservation piggybacking or lost cost accounting.

Request bodies are bounded before JSON parsing. A declared `Content-Length` above `max_request_body_bytes` (`FOUNDRY_MAX_REQUEST_BODY_BYTES`, default 2 MiB) is rejected with `413` before any read; when `Content-Length` is absent, the body is read incrementally with the same cap enforced. Token-estimation recursion over nested request JSON is bounded by depth and total character count, failing closed (estimate unavailable) rather than allowing unbounded recursion or memory growth.

Authentication comparisons (`verify_client_auth`, `verify_admin_auth`) evaluate every configured key using `hmac.compare_digest` without an early return, avoiding a timing side channel that could otherwise reveal a matching key's position in the configured list.

## Secret Handling

Use Azure Container Apps secrets or managed identity where practical. Never store API keys, authorization headers, credentials, prompts, or model outputs in source, Git history, Docker images, logs, or normal status responses. Log redaction must be tested rather than assumed.

For Google AI Studio backends, the backend client injects the server-side credential as
`Authorization: Bearer <key>` on the documented OpenAI-compatible surface (verified 2026-10-05;
the native `x-goog-api-key` header is not used there). Client-supplied `Authorization`, `api-key`,
`x-api-key`, and `x-goog-api-key` values are stripped before forwarding, and credential-bearing
query strings (including Google's `key` parameter) are rejected by the backend client. Admin status
and metric labels identify
backends and quota groups by configured IDs only; they never include credentials. Keep project IDs
and quota configuration separate from API key strings. Google recommends restricting API keys and
keeping them confidential; see [API key security guidance](https://docs.cloud.google.com/docs/authentication/api-keys-use).

## Identity and Deployment

Configured `openai_compatible` backends use server-owned Bearer credentials, with caller
auth/cookies/forwarding headers stripped. Raw endpoint validation precedes URL normalization;
outbound requests remain confined to the configured HTTPS origin, port and API root.
Physical model IDs are JSON body values, never URL path segments. The text adapter imports
no Google capability/media/schema helpers, executes no tools and fetches no content URLs.
Only pre-output 429 permits failover; ambiguous dispatched failures retain known usage or
the reservation estimate. Local mocked verification is **Implemented**; actual upstream
compatibility requires separate live evidence.

Infrastructure should define only the RBAC and identity permissions needed for Foundry access, cost reconciliation, registry access, and deployment. GitHub Actions should prefer OIDC over long-lived credentials. Subscription IDs and resource IDs belong in deployment parameters, not source defaults.

The template creates a user-assigned runtime identity before the container app. `AcrPull` (ACR only), `Key Vault Secrets User`, and, in table mode, `Storage Table Data Contributor` are granted to it before app provisioning; storage data access is scoped to each router table. Key Vault references select this identity, and the application selects it through `FOUNDRY_AZURE_CLIENT_ID`. External registries use secret-mode pull with an out-of-band `@secure()` credential. No storage key, SAS token, connection string, or registry credential is committed. Role assignments for pre-existing resources in another resource group deploy through modules scoped to that group. Azure rollout and RBAC propagation still require environment verification.

## Required Security Tests

Tests must verify client authentication, administrative authentication, secret and authorization-header redaction, prompt/output non-logging, configured-backend-only egress, and rejection of arbitrary user-supplied endpoint URLs.

Logical model aliases inherit all target-pool policy without creating capacity or
bypassing capability and continuation rules. Alias configuration adds no per-client
ACLs, wildcard matching, or unknown-model fallback; unconfigured names remain 404
with no reservation or egress.

## Google tool and media boundaries

The adapter executes no tools and fetches no media/schema URLs. Tool arguments/results are
untrusted inert data; each continuation authenticates and reserves independently. Signature
state and unsupported provider fields fail closed in unsigned profiles. Media accepts bounded
inline PNG plus explicitly enabled small baseline JPEG/static VP8L. It checks container/type,
rejects ancillary metadata/animation, validates JPEG entropy completeness under pixel/block/work
budgets, and decodes only bounded small RGB/RGBA rasters. No files, uploads, OCR or transcoding are introduced.
Schema validation resolves no references or regexes. Logs/errors/admin diagnostics contain
configured feature IDs and redacted errors, never arguments, results, media or signatures.

Signed continuation is **Partially implemented** as unattached codec/key/history helpers.
Optional secret configuration is never exposed in settings representations; validation string
errors hide inputs. Do not log ValidationError.errors()/json() with raw inputs. The immutable
key ring derives caller scope only after successful authentication and keeps the matching
key-configuration snapshot for intake binding. No signed output is enabled by configured keys.

Signed runtime integration is **Partially implemented** under its startup gate. Test configurations
with a bound-history pool admit offloaded Responses intake before buffering, using the existing
two signed-work slots and original intake deadline. Saturation returns safe 503 before reading;
slow readers occupy those slots until deadline. Parser cancellation retains active-worker ownership,
and abandoned failures do not reach the asyncio exception logger. The intake 503 body is
byte-identical to the downstream work-lease 503, so no slot-count oracle is introduced; client
authentication runs before body intake, so unauthenticated probers observe 401 rather than 503.
An early 503 may arrive with the request body unconsumed, which can preclude connection reuse;
callers should treat this 503 as retryable through their normal backoff path. These local controls
do not establish the remaining aggregate resource or live-provider gates. See
[signed evidence](../plans/google-ai-studio-tools-multimodal/signed-continuation/evidence.md).
