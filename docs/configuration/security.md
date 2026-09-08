# Security

## Status: Partially implemented

The proxy must not be an unrestricted public relay. Client requests require authentication, and `/admin/status` requires separate authentication. The implemented backend client accepts only each configured backend's HTTPS origin and base path, disables redirects, injects only the selected backend credential per attempt, propagates the validated correlation ID, and strips sensitive headers. Retry/failover reuse the same credential-isolation rules and do not forward client secrets upstream. User input must not create arbitrary outbound destinations or an SSRF path. Public listener TLS and network controls remain deployment responsibilities.

## Request Identity and Intake Bounds (Implemented)

The client-supplied `x-request-id` header is validated, echoed back to the client, bound to structured logs, and forwarded upstream unchanged as a correlation ID. It is never used as the credit reservation/finalization key: the middleware also generates a server-owned `request.state.request_key` (a fresh UUID per request) that is threaded through routing, credit reservation, and streaming finalization instead. Duplicate or attacker-supplied `x-request-id` values therefore cannot cause reservation piggybacking or lost cost accounting.

Request bodies are bounded before JSON parsing. A declared `Content-Length` above `max_request_body_bytes` (`FOUNDRY_MAX_REQUEST_BODY_BYTES`, default 2 MiB) is rejected with `413` before any read; when `Content-Length` is absent, the body is read incrementally with the same cap enforced. Token-estimation recursion over nested request JSON is bounded by depth and total character count, failing closed (estimate unavailable) rather than allowing unbounded recursion or memory growth.

Authentication comparisons (`verify_client_auth`, `verify_admin_auth`) evaluate every configured key using `hmac.compare_digest` without an early return, avoiding a timing side channel that could otherwise reveal a matching key's position in the configured list.

## Secret Handling

Use Azure Container Apps secrets or managed identity where practical. Never store API keys, authorization headers, credentials, prompts, or model outputs in source, Git history, Docker images, logs, or normal status responses. Log redaction must be tested rather than assumed.

## Identity and Deployment

Infrastructure should define only the RBAC and identity permissions needed for Foundry access, cost reconciliation, registry access, and deployment. GitHub Actions should prefer OIDC over long-lived credentials. Subscription IDs and resource IDs belong in deployment parameters, not source defaults.

## Required Security Tests

Tests must verify client authentication, administrative authentication, secret and authorization-header redaction, prompt/output non-logging, configured-backend-only egress, and rejection of arbitrary user-supplied endpoint URLs.
