# Security

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

Infrastructure should define only the RBAC and identity permissions needed for Foundry access, cost reconciliation, registry access, and deployment. GitHub Actions should prefer OIDC over long-lived credentials. Subscription IDs and resource IDs belong in deployment parameters, not source defaults.

The template creates a user-assigned runtime identity before the container app. `AcrPull` (ACR only), `Key Vault Secrets User`, and, in table mode, `Storage Table Data Contributor` are granted to it before app provisioning; storage data access is scoped to each router table. Key Vault references select this identity, and the application selects it through `FOUNDRY_AZURE_CLIENT_ID`. External registries use secret-mode pull with an out-of-band `@secure()` credential. No storage key, SAS token, connection string, or registry credential is committed. Role assignments for pre-existing resources in another resource group deploy through modules scoped to that group. Azure rollout and RBAC propagation still require environment verification.

## Required Security Tests

Tests must verify client authentication, administrative authentication, secret and authorization-header redaction, prompt/output non-logging, configured-backend-only egress, and rejection of arbitrary user-supplied endpoint URLs.
